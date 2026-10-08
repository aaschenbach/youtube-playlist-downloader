"""Ponto de entrada — menu interativo CLI."""

from __future__ import annotations

import sys
from pathlib import Path

import questionary
from questionary import Style
from yt_dlp import DownloadError

from .downloader import DownloadConfig, download, fetch_info
from .ui import console, error, header, info, section, show_summary, success, warn

# ─── Estilo do questionary ────────────────────────────────────────────────────

STYLE = Style(
    [
        ("qmark", "fg:#f5c518 bold"),
        ("question", "bold"),
        ("answer", "fg:#f5c518 bold"),
        ("pointer", "fg:#f5c518 bold"),
        ("highlighted", "fg:#f5c518 bold"),
        ("selected", "fg:#00c896"),
        ("separator", "fg:#555555"),
        ("instruction", "fg:#888888"),
    ]
)

# ─── Helpers ──────────────────────────────────────────────────────────────────

DEFAULT_OUTPUT = Path.home() / "Downloads" / "YouTube"

_ERROR_HINTS: list[tuple[str, str]] = [
    (
        "ffmpeg",
        "FFmpeg não encontrado.\n"
        "  → Instale em https://ffmpeg.org/download.html e adicione ao PATH.\n"
        "  → Windows: winget install ffmpeg\n"
        "  → macOS: brew install ffmpeg\n"
        "  → Linux: sudo apt install ffmpeg",
    ),
    (
        "Sign in to confirm",
        "O YouTube pediu verificação de login (anti-bot).\n"
        "  → Exporte seus cookies com a extensão 'Get cookies.txt LOCALLY' do Chrome.\n"
        "  → Salve como cookies.txt na pasta do projeto.\n"
        "  → Adicione 'cookiefile: \"cookies.txt\"' em src/ytdl/downloader.py.",
    ),
    (
        "Video unavailable",
        "Vídeo indisponível (removido, privado ou bloqueado no seu país).\n"
        "  → Se for uma playlist, habilite 'Continuar em erros' no menu.",
    ),
    (
        "Private video",
        "Vídeo privado — não é possível baixar sem acesso à conta do dono.\n"
        "  → Se for uma playlist, habilite 'Continuar em erros' para pular e continuar.",
    ),
    (
        "This video is not available",
        "Vídeo não disponível na sua região.\n"
        "  → Tente com uma VPN ou verifique se o conteúdo é acessível no seu país.",
    ),
    (
        "HTTP Error 429",
        "O YouTube bloqueou temporariamente as requisições (muitos downloads).\n"
        "  → Aguarde alguns minutos e tente novamente.",
    ),
    (
        "Unable to extract",
        "Não foi possível extrair as informações do vídeo.\n"
        "  → Verifique se a URL está correta e se o vídeo ainda existe.\n"
        "  → Tente atualizar o yt-dlp: uv sync --upgrade-package yt-dlp --upgrade-package yt-dlp-ejs\n"
        "  → Com pip: python -m pip install -U 'yt-dlp[default,curl-cffi]'",
    ),
    (
        "PermissionError",
        "Sem permissão para salvar na pasta escolhida.\n"
        "  → Escolha uma pasta diferente, como ~/Downloads/YouTube.",
    ),
]


def _friendly_error(raw: str) -> str:
    """Retorna dica amigável ou a mensagem original se não houver hint."""
    for keyword, hint in _ERROR_HINTS:
        if keyword.lower() in raw.lower():
            return hint
    return raw


def ask(fn, *args, **kwargs):
    """Wrapper que encerra o programa ao pressionar Ctrl+C."""
    result = fn(*args, **kwargs, style=STYLE).ask()
    if result is None:
        console.print("\n[dim]Operação cancelada. Até mais![/dim]\n")
        sys.exit(0)
    return result


# ─── Etapas do fluxo ─────────────────────────────────────────────────────────

def collect_url() -> str:
    section("Passo 1 de 5 — URL")
    console.print("[dim]Cole a URL de um vídeo ou de uma playlist do YouTube.[/dim]\n")
    url = ask(questionary.text, "URL:")
    url = url.strip()
    if not url.startswith("http"):
        error("A URL deve começar com http:// ou https://")
        console.print("  → Exemplo: https://www.youtube.com/watch?v=dQw4w9WgXcQ\n")
        return collect_url()
    return url


def collect_output_dir() -> Path:
    section("Passo 2 de 5 — Pasta de destino")
    console.print(f"[dim]Onde salvar os arquivos. Padrão: {DEFAULT_OUTPUT}[/dim]\n")
    raw = ask(
        questionary.text,
        "Pasta de destino:",
        default=str(DEFAULT_OUTPUT),
    )
    path = Path(raw).expanduser()
    if path.exists() and not path.is_dir():
        error(f"'{path}' existe mas não é uma pasta. Escolha outro caminho.")
        return collect_output_dir()
    return path


def collect_mode() -> str:
    section("Passo 3 de 5 — Modo de download")
    console.print("[dim]Escolha o formato de saída dos arquivos.[/dim]\n")
    return ask(
        questionary.select,
        "O que deseja baixar?",
        choices=[
            questionary.Choice("🎬  Vídeo + áudio  (MP4 — melhor qualidade)", value="video"),
            questionary.Choice("🎵  Somente áudio  (MP3 — 192 kbps)", value="audio"),
            questionary.Choice("🎬  Melhor qualidade disponível  (automático)", value="auto"),
        ],
    )


def collect_subtitles() -> bool:
    section("Passo 4 de 5 — Legendas")
    console.print("[dim]Baixa legendas em PT e EN quando disponíveis (formato .srt).[/dim]\n")
    return ask(
        questionary.confirm,
        "Baixar legendas (PT / EN) quando disponíveis?",
        default=False,
    )


def collect_continue_on_error() -> bool:
    section("Passo 5 de 5 — Comportamento em erros")
    console.print(
        "[dim]Se um vídeo da playlist estiver indisponível, continuar ou parar?[/dim]\n"
    )
    return ask(
        questionary.confirm,
        "Continuar playlist mesmo se um vídeo falhar?",
        default=True,
    )


def confirm_start(url: str, output_dir: Path, mode: str, subtitles: bool) -> bool:
    show_summary(url, output_dir, mode, subtitles)
    return ask(questionary.confirm, "Iniciar download agora?", default=True)


# ─── Painel de informações ────────────────────────────────────────────────────

def show_info_panel(url: str) -> None:
    info("Buscando informações da URL… (pode levar alguns segundos)")
    try:
        meta = fetch_info(url)
    except DownloadError as exc:
        msg = _friendly_error(str(exc))
        warn(f"Não foi possível buscar metadados:\n  {msg}")
        console.print()
        return
    except Exception as exc:
        warn(f"Erro inesperado ao buscar metadados: {exc}")
        console.print()
        return

    title = meta.get("title") or meta.get("webpage_url_basename") or "—"
    entries = meta.get("entries") or []
    count = len(entries) if entries else None
    uploader = meta.get("uploader") or meta.get("channel") or "—"

    section("Informações encontradas")
    console.print(f"  [bold]Título:[/bold]   {title}")
    console.print(f"  [bold]Canal:[/bold]    {uploader}")
    if count:
        console.print(f"  [bold]Vídeos:[/bold]   {count} na playlist")
    console.print()


# ─── Config ──────────────────────────────────────────────────────────────────

def build_config(
    url: str,
    output_dir: Path,
    mode: str,
    subtitles: bool,
    continue_on_error: bool,
) -> DownloadConfig:
    audio_only = mode == "audio"
    fmt = {
        "video": "bv*+ba/b",
        "audio": "bestaudio/best",
        "auto": "bv*+ba/b",
    }[mode]
    return DownloadConfig(
        url=url,
        output_dir=output_dir,
        format_selector=fmt,
        audio_only=audio_only,
        subtitles=subtitles,
        continue_on_error=continue_on_error,
    )


# ─── Pós-download ────────────────────────────────────────────────────────────

def post_download_menu(output_dir: Path) -> str:
    section("O que fazer agora?")
    action = ask(
        questionary.select,
        "Escolha uma opção:",
        choices=[
            questionary.Choice("🔄  Baixar outra URL", value="again"),
            questionary.Choice("📂  Abrir pasta de destino", value="open"),
            questionary.Choice("🚪  Sair", value="exit"),
        ],
    )
    if action == "open":
        import os
        import subprocess
        try:
            if sys.platform == "win32":
                os.startfile(output_dir)  # noqa: S606
            elif sys.platform == "darwin":
                subprocess.run(["open", str(output_dir)], check=False)
            else:
                subprocess.run(["xdg-open", str(output_dir)], check=False)
            info(f"Pasta aberta: {output_dir}")
        except Exception:
            warn(
                f"Não foi possível abrir a pasta automaticamente.\n"
                f"  → Caminho: {output_dir}"
            )
        return "again"
    return action


# ─── Ciclo principal ─────────────────────────────────────────────────────────

def run_once() -> bool:
    """Executa um ciclo completo. Retorna True se deve rodar de novo."""
    url = collect_url()
    show_info_panel(url)
    output_dir = collect_output_dir()
    mode = collect_mode()
    subtitles = collect_subtitles()
    continue_on_error = collect_continue_on_error()

    if not confirm_start(url, output_dir, mode, subtitles):
        warn("Download cancelado pelo usuário.")
        return False

    section("Iniciando download")
    info(f"Salvando em: {output_dir}")
    console.print()

    cfg = build_config(url, output_dir, mode, subtitles, continue_on_error)

    try:
        result = download(cfg)
        console.print()
        if result.exit_code:
            warn("Download encerrado com erros. Alguns itens podem não ter sido baixados.")
        elif result.had_warnings:
            warn("Download encerrado com avisos. Confira as mensagens e as legendas na pasta de destino.")
        else:
            success("Download concluído!")
    except DownloadError as exc:
        console.print()
        hint = _friendly_error(str(exc))
        error("Falha no download.")
        console.print(f"\n[red]Detalhes:[/red]\n  {hint}\n")
    except PermissionError:
        console.print()
        error(
            "Sem permissão para salvar arquivos na pasta escolhida.\n"
            f"  → Pasta: {output_dir}\n"
            "  → Escolha uma pasta diferente na próxima vez."
        )
    except KeyboardInterrupt:
        console.print()
        warn("Download interrompido pelo usuário (Ctrl+C).")
        return False
    except Exception as exc:
        console.print()
        error(
            f"Erro inesperado: {exc}\n"
            "  → Se persistir, abra uma issue em:\n"
            "    https://github.com/aaschenbach/youtube-playlist-downloader/issues"
        )

    action = post_download_menu(output_dir)
    return action == "again"


# ─── Entry-point ─────────────────────────────────────────────────────────────

def main() -> None:
    header()
    while True:
        try:
            again = run_once()
        except KeyboardInterrupt:
            again = False

        if not again:
            console.print("\n[dim]Até mais! 👋[/dim]\n")
            break

        console.print()
