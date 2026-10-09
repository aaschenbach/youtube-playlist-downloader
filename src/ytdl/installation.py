"""Downloads verificados e ativação atômica de versões, fora do projeto."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request
import zipfile
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

from .engine import Tools
from .settings import REPOSITORY, VERSION, data_dir, read_json, write_json

RELEASE_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
MAX_DOWNLOAD = 600 * 1024 * 1024


def retry_windows(operation, emit=lambda event: None, attempts=8):
    """Executáveis recém-criados podem ficar bloqueados por alguns segundos."""
    for attempt in range(attempts):
        try:
            return operation()
        except OSError as exc:
            if getattr(exc, "winerror", None) not in (5, 32, 33) or attempt == attempts - 1:
                raise
            if attempt == 0:
                emit({"type": "stage", "text": "Aguardando o Windows liberar os arquivos…"})
            time.sleep(min(0.25 * 2 ** attempt, 4))


@contextmanager
def preparation_directory(root: Path, prefix: str, emit):
    staging = Path(tempfile.mkdtemp(prefix=prefix, dir=root)).resolve()
    try:
        yield staging
    finally:
        # Só remove a pasta criada por esta operação; não apaga dados do usuário.
        if staging.parent != root.resolve() or not staging.name.startswith(prefix):
            raise ValueError("A pasta temporária está fora do local de preparação.")
        try:
            retry_windows(lambda: shutil.rmtree(staging), attempts=3)
        except OSError:
            # Limpeza não pode esconder a falha original nem desfazer uma ativação válida.
            emit({"type": "detail", "text": "O Windows adiou a limpeza de arquivos temporários. Isso não altera o resultado da preparação."})


def trusted_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.hostname not in (
        "github.com", "api.github.com", "raw.githubusercontent.com", "nodejs.org",
        "release-assets.githubusercontent.com", "objects.githubusercontent.com",
    ):
        raise ValueError("A origem da atualização não é permitida.")
    return url


def response(url: str):
    request = urllib.request.Request(trusted_url(url), headers={"User-Agent": "YouTubeDownloader/" + VERSION})
    result = urllib.request.urlopen(request, timeout=30)
    trusted_url(result.url)
    return result


def get_json(url: str):
    with response(url) as stream:
        value = stream.read(4 * 1024 * 1024 + 1)
    if len(value) > 4 * 1024 * 1024:
        raise ValueError("Manifesto excede o tamanho permitido.")
    return json.loads(value)


def download_asset(asset: dict, destination: Path, emit=lambda event: None) -> None:
    checksum = asset.get("sha256", "")
    if not re.fullmatch(r"[a-fA-F0-9]{64}", checksum):
        raise ValueError("Atualização sem SHA-256 válido.")
    partial = destination.with_suffix(destination.suffix + ".part")
    digest, count = hashlib.sha256(), 0
    try:
        with response(asset["url"]) as stream, partial.open("wb") as out:
            total = int(stream.headers.get("Content-Length", "0"))
            if total > MAX_DOWNLOAD:
                raise ValueError("Download excede o tamanho permitido.")
            while block := stream.read(256 * 1024):
                count += len(block)
                if count > MAX_DOWNLOAD:
                    raise ValueError("Download excede o tamanho permitido.")
                out.write(block)
                digest.update(block)
                emit({"type": "progress", "percent": min(100, count / total * 100) if total else None, "eta": None})
        if digest.hexdigest().lower() != checksum.lower():
            raise ValueError("A verificação do download falhou. A versão anterior foi preservada.")
        retry_windows(lambda: partial.replace(destination), emit)
    finally:
        try:
            retry_windows(lambda: partial.unlink(missing_ok=True), attempts=3)
        except OSError:
            emit({"type": "detail", "text": "Um arquivo temporário de download permanece bloqueado pelo Windows."})


def extract_zip(archive: Path, destination: Path) -> None:
    destination = destination.resolve()
    with zipfile.ZipFile(archive) as bundle:
        if sum(item.file_size for item in bundle.infolist()) > 1500 * 1024 * 1024:
            raise ValueError("Pacote descompactado excede o tamanho permitido.")
        for item in bundle.infolist():
            name = item.filename.replace("\\", "/")
            target = (destination / name).resolve()
            if not target.is_relative_to(destination) or ":" in name or (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("O pacote contém um caminho inseguro.")
        bundle.extractall(destination)


def executable_version(path: Path, argument="--version", emit=lambda event: None) -> str:
    result = retry_windows(lambda: subprocess.run([str(path), argument], capture_output=True, text=True, encoding="utf-8",
                            timeout=30, check=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0), emit)
    lines = (result.stdout or result.stderr).splitlines()
    return lines[0] if lines else "OK"


def validate_manifest(manifest: dict) -> dict:
    if manifest.get("schema") != 1:
        raise ValueError("Formato de manifesto não suportado.")
    for name in ("yt-dlp", "node", "ffmpeg"):
        asset = manifest.get("tools", {}).get(name, {})
        if not asset.get("version") or not re.fullmatch(r"[a-fA-F0-9]{64}", asset.get("sha256", "")):
            raise ValueError("O manifesto não contém todas as ferramentas verificadas.")
        trusted_url(asset["url"])
    return manifest


def bundled_manifest() -> dict:
    return validate_manifest(read_json(Path(__file__).with_name("tools-manifest.json")))


def latest_manifest() -> dict:
    release = get_json(RELEASE_API)
    asset = next((asset for asset in release["assets"] if asset["name"] == "manifest.json"), None)
    if not asset:
        raise ValueError("Esta Release ainda não possui um pacote de atualização do aplicativo.")
    return validate_manifest(get_json(asset["browser_download_url"]))


class Installation:
    def __init__(self, root: Path | None = None):
        self.root = (root or data_dir()).resolve()

    def state(self) -> dict:
        return read_json(self.root / "installation.json")

    def tools(self) -> Tools | None:
        state = self.state()
        active = state.get("active")
        if not isinstance(active, str):
            return None
        folder = self.root / "tools" / active
        if not folder.resolve().is_relative_to(self.root / "tools"):
            return None
        paths = [folder / name for name in ("yt-dlp.exe", "node.exe", "ffmpeg.exe", "ffprobe.exe")]
        if not all(path.is_file() for path in paths):
            return None
        return Tools(paths[0], paths[1], folder)

    def needs_update(self, manifest: dict) -> bool:
        return self.tools() is None or self.state().get("versions") != {
            name: asset["version"] for name, asset in manifest["tools"].items()}

    def install(self, manifest: dict, emit=lambda event: None) -> Tools:
        manifest = validate_manifest(manifest)
        self.root.mkdir(parents=True, exist_ok=True)
        # O lock também impede duas instalações simultâneas por processos diferentes.
        lock_path = self.root / "install.lock"
        with lock_path.open("a+b") as lock:
            if os.name == "nt":
                import msvcrt
                lock.seek(0)
                if lock.read(1) == b"":
                    lock.write(b"0")
                    lock.flush()
                lock.seek(0)
                try:
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError as exc:
                    raise ValueError("Outra preparação está em andamento. Aguarde sua conclusão.") from exc
            return self._install(manifest, emit)

    def _install(self, manifest, emit):
        folder_name = str(time.time_ns())
        # Executar e depois renomear a pasta pode falhar no Windows. A ativação
        # usa apenas o ponteiro JSON; esta pasta já fica no endereço definitivo.
        prepared = self.root / "tools" / folder_name
        prepared.mkdir(parents=True)
        with preparation_directory(self.root, "prepare-", emit) as staging:
            for name, filenames in (("yt-dlp", ["yt-dlp.exe"]), ("node", ["node.exe"]),
                                    ("ffmpeg", ["ffmpeg.exe", "ffprobe.exe"])):
                asset = manifest["tools"][name]
                emit({"type": "stage", "text": f"Preparando {name} ({asset['version']})…"})
                cache = self.root / "cache"
                cache.mkdir(exist_ok=True)
                payload = cache / (asset["sha256"] + (".zip" if asset.get("archive") else ".exe"))
                valid_cache = False
                if payload.is_file():
                    def check_cache():
                        with payload.open("rb") as stream:
                            return hashlib.file_digest(stream, "sha256").hexdigest() == asset["sha256"].lower()
                    valid_cache = retry_windows(check_cache, emit)
                if not valid_cache:
                    download_asset(asset, payload, emit)
                else:
                    emit({"type": "detail", "text": f"Reutilizando o download verificado de {name}."})
                if asset.get("archive"):
                    unpacked = staging / name
                    extract_zip(payload, unpacked)
                    for filename in filenames:
                        matches = list(unpacked.rglob(filename))
                        if len(matches) != 1:
                            raise ValueError(f"O pacote de {name} não contém {filename} de forma inequívoca.")
                        retry_windows(lambda: shutil.copy2(matches[0], prepared / filename), emit)
                    notices = prepared / "licenses" / name
                    notices.mkdir(parents=True)
                    for notice in unpacked.rglob("*"):
                        if notice.is_file() and notice.name.lower().startswith(("license", "copying", "readme")):
                            retry_windows(lambda: shutil.copy2(notice, notices / notice.name), emit)
                else:
                    retry_windows(lambda: shutil.copy2(payload, prepared / filenames[0]), emit)
            emit({"type": "stage", "text": "Verificando as ferramentas…"})
            for name in ("yt-dlp.exe", "node.exe", "ffmpeg.exe", "ffprobe.exe"):
                executable_version(prepared / name, "-version" if name.startswith("ff") else "--version", emit)
            versions = {name: asset["version"] for name, asset in manifest["tools"].items()}
            previous = self.state().get("active")
            retry_windows(lambda: write_json(self.root / "installation.json", {"active": folder_name, "previous": previous, "versions": versions}), emit)
        tools = self.tools()
        if tools is None:
            raise ValueError("A instalação não foi ativada corretamente.")
        return tools

    def rollback(self):
        state = self.state()
        previous = state.get("previous")
        if not previous or not (self.root / "tools" / previous).resolve().is_relative_to(self.root / "tools"):
            raise ValueError("Não existe uma versão anterior disponível.")
        folder = self.root / "tools" / previous
        for name in ("yt-dlp.exe", "node.exe", "ffmpeg.exe", "ffprobe.exe"):
            executable_version(folder / name, "-version" if name.startswith("ff") else "--version")
        write_json(self.root / "installation.json", {"active": previous, "previous": state["active"], "versions": {}})

    def install_app(self, asset: dict, emit=lambda event: None) -> Path:
        version = asset.get("version", "")
        if not re.fullmatch(r"\d+\.\d+\.\d+", version):
            raise ValueError("Versão do aplicativo inválida.")
        self.root.mkdir(parents=True, exist_ok=True)
        with preparation_directory(self.root, "app-", emit) as staging:
            payload = staging / "app.zip"
            emit({"type": "stage", "text": "Preparando atualização do aplicativo…"})
            download_asset(asset, payload, emit)
            unpacked = staging / "ready"
            extract_zip(payload, unpacked)
            matches = list(unpacked.rglob("YouTube Downloader.exe"))
            if len(matches) != 1:
                raise ValueError("Executável do aplicativo ausente ou duplicado.")
            destination = self.root / "apps" / (version + "-" + str(time.time_ns()))
            destination.parent.mkdir(parents=True, exist_ok=True)
            retry_windows(lambda: unpacked.replace(destination), emit)
            executable = destination / matches[0].relative_to(unpacked)
            executable_version(executable, "--self-test", emit)
            old = read_json(self.root / "app.json").get("active")
            if not old:
                import sys
                old = str(Path(sys.executable).resolve()) if getattr(sys, "frozen", False) else None
            retry_windows(lambda: write_json(self.root / "app.json", {"active": str(executable), "previous": old, "version": version}), emit)
        return executable
