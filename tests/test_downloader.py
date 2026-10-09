import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ytdl import cli
from ytdl.downloader import DownloadConfig, DownloadResult, build_ydl_opts, download, fetch_info


class DownloaderTests(unittest.TestCase):
    def test_node_is_enabled_and_extra_options_can_override_defaults(self):
        with tempfile.TemporaryDirectory() as folder, patch("ytdl.downloader.which", return_value="node.exe"):
            cfg = DownloadConfig("https://example.com", Path(folder), subtitles=True)
            opts = build_ydl_opts(cfg)
            self.assertEqual(opts["js_runtimes"]["node"], {"path": "node.exe"})
            self.assertEqual(opts["sleep_interval_subtitles"], 5)
            cfg.extra_opts = {"sleep_interval_subtitles": 10}
            self.assertEqual(build_ydl_opts(cfg)["sleep_interval_subtitles"], 10)

    def test_without_node_keeps_deno_and_video_options(self):
        with tempfile.TemporaryDirectory() as folder, patch("ytdl.downloader.which", return_value=None):
            opts = build_ydl_opts(DownloadConfig("https://example.com", Path(folder)))
            self.assertEqual(opts["js_runtimes"], {"deno": {}})
            self.assertNotIn("sleep_interval_subtitles", opts)
            self.assertEqual(opts["sleep_interval"], 5)
            self.assertEqual(opts["max_sleep_interval"], 10)
            self.assertEqual(opts["sleep_interval_requests"], 1)
            self.assertEqual(opts["download_archive"], str(Path(folder) / ".download-archive.txt"))

    def test_metadata_uses_same_runtime(self):
        with patch("ytdl.downloader.which", return_value="node.exe"), patch("ytdl.downloader.YoutubeDL") as engine:
            engine.return_value.__enter__.return_value.extract_info.return_value = {"title": "Example"}
            self.assertEqual(fetch_info("https://example.com"), {"title": "Example"})
            self.assertIn("node", engine.call_args.args[0]["js_runtimes"])
            self.assertEqual(engine.call_args.args[0]["sleep_interval_requests"], 1)

    def test_ignored_errors_and_subtitle_warnings_are_reported(self):
        def simulate(ydl, urls):
            ydl.report_warning("Unable to download video subtitles", only_once=True)
            ydl.report_error("Video unavailable")
            return ydl._download_retcode

        with tempfile.TemporaryDirectory() as folder, patch("ytdl.downloader._ReportingYoutubeDL.download", simulate):
            result = download(DownloadConfig("https://example.com", Path(folder), extra_opts={"quiet": True}))
            self.assertNotEqual(result.exit_code, 0)
            self.assertTrue(result.had_warnings)

    def test_cli_distinguishes_success_warnings_and_errors(self):
        for result, expected_success in [(DownloadResult(0, False), True), (DownloadResult(0, True), False), (DownloadResult(1, False), False)]:
            with self.subTest(result=result), patch.multiple(
                cli, collect_url=unittest.mock.DEFAULT, show_info_panel=unittest.mock.DEFAULT,
                collect_output_dir=unittest.mock.DEFAULT, collect_mode=unittest.mock.DEFAULT,
                collect_subtitles=unittest.mock.DEFAULT, collect_continue_on_error=unittest.mock.DEFAULT,
                confirm_start=unittest.mock.DEFAULT, build_config=unittest.mock.DEFAULT,
                section=unittest.mock.DEFAULT, info=unittest.mock.DEFAULT,
                post_download_menu=unittest.mock.DEFAULT, download=unittest.mock.DEFAULT,
                success=unittest.mock.DEFAULT, warn=unittest.mock.DEFAULT,
            ) as mocks:
                mocks["download"].return_value = result
                mocks["post_download_menu"].return_value = "exit"
                self.assertFalse(cli.run_once())
                self.assertEqual(mocks["success"].called, expected_success)
                self.assertEqual(mocks["warn"].called, not expected_success)


if __name__ == "__main__":
    unittest.main()
