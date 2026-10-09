"""Cria ZIP e manifesto de Release; não publica automaticamente."""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ytdl.installation import bundled_manifest  # noqa: E402
from ytdl.settings import REPOSITORY, VERSION, write_json  # noqa: E402


def main():
    if sys.platform != "win32":
        raise SystemExit("O build deve ser executado no Windows.")
    manifest = bundled_manifest()
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--onedir",
        "--name", "YouTube Downloader", "--paths", str(ROOT / "src"),
        "--add-data", str(ROOT / "src/ytdl/tools-manifest.json") + ";ytdl",
        "--specpath", str(ROOT / "build"), str(ROOT / "scripts/window_entry.py")], cwd=ROOT, check=True)
    folder = ROOT / "dist/YouTube Downloader"
    shutil.copy2(ROOT / "LEIA-ME.txt", folder)
    shutil.copy2(ROOT / "THIRD_PARTY_NOTICES.md", folder)
    notices = folder / "licenses"
    notices.mkdir(exist_ok=True)
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if not python_license.is_file():
        python_license = Path(sys.base_prefix) / "LICENSE"
    if not python_license.is_file():
        raise FileNotFoundError("Licença do Python não encontrada; o pacote não será distribuído sem ela.")
    shutil.copy2(python_license, notices / "PYTHON-LICENSE.txt")
    for source in (Path(sys.base_prefix) / "tcl").rglob("license*"):
        if source.is_file():
            shutil.copy2(source, notices / (source.parent.name + "-" + source.name))
    executable = folder / "YouTube Downloader.exe"
    subprocess.run([str(executable), "--self-test"], check=True, timeout=60)
    filename = f"YouTubeDownloader-{VERSION}-Windows-x64"
    archive = Path(shutil.make_archive(str(ROOT / "dist" / filename), "zip", root_dir=folder.parent, base_dir=folder.name))
    with archive.open("rb") as stream:
        checksum = hashlib.file_digest(stream, "sha256").hexdigest()
    manifest["app"] = {"version": VERSION, "url": f"https://github.com/{REPOSITORY}/releases/download/v{VERSION}/{archive.name}", "sha256": checksum}
    write_json(ROOT / "dist/manifest.json", manifest)
    (ROOT / "dist/SHA256SUMS.txt").write_text(f"{checksum}  {archive.name}\n", encoding="ascii")
    print("Pacote criado:", archive)


if __name__ == "__main__":
    main()
