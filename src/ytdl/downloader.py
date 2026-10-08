"""Lógica de download usando yt-dlp."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from shutil import which

from yt_dlp import YoutubeDL


@dataclass
class DownloadConfig:
    url: str
    output_dir: Path
    format_selector: str = "bv*+ba/b"
    merge_format: str = "mp4"
    continue_on_error: bool = True
    audio_only: bool = False
    subtitles: bool = False
    extra_opts: dict = field(default_factory=dict)


@dataclass
class DownloadResult:
    exit_code: int
    had_warnings: bool


class _ReportingYoutubeDL(YoutubeDL):
    had_warnings = False

    def report_warning(self, message, *args, **kwargs):
        self.had_warnings = True
        return super().report_warning(message, *args, **kwargs)


def runtime_opts() -> dict:
    # Deno mantém a prioridade; Node precisa ser habilitado explicitamente.
    runtimes = {"deno": {}}
    node = which("node")
    if node:
        runtimes["node"] = {"path": node}
    return {"js_runtimes": runtimes}


def build_ydl_opts(cfg: DownloadConfig) -> dict:
    out_dir = cfg.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    if cfg.audio_only:
        fmt = "bestaudio/best"
        outtmpl = str(out_dir / "%(playlist_index)03d - %(title)s [%(id)s].%(ext)s")
        postprocessors = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}]
    else:
        fmt = cfg.format_selector
        outtmpl = str(out_dir / "%(playlist_index)03d - %(title)s [%(id)s].%(ext)s")
        postprocessors = []

    opts: dict = {
        "format": fmt,
        "outtmpl": outtmpl,
        "merge_output_format": cfg.merge_format,
        "download_archive": str(out_dir / ".download-archive.txt"),
        "noplaylist": False,
        "ignoreerrors": cfg.continue_on_error,
        "windowsfilenames": True,
        "retries": 5,
        "concurrent_fragment_downloads": 4,
        "postprocessors": postprocessors,
        **runtime_opts(),
    }

    if cfg.subtitles:
        opts.update({
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["pt", "pt-BR", "en"],
            "subtitlesformat": "srt",
            "sleep_interval_requests": 1,
            "sleep_interval_subtitles": 5,
        })

    opts.update(cfg.extra_opts)
    return opts


def fetch_info(url: str) -> dict:
    """Busca metadados sem baixar."""
    with YoutubeDL({"quiet": True, "noplaylist": False, "extract_flat": "in_playlist", **runtime_opts()}) as ydl:
        return ydl.extract_info(url, download=False) or {}


def download(cfg: DownloadConfig) -> DownloadResult:
    opts = build_ydl_opts(cfg)
    with _ReportingYoutubeDL(opts) as ydl:
        exit_code = ydl.download([cfg.url])
        return DownloadResult(exit_code=exit_code, had_warnings=ydl.had_warnings)
