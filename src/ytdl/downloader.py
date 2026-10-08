"""Lógica de download usando yt-dlp."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

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
    }

    if cfg.subtitles:
        opts.update({
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["pt", "pt-BR", "en"],
            "subtitlesformat": "srt",
        })

    opts.update(cfg.extra_opts)
    return opts


def fetch_info(url: str) -> dict:
    """Busca metadados sem baixar."""
    with YoutubeDL({"quiet": True, "noplaylist": False, "extract_flat": "in_playlist"}) as ydl:
        return ydl.extract_info(url, download=False) or {}


def download(cfg: DownloadConfig) -> None:
    opts = build_ydl_opts(cfg)
    with YoutubeDL(opts) as ydl:
        ydl.download([cfg.url])
