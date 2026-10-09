"""Validação local isolada; não lê cookies reais nem acessa vídeos."""
from __future__ import annotations

import argparse
import subprocess
import sys
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ytdl.engine import Engine, Task  # noqa: E402
from ytdl.gui import Application  # noqa: E402
from ytdl.installation import Installation, bundled_manifest  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--capture", action="store_true", help="Requer Pillow no ambiente de desenvolvimento")
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--package", type=Path, help="Testa instalação local do ZIP sem publicar Release")
    parser.add_argument("--fixture", action="store_true", help="Testa motor com vídeo próprio em HTTP local")
    parser.add_argument("--playlist-preview", action="store_true", help="Mostra um estado controlado da playlist nas capturas")
    args = parser.parse_args()
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    installation = Installation(artifacts / "Windows com espaços e acentos")
    if args.fixture:
        import functools
        import tempfile
        import threading
        from dataclasses import replace
        from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
        from unittest.mock import patch
        tools = installation.tools()
        if tools is None:
            raise ValueError("Execute --prepare antes de --fixture.")
        class Handler(SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass
        with tempfile.TemporaryDirectory(dir=artifacts, prefix="fixture-") as temporary:
            folder = Path(temporary)
            subprocess.run([str(tools.ffmpeg_dir / "ffmpeg.exe"), "-v", "error", "-f", "lavfi", "-i",
                "color=c=blue:s=160x90:d=1", "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                "-c:v", "libx264", "-c:a", "aac", "-shortest", str(folder / "sample.mp4")],
                check=True, timeout=30, capture_output=True)
            server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(folder)))
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                url = f"http://127.0.0.1:{server.server_port}/sample.mp4"
                task = Task(url, folder / "downloads")
                with patch("ytdl.engine.validate_url", lambda value: value):
                    engine = Engine(tools)
                    meta = engine.fetch_info(task)
                    if not meta.get("id"):
                        raise AssertionError("Metadados não retornaram ID.")
                    first = engine.download(task)
                    second = Engine(tools).download(task)
                    audio = Engine(tools).download(replace(task, output_dir=folder / "audio", audio=True))
                    if first.exit_code or not first.completed or second.exit_code or not second.skipped:
                        raise AssertionError(f"Download/arquivo divergiram: {first!r}, {second!r}")
                    if audio.exit_code or not list((folder / "audio").glob("*.mp3")):
                        raise AssertionError(f"Conversão MP3 divergiu: {audio!r}")
                print("Motor real: metadados, MP4, histórico e MP3 em HTTP local: OK")
                subprocess.run([str(tools.ffmpeg_dir / "ffmpeg.exe"), "-v", "error", "-i", str(folder / "sample.mp4"),
                    "-map", "0:v", "-map", "0:a", "-c", "copy", "-f", "dash", "-seg_duration", "1",
                    "-adaptation_sets", "id=0,streams=v id=1,streams=a", str(folder / "manifest.mpd")],
                    check=True, timeout=30, capture_output=True, cwd=folder)
                separated_events = []
                with patch("ytdl.engine.validate_url", lambda value: value):
                    separated = Engine(tools, separated_events.append).download(Task(
                        f"http://127.0.0.1:{server.server_port}/manifest.mpd", folder / "separated"))
                media_files = {event.get("format_id") for event in separated_events if event["type"] == "progress" and event.get("format_id")}
                if separated.exit_code or not separated.completed or len(media_files) != 2:
                    print("\n".join(event.get("text", str(event)) for event in separated_events), flush=True)
                    raise AssertionError(f"Imagem e áudio separados divergiram: {separated!r}, {media_files!r}")
                if not any(event["type"] == "processing" and event.get("postprocessor") == "Merger" for event in separated_events):
                    raise AssertionError("Evento real de junção não foi recebido.")
                if sum(event["type"] == "waiting" for event in separated_events) != 2:
                    raise AssertionError("Esperas reais dos dois arquivos não foram recebidas.")
                if not any(event["type"] == "video-plan" and len(event["formats"]) == 2 for event in separated_events):
                    raise AssertionError("Plano real dos dois arquivos não foi recebido.")
                print("Imagem e áudio separados, esperas, identidade dos arquivos e junção reais: OK")
                import shutil
                from ytdl.playlist_progress import PlaylistProgress
                shutil.copy2(folder / "sample.mp4", folder / "sample2.mp4")
                (folder / "playlist.html").write_text('<html><head><title>Lista de teste</title></head><body>'
                    '<video src="sample.mp4" controls></video><video src="sample2.mp4" controls></video></body></html>', encoding="utf-8")
                playlist_task = Task(f"http://127.0.0.1:{server.server_port}/playlist.html", folder / "playlist", playlist=True)
                with patch("ytdl.engine.validate_url", lambda value: value):
                    for attempt in range(2):
                        events = []
                        playlist_engine = Engine(tools, events.append)
                        metadata = playlist_engine.fetch_info(playlist_task)
                        tracker = PlaylistProgress.from_metadata(metadata)
                        result = playlist_engine.download(playlist_task)
                        for event in events:
                            if event["type"] == "playlist-position":
                                tracker.begin(event["position"], event["total"])
                            elif event["type"] == "item":
                                tracker.record(event["id"], event["status"])
                            elif event["type"] == "playlist-finished":
                                tracker.finish()
                        if result.exit_code or tracker.total != 2 or tracker.processed != 2 or tracker.remaining != 0:
                            raise AssertionError(f"Progresso real de playlist divergiu: {result!r}, {tracker!r}")
                        expected = "Concluído" if attempt == 0 else "Já baixado"
                        if tracker.count(expected) != 2:
                            raise AssertionError(f"Resultado real de playlist divergiu: {expected}, {tracker!r}")
                print("Playlist real em HTTP local: total, progresso, conclusões e itens já baixados: OK")
            finally:
                server.shutdown()
                server.server_close()
                worker.join(5)
    if args.package:
        import hashlib
        import shutil
        from unittest.mock import patch
        from ytdl.settings import VERSION
        def local_download(asset, path, emit):
            with args.package.open("rb") as source:
                checksum = hashlib.file_digest(source, "sha256").hexdigest()
            if checksum != asset["sha256"]:
                raise ValueError("SHA-256 do pacote local divergiu.")
            shutil.copy2(args.package, path)
        with args.package.open("rb") as source:
            checksum = hashlib.file_digest(source, "sha256").hexdigest()
        with patch("ytdl.installation.download_asset", local_download):
            path = installation.install_app({"version": VERSION, "sha256": checksum})
        print("Atualização local, extração e teste do executável: OK", path.name)
    if args.prepare:
        tools = installation.install(bundled_manifest(), lambda event: print(event["text"]) if event["type"] == "stage" else None)
        # O parser real precisa aceitar os argumentos sem acessar o YouTube.
        engine = Engine(tools)
        task = Task("https://youtube.com/live/abcdefghijk", artifacts / "downloads")
        subprocess.run(engine.common(task) + ["--match-filter", "!is_live & live_status!=?is_upcoming", "--version"],
                       check=True, timeout=30)
        print("Preparação isolada e argumentos reais: OK")
    if args.capture:
        from PIL import ImageGrab
        root = tk.Tk()
        root.tk.call("tk", "scaling", float(root.tk.call("tk", "scaling")) * args.scale)
        app = Application(root, installation, startup=False)
        root.attributes("-topmost", True)
        def capture(name):
            root.update()
            left, top = root.winfo_rootx(), root.winfo_rooty()
            filename = name if args.scale == 1 else name.replace(".png", f"-{args.scale:g}x.png")
            ImageGrab.grab(bbox=(left, top, left + root.winfo_width(), top + root.winfo_height())).save(artifacts / filename)
        def inspect():
            if args.playlist_preview:
                app.playlist_tracking = True
                app.playlist_frame.grid()
                app.url.set("https://www.youtube.com/playlist?list=exemplo")
                app.emit({"type": "metadata", "value": {"title": "Playlist de exemplo", "entries": [
                    {"id": str(index), "title": f"Vídeo de exemplo {index}"} for index in range(1, 6)]}})
                for position, status in ((1, "Concluído"), (2, "Já baixado"), (3, "Falhou")):
                    app.emit({"type": "playlist-position", "position": position, "total": 5})
                    app.emit({"type": "item", "id": str(position), "status": status})
                app.emit({"type": "playlist-position", "position": 4, "total": 5})
                app.emit({"type": "item", "id": "4", "status": "Baixando"})
                app.emit({"type": "video-plan", "video": {"id": "4", "title": "Vídeo de exemplo 4"}, "formats": [
                    {"format_id": "v", "acodec": "none", "vcodec": "h264"},
                    {"format_id": "a", "vcodec": "none", "acodec": "aac"}]})
                app.emit({"type": "progress", "percent": 100, "status": "finished", "format_id": "v"})
                app.emit({"type": "waiting", "seconds": 7})
                app.poll()
            capture("janela-inicial.png")
            if args.playlist_preview:
                app.emit({"type": "progress", "percent": 46, "format_id": "a", "downloaded": 4_600_000, "total": 10_000_000, "speed": 300_000, "eta": 18})
                app.poll()
                capture("janela-audio.png")
                app.emit({"type": "progress", "percent": 100, "status": "finished", "format_id": "a"})
                app.emit({"type": "processing", "postprocessor": "Merger", "status": "started"})
                app.poll()
                capture("janela-finalizacao.png")
                app.emit({"type": "item", "id": "4", "status": "Concluído"})
                app.emit({"type": "item", "id": "5", "status": "Já baixado"})
                app.poll()
                app.status.set("Playlist encerrada: 2 concluídos, 2 já baixados e 1 com falha. Use Abrir pasta ou Tentar novamente / retomar.")
                capture("janela-conclusao.png")
            from tkinter import ttk
            def notebooks(widget):
                for child in widget.winfo_children():
                    if isinstance(child, ttk.Notebook):
                        yield child
                    yield from notebooks(child)
            notebook = next(notebooks(root))
            notebook.select(1)
            capture("janela-sessao.png")
            notebook.select(2)
            capture("janela-atualizacao.png")
            root.destroy()
            print("Capturas de interface gravadas em artifacts/.")
        root.after(800, inspect)
        root.mainloop()


if __name__ == "__main__":
    main()
