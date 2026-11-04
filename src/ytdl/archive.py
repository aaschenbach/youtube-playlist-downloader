"""Históricos por formato, preservando o histórico legado sem alterações."""
from __future__ import annotations

import re
from pathlib import Path


def archive_for(output: Path, audio: bool) -> Path:
    mp4 = output / ".download-archive-mp4.txt"
    mp3 = output / ".download-archive-mp3.txt"
    legacy = output / ".download-archive.txt"
    if legacy.is_file() and (not mp4.exists() or not mp3.exists()):
        media = {"mp4": set(), "mp3": set()}
        for file in output.iterdir():
            if file.is_file() and file.suffix.lower() in (".mp4", ".mp3"):
                match = re.search(r"\[([^\]]+)\]$", file.stem)
                if match:
                    media[file.suffix.lower()[1:]].add(match.group(1))
        lines = legacy.read_text(encoding="utf-8-sig").splitlines(keepends=True)
        for path, extension in ((mp4, "mp4"), (mp3, "mp3")):
            if path.exists():
                continue
            selected = []
            for line in lines:
                identifier = line.strip().rsplit(" ", 1)[-1]
                found = {kind for kind, ids in media.items() if identifier in ids}
                if not found or extension in found:
                    selected.append(line)
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_text("".join(selected), encoding="utf-8")
            temporary.replace(path)
    return mp3 if audio else mp4
