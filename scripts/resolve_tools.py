"""Resolve versões oficiais e grava um manifesto verificável para o build."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ytdl.installation import get_json, response, validate_manifest
from ytdl.settings import VERSION, write_json


def github_asset(repository, release, filename):
    asset = next(asset for asset in release["assets"] if asset["name"] == filename)
    digest = asset.get("digest", "")
    if not digest.startswith("sha256:"):
        raise ValueError(f"A Release de {repository} não forneceu SHA-256 para {filename}.")
    return {"version": release["tag_name"], "url": asset["browser_download_url"],
            "sha256": digest.split(":", 1)[1], "archive": filename.endswith(".zip")}


def resolve():
    yt = get_json("https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest")
    releases = get_json("https://api.github.com/repos/yt-dlp/FFmpeg-Builds/releases?per_page=5")
    ffmpeg = next(release for release in releases if release["tag_name"].startswith("autobuild-") and not release["draft"])
    asset = next(asset for asset in ffmpeg["assets"] if asset["name"].endswith("-win64-gpl.zip"))
    nodes = get_json("https://nodejs.org/dist/index.json")
    node = next(node for node in nodes if node["lts"] and "win-x64-zip" in node["files"] and int(node["version"].split(".")[0][1:]) >= 22)
    filename = f"node-{node['version']}-win-x64.zip"
    base = f"https://nodejs.org/dist/{node['version']}/"
    with response(base + "SHASUMS256.txt") as stream:
        sums = stream.read(128 * 1024).decode("utf-8")
    checksum = next(line.split()[0] for line in sums.splitlines() if line.split()[-1] == filename)
    return validate_manifest({"schema": 1, "version": VERSION, "tools": {
        "yt-dlp": github_asset("yt-dlp/yt-dlp", yt, "yt-dlp.exe"),
        "ffmpeg": github_asset("yt-dlp/FFmpeg-Builds", ffmpeg, asset["name"]),
        "node": {"version": node["version"], "url": base + filename, "sha256": checksum, "archive": True},
    }})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "src/ytdl/tools-manifest.json")
    args = parser.parse_args()
    manifest = resolve()
    write_json(args.output, manifest)
    print("Manifesto verificado:", ", ".join(f"{name} {asset['version']}" for name, asset in manifest["tools"].items()))


if __name__ == "__main__":
    main()
