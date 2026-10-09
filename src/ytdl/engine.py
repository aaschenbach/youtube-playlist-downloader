"""Adaptador do executável: consulta e download compartilham a mesma sessão."""
from __future__ import annotations

import json
import os
import re
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .settings import redact, validate_cookie_file, validate_url

Emit = Callable[[dict], None]


class Cancelled(Exception):
    pass


class EngineError(Exception):
    pass


@dataclass
class Session:
    cookie_file: Path | None = None
    browser: str | None = None
    profile: str = ""

    def arguments(self) -> list[str]:
        if self.cookie_file:
            return ["--cookies", str(validate_cookie_file(self.cookie_file))]
        if self.browser:
            if self.browser not in ("firefox", "chrome", "edge"):
                raise ValueError("Navegador não suportado.")
            return ["--cookies-from-browser", self.browser + (":" + self.profile if self.profile else "")]
        return []


@dataclass
class Tools:
    ytdlp: Path
    node: Path
    ffmpeg_dir: Path


@dataclass
class Task:
    url: str
    output_dir: Path
    audio: bool = False
    subtitles: bool = False
    playlist: bool = False
    subtitles_only: bool = False
    session: Session = field(default_factory=Session)


@dataclass
class Result:
    exit_code: int
    completed: set[str] = field(default_factory=set)
    skipped: set[str] = field(default_factory=set)
    failed: set[str] = field(default_factory=set)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class Engine:
    def __init__(self, tools: Tools, emit: Emit = lambda event: None):
        self.tools, self.emit = tools, emit
        self.cancelled = threading.Event()
        self.process: subprocess.Popen | None = None
        self.lock = threading.Lock()

    def cancel(self):
        self.cancelled.set()
        with self.lock:
            process = self.process
            if process and process.poll() is None:
                # FFmpeg é filho do yt-dlp. Encerrar só o pai deixaria conversões órfãs.
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   creationflags=subprocess.CREATE_NO_WINDOW, timeout=15, check=False)
                else:
                    process.terminate()

    def common(self, task: Task) -> list[str]:
        return [str(self.tools.ytdlp.resolve()), "--ignore-config", "--no-colors", "--encoding", "utf-8",
                "--no-js-runtimes", "--js-runtimes", "node:" + str(self.tools.node.resolve()),
                "--ffmpeg-location", str(self.tools.ffmpeg_dir.resolve()),
                "--socket-timeout", "20", "--retries", "0", "--extractor-retries", "0", "--sleep-requests", "1",
                "--yes-playlist" if task.playlist else "--no-playlist", *task.session.arguments()]

    def lines(self, args: list[str]):
        if self.cancelled.is_set():
            raise Cancelled()
        with self.lock:
            if self.cancelled.is_set():
                raise Cancelled()
            self.process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                            text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL,
                                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            process = self.process
        try:
            assert process.stdout is not None
            for line in process.stdout:
                if self.cancelled.is_set():
                    raise Cancelled()
                yield line.rstrip()
            process.wait()
            if self.cancelled.is_set():
                raise Cancelled()
        finally:
            if process.poll() is None:
                self.cancel()
                process.wait(timeout=20)
            if process.stdout:
                process.stdout.close()

    def fetch_info(self, task: Task) -> dict:
        self.emit({"type": "stage", "text": "Consultando informações…"})
        metadata = None
        failures = []
        args = self.common(task) + ["--dump-single-json", "--flat-playlist", "--", validate_url(task.url)]
        for line in self.lines(args):
            if line.startswith("{"):
                try:
                    metadata = json.loads(line)
                    continue
                except ValueError:
                    pass
            safe = redact(line)
            self.emit({"type": "detail", "text": safe})
            if "ERROR:" in line or "WARNING:" in line:
                failures.append(safe)
        if self.process.returncode or not metadata:
            raise EngineError("\n".join(failures[-8:]) or "Falha ao consultar informações.")
        if metadata.get("is_live") or metadata.get("live_status") in ("is_live", "is_upcoming"):
            raise EngineError("Esta transmissão está ativa ou agendada. Aguarde seu encerramento; gravação ao vivo não é suportada.")
        return metadata

    def download(self, task: Task) -> Result:
        output = task.output_dir.expanduser().resolve()
        output.mkdir(parents=True, exist_ok=True)
        # Testar escrita antes de iniciar qualquer tráfego de download.
        import tempfile
        with tempfile.TemporaryFile(dir=output):
            pass
        args = self.common(task) + ["--newline", "--progress", "--no-quiet", "--no-simulate", "--continue", "--no-overwrites",
            "--windows-filenames", "--ignore-errors", "--sleep-interval", "5",
            "--max-sleep-interval", "10", "--concurrent-fragments", "1",
            "-P", str(output), "-o", "%(playlist_index&{:03d} - |)s%(title).180B [%(id)s].%(ext)s",
            "--print", 'video:YTDL_PLAN:{"video":%(.{id,title,format_id,vcodec,acodec,ext})j,"formats":%(requested_formats.:.{format_id,vcodec,acodec,ext}|[])j,"subtitles":%(requested_subtitles.:.{ext,name}|[])j}',
            "--progress-template", 'download:YTDL_FILE:{"info":%(info.{id,format_id,vcodec,acodec,ext})j,"progress":%(progress.{status,filename,downloaded_bytes,total_bytes,total_bytes_estimate,eta,speed})j}',
            "--progress-template", 'postprocess:YTDL_POST:%(progress.{status,postprocessor})j',
            "--print", "before_dl:YTDL_ITEM:%(id)j", "--print", "after_move:YTDL_DONE:%(.{id,filepath})j"]
        if task.subtitles_only:
            args += ["--skip-download"]
        else:
            args += ["--download-archive", str(output / ".download-archive.txt")]
            args += ["-f", "bestaudio/best", "-x", "--audio-format", "mp3", "--audio-quality", "192K"] if task.audio else [
                "-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]", "--merge-output-format", "mp4"]
        if task.subtitles or task.subtitles_only:
            args += ["--write-subs", "--write-auto-subs", "--sub-langs", "pt,pt-BR,en", "--sub-format", "srt/best",
                     "--convert-subs", "srt", "--sleep-subtitles", "5"]
        args += ["--match-filter", "!is_live & live_status!=?is_upcoming", "--", validate_url(task.url)]
        result = Result(0)
        current = ""
        subtitle_file = None
        self.emit({"type": "stage", "text": "Recuperando legendas…" if task.subtitles_only else "Baixando…"})
        for line in self.lines(args):
            position = re.search(r"^\[download\] Downloading item (\d+) of (\d+|N/A)", line)
            if position:
                current = ""
                subtitle_file = None
                self.emit({"type": "playlist-position", "position": int(position[1]),
                           "total": int(position[2]) if position[2].isdigit() else None})
            if line.startswith("[download] Finished downloading playlist:"):
                self.emit({"type": "playlist-finished"})
            if line.startswith("YTDL_PLAN:"):
                plan = json.loads(line.split(":", 1)[1])
                current = str(plan["video"]["id"])
                subtitle_file = None
                self.emit({"type": "video-plan", **plan, "audio": task.audio,
                           "subtitles_requested": task.subtitles or task.subtitles_only, "subtitles_only": task.subtitles_only})
                continue
            if line.startswith("YTDL_POST:"):
                self.emit({"type": "processing", **json.loads(line.split(":", 1)[1])})
                continue
            if line.startswith(("YTDL_PROGRESS:", "YTDL_FILE:")):
                try:
                    payload = json.loads(line.split(":", 1)[1])
                    progress = payload.get("progress", payload)
                    info = payload.get("info", {})
                    downloaded = progress.get("downloaded_bytes") or 0
                    total = progress.get("total_bytes") or progress.get("total_bytes_estimate")
                    self.emit({"type": "progress", "percent": min(100, downloaded / total * 100) if total else None,
                               "eta": progress.get("eta"), "speed": progress.get("speed"),
                               "downloaded": downloaded, "total": total, "estimated": not progress.get("total_bytes"),
                               "status": progress.get("status"), "filename": progress.get("filename"),
                               "format_id": info.get("format_id"), "subtitle": bool(subtitle_file)})
                except (ValueError, TypeError):
                    pass
                continue
            if line.startswith(("YTDL_ITEM:", "YTDL_DONE:")):
                payload = json.loads(line.split(":", 1)[1])
                identifier = str(payload["id"] if isinstance(payload, dict) else payload)
                if line.startswith("YTDL_DONE:"):
                    if isinstance(payload, dict) and not task.subtitles_only and not Path(payload.get("filepath") or "").is_file():
                        result.failed.add(identifier)
                        result.errors.append("O arquivo final não foi encontrado na pasta de destino.")
                        self.emit({"type": "item", "id": identifier, "status": "Falhou"})
                    if identifier not in result.failed:
                        result.completed.add(identifier)
                        self.emit({"type": "item", "id": identifier, "status": "Concluído"})
                else:
                    subtitle_file = None
                    self.emit({"type": "subtitles-ready"})
                    current = identifier
                    self.emit({"type": "item", "id": identifier, "status": "Baixando"})
                continue
            safe = redact(line)
            self.emit({"type": "detail", "text": safe})
            sleep = re.search(r"^\[download\] Sleeping ([\d.]+) seconds", line)
            if sleep:
                self.emit({"type": "waiting", "seconds": float(sleep[1])})
            if line.startswith("[info] Writing video subtitles to:"):
                subtitle_file = line.split("to:", 1)[1].strip()
                self.emit({"type": "subtitle-start", "filename": subtitle_file})
            if re.search(r"^\[info\] Video subtitle .* is already present", line):
                self.emit({"type": "subtitle-existing"})
            if "has already been recorded in the archive" in line:
                match = re.search(r"(?:\[download\]\s+)?([\w-]+):.*already been recorded", line)
                if match:
                    result.skipped.add(match[1])
                    self.emit({"type": "item", "id": match[1], "status": "Já baixado"})
            if "WARNING:" in line:
                result.warnings.append(safe)
                if "Unable to download video subtitles" in line:
                    self.emit({"type": "subtitle-failure"})
            if "does not pass filter" in line:
                result.warnings.append("Uma transmissão ativa/agendada foi pulada. " + safe)
                self.emit({"type": "playlist-filtered", "title": line.removeprefix("[download] ").split(" does not pass filter", 1)[0]})
            if "ERROR:" in line:
                result.errors.append(safe)
                match = re.search(r"\[youtube\]\s+([\w-]+):", line)
                identifier = match[1] if match else current
                if identifier:
                    result.failed.add(identifier)
                    self.emit({"type": "item", "id": identifier, "status": "Falhou"})
                else:
                    self.emit({"type": "playlist-outcome", "status": "Falhou"})
                # Não continuar uma playlist inteira quando a sessão foi bloqueada.
                if any(value in line.lower() for value in ("429", "not a bot", "sign in to confirm")):
                    self.cancel()
                    break
        result.exit_code = self.process.returncode or (1 if result.errors else 0)
        result.completed.difference_update(result.failed)
        return result
