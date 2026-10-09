import io
import json
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ytdl.downloader import DownloadConfig, build_ydl_opts, fetch_info
from ytdl.engine import Cancelled, Engine, EngineError, Session, Task, Tools
from ytdl.installation import Installation, download_asset, extract_zip, validate_manifest, executable_version, preparation_directory, retry_windows
from ytdl.settings import friendly_error, read_json, redact, validate_cookie_file, validate_url, write_json


URL = "https://youtube.com/live/abcdefghijk"
COOKIE = "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t1999999999\tTEST\tfake-only\n"


class FakeEngine(Engine):
    def __init__(self, tools, lines, code=0):
        self.events = []
        super().__init__(tools, self.events.append)
        self.fixture = lines
        self.calls = []
        self.code = code

    def lines(self, args):
        self.calls.append(args)
        self.process = SimpleNamespace(returncode=self.code)
        yield from self.fixture

    def cancel(self):
        self.cancelled.set()
        self.process.returncode = 1


class SessionTests(unittest.TestCase):
    def test_cookie_config_is_shared_by_query_and_download(self):
        with tempfile.TemporaryDirectory(prefix="espaços ") as temporary:
            folder = Path(temporary)
            cookie = folder / "sessão.txt"
            cookie.write_text(COOKIE, encoding="utf-8")
            task = Task(URL, folder, session=Session(cookie_file=cookie))
            tools = Tools(folder / "yt-dlp.exe", folder / "node.exe", folder)
            engine = FakeEngine(tools, [json.dumps({"title": "Teste"})])
            engine.fetch_info(task)
            engine.fixture = ['YTDL_ITEM:"abc"', 'YTDL_DONE:"abc"']
            result = engine.download(task)
            for args in engine.calls:
                self.assertEqual(args[args.index("--cookies") + 1], str(cookie.resolve()))
                self.assertEqual(args[args.index("--js-runtimes") + 1], "node:" + str(tools.node.resolve()))
                self.assertIn("--ignore-config", args)
                self.assertEqual(args[-2:], ["--", URL])
            self.assertEqual(result.completed, {"abc"})
            cfg = DownloadConfig(URL, folder, session=task.session)
            with patch("ytdl.downloader.YoutubeDL") as library:
                fetch_info(URL, task.session)
                self.assertEqual(library.call_args.args[0]["cookiefile"], build_ydl_opts(cfg)["cookiefile"])

    def test_invalid_or_missing_cookies_fail_before_starting_process(self):
        with tempfile.TemporaryDirectory() as temporary:
            cookie = Path(temporary) / "cookies.txt"
            with self.assertRaises(ValueError):
                validate_cookie_file(cookie)
            cookie.write_text("not Netscape", encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_cookie_file(cookie)
            cookie.write_text(COOKIE.replace(".youtube.com", ".example.com"), encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_cookie_file(cookie)

    def test_browser_denial_differs_from_youtube_rejection(self):
        self.assertIn("ler a sessão", friendly_error("ERROR: Access denied while decrypting Chrome"))
        self.assertIn("recusando", friendly_error("Sign in to confirm you're not a bot"))
        self.assertEqual(Session(browser="firefox", profile="Perfil pessoal").arguments(),
                         ["--cookies-from-browser", "firefox:Perfil pessoal"])

    def test_private_data_is_not_logged(self):
        message = redact("ERROR: https://user:password@example.com/media?token=SECRET cookie=SECRET visitor_data=SECRET")
        for secret in ("password", "SECRET", "user:"):
            self.assertNotIn(secret, message)

    def test_url_restrictions(self):
        self.assertEqual(validate_url(URL), URL)
        for value in ("file:///x", "https://youtube.com.evil.test/watch", "https://user:pass@youtube.com/watch"):
            with self.assertRaises(ValueError):
                validate_url(value)


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.folder = Path(self.temporary.name)
        self.tools = Tools(self.folder / "yt-dlp.exe", self.folder / "node.exe", self.folder)
        self.task = Task(URL, self.folder)

    def tearDown(self):
        self.temporary.cleanup()

    def test_live_refusal_and_finished_live_acceptance(self):
        engine = FakeEngine(self.tools, ['{"is_live":true,"title":"Live"}'])
        with self.assertRaisesRegex(EngineError, "ativa"):
            engine.fetch_info(self.task)
        engine.fixture = ['{"live_status":"was_live","title":"Gravação"}']
        self.assertEqual(engine.fetch_info(self.task)["title"], "Gravação")

    def test_live_filter_accepts_unknown_status_but_refuses_active_or_upcoming(self):
        from yt_dlp.utils import match_filter_func
        engine = FakeEngine(self.tools, [])
        engine.download(self.task)
        arguments = engine.calls[0]
        filter_value = arguments[arguments.index("--match-filter") + 1]
        match = match_filter_func(filter_value)
        for metadata in ({}, {"is_live": False}, {"live_status": "was_live"}):
            self.assertIsNone(match(metadata, incomplete=False))
        for metadata in ({"is_live": True}, {"live_status": "is_upcoming"}):
            self.assertIsNotNone(match(metadata, incomplete=False))

    def test_rate_limit_stops_playlist_without_looping(self):
        engine = FakeEngine(self.tools, ["WARNING: HTTP Error 429", "ERROR: [youtube] abc: Sign in to confirm you're not a bot", 'YTDL_DONE:"wrong"'])
        result = engine.download(self.task)
        self.assertTrue(engine.cancelled.is_set())
        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(result.failed, {"abc"})
        self.assertEqual(result.completed, set())

    def test_archive_is_preserved_and_subtitle_recovery_bypasses_it(self):
        archive = self.folder / ".download-archive.txt"
        archive.write_text("youtube abc\n")
        engine = FakeEngine(self.tools, ["[download] abc: has already been recorded in the archive"])
        result = engine.download(self.task)
        self.assertEqual(result.skipped, {"abc"})
        self.assertIn("--download-archive", engine.calls[-1])
        self.task.subtitles_only = True
        engine.download(self.task)
        self.assertNotIn("--download-archive", engine.calls[-1])
        self.assertIn("--skip-download", engine.calls[-1])
        self.assertIn("--no-overwrites", engine.calls[-1])
        self.assertEqual(archive.read_text(), "youtube abc\n")

    def test_postprocessing_failure_is_not_counted_as_complete(self):
        engine = FakeEngine(self.tools, ['YTDL_ITEM:"abc"', "ERROR: Conversion failed", 'YTDL_DONE:"abc"'])
        result = engine.download(self.task)
        self.assertNotIn("abc", result.completed)
        self.assertIn("abc", result.failed)

    def test_progress_without_total_does_not_invent_percentage(self):
        engine = FakeEngine(self.tools, ['YTDL_PROGRESS:{"downloaded_bytes":123,"eta":null}'])
        engine.download(self.task)
        event = next(event for event in engine.events if event["type"] == "progress")
        self.assertIsNone(event["percent"])
        self.assertIsNone(event["eta"])

    def test_structured_files_waits_and_final_path_validation(self):
        engine = FakeEngine(self.tools, [
            'YTDL_PLAN:{"video":{"id":"abc","title":"Example"},"formats":[],"subtitles":[]}',
            '[download] Sleeping 7.25 seconds ...',
            'YTDL_FILE:{"info":{"format_id":"v"},"progress":{"status":"finished","total_bytes":20,"downloaded_bytes":20}}',
            'YTDL_POST:{"postprocessor":"Merger","status":"started"}',
            'YTDL_DONE:{"id":"abc","filepath":"missing-final.mp4"}'])
        result = engine.download(self.task)
        self.assertIn("abc", result.failed)
        self.assertFalse(result.completed)
        self.assertIn({"type": "waiting", "seconds": 7.25}, engine.events)
        progress = next(event for event in engine.events if event["type"] == "progress")
        self.assertEqual(progress["format_id"], "v")
        self.assertEqual(progress["status"], "finished")
        self.assertEqual(progress["percent"], 100)

    def test_safe_plan_projection_does_not_output_media_urls(self):
        from yt_dlp import YoutubeDL
        engine = FakeEngine(self.tools, [])
        engine.download(self.task)
        template = next(value.split("YTDL_PLAN:", 1)[1] for value in engine.calls[0] if "YTDL_PLAN:" in value)
        output = YoutubeDL().evaluate_outtmpl(template, {"id": "abc", "requested_formats": [
            {"format_id": "a", "url": "SECRET", "http_headers": {"Cookie": "SECRET"}}],
            "requested_subtitles": {"pt": {"ext": "srt", "url": "SECRET"}}})
        self.assertNotIn("SECRET", output)
        self.assertEqual(json.loads(output)["formats"][0]["format_id"], "a")

    def test_sleep_policy_is_not_duplicated_and_also_applies_to_query(self):
        engine = FakeEngine(self.tools, ['{"id":"abc"}'])
        engine.fetch_info(self.task)
        engine.fixture = []
        engine.download(self.task)
        for arguments in engine.calls:
            self.assertEqual(arguments.count("--sleep-requests"), 1)
        self.assertEqual(engine.calls[-1][engine.calls[-1].index("--sleep-interval") + 1], "5")
        self.assertEqual(engine.calls[-1][engine.calls[-1].index("--max-sleep-interval") + 1], "10")

    def test_playlist_position_and_finish_are_emitted_from_real_messages(self):
        engine = FakeEngine(self.tools, ["[download] Downloading item 2 of 5", 'YTDL_ITEM:"abc"',
                                       'YTDL_DONE:"abc"', "[download] Finished downloading playlist: Test"])
        self.task.playlist = True
        engine.download(self.task)
        self.assertIn({"type": "playlist-position", "position": 2, "total": 5}, engine.events)
        self.assertIn({"type": "playlist-finished"}, engine.events)

    def test_error_before_format_selection_does_not_reuse_previous_video_id(self):
        engine = FakeEngine(self.tools, ["[download] Downloading item 1 of 2", 'YTDL_ITEM:"abc"',
            'YTDL_DONE:"abc"', "[download] Downloading item 2 of 2", "ERROR: Requested format unavailable"])
        engine.download(self.task)
        self.assertIn({"type": "playlist-outcome", "status": "Falhou"}, engine.events)
        self.assertNotIn({"type": "item", "id": "abc", "status": "Falhou"}, engine.events)

    def test_cancel_closes_real_child_process(self):
        import sys
        engine = Engine(self.tools)
        started = threading.Event()
        def consume():
            try:
                for line in engine.lines([sys.executable, "-u", "-c", "import time; print('ready', flush=True); time.sleep(30)"]):
                    started.set()
            except Cancelled:
                pass
        worker = threading.Thread(target=consume)
        worker.start()
        self.assertTrue(started.wait(10))
        engine.cancel()
        worker.join(10)
        self.assertFalse(worker.is_alive())
        self.assertIsNotNone(engine.process.poll())


class InstallationTests(unittest.TestCase):
    def manifest(self):
        return {"schema": 1, "tools": {name: {"version": "test", "url": "https://github.com/example/release.exe", "sha256": "a" * 64}
                for name in ("yt-dlp", "node", "ffmpeg")}}

    def test_missing_hash_and_untrusted_url_are_rejected(self):
        manifest = self.manifest()
        manifest["tools"]["node"]["sha256"] = ""
        with self.assertRaises(ValueError):
            validate_manifest(manifest)
        manifest["tools"]["node"]["sha256"] = "a" * 64
        manifest["tools"]["node"]["url"] = "http://example.com/node.exe"
        with self.assertRaises(ValueError):
            validate_manifest(manifest)

    def test_windows_file_lock_is_retried_during_probe(self):
        import subprocess
        busy = PermissionError(13, "arquivo em uso")
        busy.winerror = 32
        result = subprocess.CompletedProcess([], 0, stdout="ffmpeg test\n", stderr="")
        events = []
        with patch("ytdl.installation.subprocess.run", side_effect=[busy, result]) as run, patch("ytdl.installation.time.sleep"):
            self.assertEqual(executable_version(Path("ffmpeg.exe"), "-version", events.append), "ffmpeg test")
            self.assertEqual(run.call_count, 2)
        self.assertTrue(any("Aguardando" in event["text"] for event in events))

    def test_windows_retry_is_bounded_and_other_errors_are_not_retried(self):
        busy = PermissionError(13, "acesso negado")
        busy.winerror = 5
        with patch("ytdl.installation.time.sleep"), patch("ytdl.installation.shutil.copy2", side_effect=busy) as copy:
            with self.assertRaises(PermissionError):
                retry_windows(lambda: copy("source", "destination"), attempts=3)
            self.assertEqual(copy.call_count, 3)
        with patch("ytdl.installation.shutil.copy2", side_effect=OSError("disco cheio")) as copy:
            with self.assertRaises(OSError):
                retry_windows(lambda: copy("source", "destination"))
            self.assertEqual(copy.call_count, 1)

    def test_cleanup_failure_does_not_mask_original_error(self):
        busy = PermissionError(13, "arquivo em uso")
        busy.winerror = 32
        events = []
        with tempfile.TemporaryDirectory() as temporary:
            with patch("ytdl.installation.shutil.rmtree", side_effect=busy), patch("ytdl.installation.time.sleep"):
                with self.assertRaisesRegex(ValueError, "original"):
                    with preparation_directory(Path(temporary), "prepare-", events.append):
                        raise ValueError("original")
        self.assertTrue(any("limpeza" in event["text"] for event in events))

    def test_real_windows_lock_is_released_before_cleanup(self):
        import ctypes
        import os
        import time
        if os.name != "nt":
            self.skipTest("Teste de compartilhamento de arquivos do Windows")
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.restype = ctypes.c_void_p
        kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p,
                                      ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        with tempfile.TemporaryDirectory() as temporary:
            with preparation_directory(Path(temporary), "prepare-", lambda event: None) as staging:
                filename = staging / "locked.txt"
                filename.write_text("fixture")
                handle = kernel.CreateFileW(str(filename), 0x80000000, 1, None, 3, 0x80, None)
                self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
                def release():
                    time.sleep(0.4)
                    kernel.CloseHandle(handle)
                worker = threading.Thread(target=release)
                worker.start()
            worker.join(5)
            self.assertFalse(staging.exists())
    def test_archive_cannot_escape_install_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for filename in ("../escape.txt", "..\\escape.txt", "C:/escape.txt", "file.txt:stream"):
                with zipfile.ZipFile(root / "bad.zip", "w") as archive:
                    archive.writestr(filename, "bad")
                with self.assertRaises(ValueError):
                    extract_zip(root / "bad.zip", root / "inside")
            self.assertFalse((root / "escape.txt").exists())

    def test_corrupted_download_preserves_existing_file_and_removes_partial(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "node.exe"
            path.write_bytes(b"old")
            stream = io.BytesIO(b"corrupted")
            stream.headers = {"Content-Length": "9"}
            with patch("ytdl.installation.response", return_value=stream):
                with self.assertRaisesRegex(ValueError, "verificação"):
                    download_asset(self.manifest()["tools"]["node"], path)
            self.assertEqual(path.read_bytes(), b"old")
            self.assertFalse(path.with_suffix(".exe.part").exists())

    def test_failed_preparation_keeps_active_version_and_preferences(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_json(root / "installation.json", {"active": "old", "versions": {}})
            write_json(root / "preferences.json", {"cookie_file": "private-path"})
            installer = Installation(root)
            with patch("ytdl.installation.download_asset", side_effect=OSError("offline")):
                with self.assertRaises(OSError):
                    installer.install(self.manifest())
            self.assertEqual(installer.state()["active"], "old")
            self.assertEqual(read_json(root / "preferences.json")["cookie_file"], "private-path")

    def test_installation_activates_without_moving_executed_directory_and_reuses_cache(self):
        import hashlib
        payloads = {}
        for name, filenames in (("yt-dlp", ["yt-dlp.exe"]), ("node", ["node.exe"]), ("ffmpeg", ["ffmpeg.exe", "ffprobe.exe"])):
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, "w") as archive:
                for filename in filenames:
                    archive.writestr("bin/" + filename, b"fake executable for test only")
            payloads[name] = stream.getvalue()
        manifest = {"schema": 1, "tools": {name: {"version": "test", "url": f"https://github.com/example/{name}.zip",
            "sha256": hashlib.sha256(payload).hexdigest(), "archive": True} for name, payload in payloads.items()}}
        def fake_download(asset, path, emit):
            name = asset["url"].rsplit("/", 1)[1][:-4]
            path.write_bytes(payloads[name])
        original_replace = Path.replace
        def forbid_directory_move(path, target):
            if path.is_dir():
                error = PermissionError(13, "diretório em uso")
                error.winerror = 5
                raise error
            return original_replace(path, target)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            installer = Installation(root)
            def probe(path, argument, emit):
                self.assertTrue(path.resolve().is_relative_to(root / "tools"))
                return "test"
            with patch("ytdl.installation.download_asset", fake_download), patch("ytdl.installation.executable_version", probe), patch.object(Path, "replace", forbid_directory_move):
                tools = installer.install(manifest)
                self.assertTrue(tools.ffmpeg_dir.is_relative_to(root / "tools"))
                with patch("ytdl.installation.download_asset", side_effect=AssertionError("download repetido")):
                    installer.install(manifest)
            self.assertTrue(installer.tools().ytdlp.is_file())

    def test_app_smoke_test_failure_keeps_old_app(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_json(root / "app.json", {"active": "old.exe"})
            def fake_download(asset, path, emit):
                with zipfile.ZipFile(path, "w") as archive:
                    archive.writestr("App/YouTube Downloader.exe", b"fake")
            with patch("ytdl.installation.download_asset", fake_download), patch("ytdl.installation.executable_version", side_effect=OSError("broken")):
                with self.assertRaises(OSError):
                    Installation(root).install_app({"version": "2.1.0"})
            self.assertEqual(read_json(root / "app.json")["active"], "old.exe")


class GuiTests(unittest.TestCase):
    def test_image_completion_wait_audio_finalization_and_explicit_success(self):
        import tkinter as tk
        from ytdl.gui import Application
        from ytdl.engine import Result
        with tempfile.TemporaryDirectory() as temporary:
            root = tk.Tk()
            root.withdraw()
            try:
                app = Application(root, Installation(Path(temporary)), startup=False)
                app.last_task = Task(URL, Path(temporary))
                app.emit({"type": "video-plan", "video": {"id": "a", "title": "Example"}, "formats": [
                    {"format_id": "v", "acodec": "none"}, {"format_id": "a", "vcodec": "none"}]})
                app.emit({"type": "progress", "format_id": "v", "percent": 100, "status": "finished"})
                app.poll()
                self.assertIn("Ainda falta: áudio", app.progress_text.get())
                self.assertIn("Áudio: Aguardando", app.video_text.get())
                app.emit({"type": "waiting", "seconds": 7})
                app.poll()
                self.assertIn("Pausa entre downloads: áudio", app.status.get())
                self.assertIn("não está pronto", app.progress_text.get())
                app.emit({"type": "progress", "format_id": "a", "percent": None, "downloaded": 40})
                app.poll()
                self.assertIsNone(app.wait_until)
                self.assertIn("tamanho total desconhecido", app.progress_text.get())
                app.emit({"type": "processing", "postprocessor": "Merger", "status": "started"})
                app.poll()
                self.assertEqual(app.status.get(), "Juntando imagem e áudio…")
                app.emit({"type": "item", "id": "a", "status": "Concluído"})
                app.poll()
                app.download_finished(Result(0, completed={"a"}))
                self.assertIn("Vídeo concluído e salvo em:", app.status.get())
                self.assertIn(temporary, app.status.get())
                for callback in root.tk.call("after", "info"):
                    root.after_cancel(callback)
            finally:
                root.destroy()
    def test_playlist_bar_is_independent_of_file_and_remains_partial_on_cancel(self):
        import tkinter as tk
        from ytdl.gui import Application
        with tempfile.TemporaryDirectory() as temporary:
            root = tk.Tk()
            root.withdraw()
            try:
                app = Application(root, Installation(Path(temporary)), startup=False)
                tools = Tools(Path("yt-dlp.exe"), Path("node.exe"), Path(temporary))
                task = Task(URL, Path(temporary), playlist=True)
                with patch.object(app.installation, "tools", return_value=tools), patch.object(app, "background"):
                    app.run_task(task)
                app.emit({"type": "metadata", "value": {"entries": [{"id": "a"}, {"id": "b"}, {"id": "c"}]}})
                app.emit({"type": "playlist-position", "position": 1, "total": 3})
                app.emit({"type": "item", "id": "a", "status": "Baixando"})
                app.emit({"type": "progress", "percent": 100, "eta": 0})
                app.poll()
                self.assertEqual(float(app.playlist_bar["value"]), 0)
                self.assertIn("faltam 3", app.playlist_text.get())
                app.emit({"type": "item", "id": "a", "status": "Concluído"})
                app.emit({"type": "playlist-position", "position": 2, "total": 3})
                app.emit({"type": "cancelled"})
                app.poll()
                self.assertIn("1 de 3 processados", app.playlist_text.get())
                self.assertIn("faltam 2", app.playlist_text.get())
                self.assertLess(float(app.playlist_bar["value"]), 100)
                self.assertIn("Concluídos: 1", app.playlist_counts.get())
                for callback in root.tk.call("after", "info"):
                    root.after_cancel(callback)
            finally:
                root.destroy()

    def test_window_validation_and_removing_session_preserve_original(self):
        import tkinter as tk
        from ytdl.gui import Application
        with tempfile.TemporaryDirectory() as temporary:
            root = tk.Tk()
            root.withdraw()
            try:
                application = Application(root, Installation(Path(temporary)), startup=False)
                application.url.set("not a url")
                application.start_download()
                self.assertIn("link", application.status.get())
                cookie = Path(temporary) / "cookies.txt"
                cookie.write_text(COOKIE)
                application.cookie_path.set(str(cookie))
                application.remove_session()
                self.assertTrue(cookie.exists())
                self.assertEqual(application.cookie_path.get(), "")
                application.emit({"type": "stage", "text": "Consultando"})
                application.poll()
                self.assertEqual(application.status.get(), "Consultando")
                self.assertEqual(str(application.progress["mode"]), "indeterminate")
                application.progress.stop()
                for callback in root.tk.call("after", "info"):
                    root.after_cancel(callback)
            finally:
                root.destroy()


if __name__ == "__main__":
    unittest.main()
