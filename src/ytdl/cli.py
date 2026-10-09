"""Ponto de entrada — menu interativo CLI."""

from __future__ import annotations

import sys
from pathlib import Path

import questionary
from questionary import Style
from yt_dlp import DownloadError

from .downloader import DownloadConfig, download, fetch_info, saved_session
from .settings import friendly_error, data_dir, read_json, write_json, validate_cookie_file, redact
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

def _friendly_error(raw: str) -> str:
    """Explica falhas sem atribuir causas que não foram confirmadas."""
    return friendly_error(raw)


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

def show_info_panel(url: str) -> bool:
    info("Buscando informações da URL… (pode levar alguns segundos)")
    try:
        meta = fetch_info(url)
    except DownloadError as exc:
        msg = _friendly_error(str(exc))
        warn(f"Não foi possível buscar metadados:\n  {msg}")
        console.print()
        return False
    except Exception as exc:
        warn(f"Não foi possível consultar informações: {redact(str(exc))}")
        console.print()
        return False

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
    return True


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
        session=saved_session(),
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
    if show_info_panel(url) is False:
        warn("Resolva a sessão pelo menu inicial ou tente mais tarde. O download não será iniciado.")
        return True
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
            action = ask(questionary.select, "O que deseja fazer?", choices=["Baixar", "Configurar sessão", "Sair"])
            if action == "Sair":
                break
            if action == "Configurar sessão":
                raw = ask(questionary.text, "Caminho do cookies.txt (vazio remove a sessão):").strip().strip('"')
                try:
                    cookie = str(validate_cookie_file(Path(raw))) if raw else ""
                    preferences = read_json(data_dir() / "preferences.json")
                    preferences.update(cookie_file=cookie, browser="Sem sessão", profile="")
                    write_json(data_dir() / "preferences.json", preferences)
                    success("Configuração salva. Consulta e download usarão a mesma sessão.")
                except ValueError as exc:
                    error(str(exc))
                continue
            again = run_once()
        except KeyboardInterrupt:
            again = False

        if not again:
            console.print("\n[dim]Até mais! 👋[/dim]\n")
            break

        console.print()
