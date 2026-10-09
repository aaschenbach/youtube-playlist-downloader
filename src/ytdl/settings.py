"""Preferências locais; nunca guarda o conteúdo da sessão."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

APP_NAME = "YouTubeDownloader"
VERSION = "2.0.4"
REPOSITORY = "aaschenbach/youtube-playlist-downloader"


def data_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / APP_NAME


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {} if default is None else default


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def validate_cookie_file(path: Path) -> Path:
    path = path.expanduser().resolve()
    try:
        with path.open(encoding="utf-8-sig") as stream:
            header = stream.readline().strip()
            if header not in ("# Netscape HTTP Cookie File", "# HTTP Cookie File"):
                raise ValueError("O arquivo não está no formato cookies.txt (Netscape). Exporte novamente seguindo a ajuda.")
            found = False
            for line in stream:
                if line.startswith("#HttpOnly_"):
                    line = line[len("#HttpOnly_"):]
                elif line.startswith("#") or not line.strip():
                    continue
                fields = line.rstrip("\r\n").split("\t")
                if len(fields) != 7 or not fields[4].isdigit():
                    raise ValueError("O arquivo de cookies possui linhas inválidas. Exporte novamente seguindo a ajuda.")
                domain = fields[0].lstrip(".").lower()
                if domain == "youtube.com" or domain.endswith(".youtube.com"):
                    found = True
            if not found:
                raise ValueError("Este arquivo não contém uma sessão do YouTube. Exporte os cookies de youtube.com.")
    except (OSError, UnicodeError) as exc:
        raise ValueError("Não foi possível ler o arquivo de cookies. Selecione um arquivo acessível.") from exc
    return path


def validate_url(value: str) -> str:
    value = value.strip()
    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https") or parsed.username or parsed.password:
        raise ValueError("Cole um link completo do YouTube, começando com https://.")
    if host not in ("youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"):
        raise ValueError("Este aplicativo aceita links do YouTube.")
    return value


def redact(message: str) -> str:
    # URLs extraídas podem carregar tokens de mídia. Os detalhes não precisam deles.
    def clean(match):
        parsed = urlsplit(match.group())
        return urlunsplit((parsed.scheme, parsed.hostname or "", parsed.path, "", ""))
    message = re.sub(r"https?://[^\s]+", clean, message)
    return re.sub(r"(?i)(cookie|authorization|token|visitor_data)\s*[:=]\s*[^\s]+", r"\1=[oculto]", message)


def friendly_error(raw: str) -> str:
    text = raw.lower()
    if "winerror 32" in text or "winerror 33" in text or "winerror 5" in text:
        return "O Windows não liberou os arquivos necessários à preparação. Aguarde e use Preparar / atualizar novamente. A instalação anterior foi preservada."
    if "429" in text or "too many requests" in text:
        return "O YouTube limitou as consultas. Aguarde antes de tentar novamente. Sua tarefa foi preservada; não faremos novas tentativas automaticamente."
    if any(word in text for word in ("dpapi", "decrypt", "permission denied", "access denied", "could not copy", "acesso negado")):
        return "Não foi possível ler a sessão do navegador. Use Selecionar cookies.txt ou escolha um perfil do Firefox em Sessão."
    if "sign in" in text or "not a bot" in text:
        return "O YouTube pediu uma verificação. Abra o vídeo no navegador e configure um arquivo cookies.txt em Sessão. Se você já fez isso, o YouTube ainda está recusando esta sessão; você pode substituí-la ou tentar mais tarde."
    if "cookie" in text:
        return "A sessão não pôde ser usada. Selecione um arquivo cookies.txt válido ou exporte uma nova sessão seguindo a ajuda."
    if "ffmpeg" in text or "javascript runtime" in text:
        return "Uma ferramenta necessária falhou. Use Preparar / atualizar para verificar a instalação."
    if "requested format" in text:
        return "O YouTube não ofereceu o formato escolhido para este vídeo. Você pode tentar MP3 ou consultar os detalhes."
    if "unavailable" in text or "private video" in text or "not available" in text:
        return "O YouTube informou que o conteúdo não está disponível para esta sessão. Verifique se ele abre no navegador."
    if "permission" in text or "acesso" in text:
        return "Não foi possível acessar a pasta ou o arquivo. Escolha uma pasta em que você possa salvar."
    return "Não foi possível concluir a operação. Verifique sua conexão e abra Detalhes para consultar o motivo. A tarefa foi preservada."
