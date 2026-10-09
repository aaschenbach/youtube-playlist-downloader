"""Componentes de UI — cabeçalho, painéis e helpers de exibição."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

console = Console()


def header() -> None:
    console.print()
    console.print(
        Panel.fit(
            "[bold yellow]▶  YouTube Downloader[/bold yellow]\n"
            "[dim]Baixe vídeos e playlists do YouTube com facilidade[/dim]",
            border_style="yellow",
            padding=(0, 2),
        )
    )
    console.print()


def section(title: str) -> None:
    console.print(Rule(f"[bold cyan]{title}[/bold cyan]", style="cyan"))


def info(msg: str) -> None:
    console.print(f"[cyan]ℹ[/cyan]  {msg}")


def success(msg: str) -> None:
    console.print(f"[green]✔[/green]  {msg}")


def warn(msg: str) -> None:
    console.print(f"[yellow]⚠[/yellow]  {msg}")


def error(msg: str) -> None:
    console.print(f"[red]✘[/red]  {msg}")


def show_summary(url: str, output_dir: Path, mode: str, subtitles: bool) -> None:
    section("Resumo do download")
    console.print(f"  [bold]URL:[/bold]       {url}")
    console.print(f"  [bold]Destino:[/bold]   {output_dir}")
    console.print(f"  [bold]Modo:[/bold]      {mode}")
    console.print(f"  [bold]Legendas:[/bold]  {'sim' if subtitles else 'não'}")
    console.print()
