"""Tarefas de download escolhidas pelo usuário, sem dados de sessão."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from .settings import read_json, validate_url, write_json


MODES = ("MP4 — vídeo e áudio", "MP3 — somente áudio")


def load(path: Path) -> list[dict]:
    data = read_json(path, {"downloads": []})
    rows = data.get("downloads", []) if isinstance(data, dict) else []
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict) and
            all(isinstance(row.get(key), str) for key in ("id", "name", "url", "output", "mode")) and
            isinstance(row.get("subtitles"), bool) and isinstance(row.get("playlist"), bool) and
            row["mode"] in MODES]


def save(path: Path, rows: list[dict]) -> None:
    write_json(path, {"version": 1, "downloads": rows})


def make(name: str, url: str, output: str, mode: str, subtitles: bool, playlist: bool, identifier: str | None = None) -> dict:
    name = name.strip()
    if not name:
        raise ValueError("Dê um nome ao download salvo.")
    if mode not in MODES:
        raise ValueError("Escolha MP4 ou MP3.")
    folder = output.strip()
    if not folder:
        raise ValueError("Escolha a pasta de destino.")
    return {"id": identifier or uuid4().hex, "name": name, "url": validate_url(url), "output": folder,
            "mode": mode, "subtitles": bool(subtitles), "playlist": bool(playlist)}
