"""Presentation layer.

``sync`` talks to the user only through the :class:`UI` protocol, so swapping in
a TUI or web UI later means writing one new class — no core changes. :class:`RichUI`
is the terminal implementation; tests inject a fake.
"""

from __future__ import annotations

import sys
from typing import Protocol, runtime_checkable

from .semantic_diff import DiffResult


def _make_output_utf8_safe() -> None:
    """Best-effort: stop non-ASCII output from crashing on legacy Windows consoles.

    On a cp1252 console (or redirected output), printing characters outside the
    code page raises UnicodeEncodeError. Reconfiguring to UTF-8 with
    ``errors="replace"`` keeps the CLI robust against arbitrary collection content.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError, OSError):
            pass


@runtime_checkable
class UI(Protocol):
    def info(self, message: str) -> None: ...
    def success(self, message: str) -> None: ...
    def warn(self, message: str) -> None: ...
    def error(self, message: str) -> None: ...
    def detail(self, message: str) -> None: ...  # shown only when verbose
    def confirm(self, question: str, *, default: bool = False) -> bool: ...
    def prompt(
        self, question: str, *, password: bool = False, default: str | None = None
    ) -> str: ...
    def select(
        self, title: str, options: list[tuple[str, str]], *, preselect_all: bool = True
    ) -> list[str]: ...
    def show_diff(self, diff: DiffResult) -> None: ...
    def table(self, title: str, columns: list[str], rows: list[list[str]]) -> None: ...


class RichUI:
    """Terminal UI built on Rich."""

    def __init__(self, verbose: bool = False) -> None:
        from rich.console import Console

        _make_output_utf8_safe()
        self.verbose = verbose
        self._console = Console()
        self._err = Console(stderr=True)

    def info(self, message: str) -> None:
        self._console.print(message)

    def success(self, message: str) -> None:
        self._console.print(f"[green]ok[/green] {message}")

    def warn(self, message: str) -> None:
        self._console.print(f"[yellow]warning[/yellow] {message}")

    def error(self, message: str) -> None:
        self._err.print(f"[red]error[/red] {message}")

    def detail(self, message: str) -> None:
        if self.verbose:
            self._console.print(f"[dim]{message}[/dim]")

    def confirm(self, question: str, *, default: bool = False) -> bool:
        from rich.prompt import Confirm

        return Confirm.ask(question, default=default, console=self._console)

    def prompt(self, question: str, *, password: bool = False, default: str | None = None) -> str:
        from rich.prompt import Prompt

        return Prompt.ask(question, password=password, default=default, console=self._console)

    def select(
        self, title: str, options: list[tuple[str, str]], *, preselect_all: bool = True
    ) -> list[str]:
        """Numbered multiselect. Returns the chosen option *values*.

        Rich has no native checkbox list, so we present a numbered menu and accept
        comma-separated indices or ``all`` / ``none``.
        """
        if not options:
            return []
        self._console.print(f"\n[bold]{title}[/bold]")
        for i, (_value, label) in enumerate(options, start=1):
            self._console.print(f"  [cyan]{i}[/cyan]. {label}")
        default = "all" if preselect_all else ""
        raw = (
            self.prompt("Select (comma-separated numbers, 'all', or 'none')", default=default)
            .strip()
            .lower()
        )
        if raw in ("", "none"):
            return []
        if raw == "all":
            return [value for value, _ in options]
        chosen: list[str] = []
        for part in raw.split(","):
            part = part.strip()
            if part.isdigit() and 1 <= int(part) <= len(options):
                chosen.append(options[int(part) - 1][0])
        return chosen

    def show_diff(self, diff: DiffResult) -> None:
        if diff.is_empty:
            self._console.print(f"[dim]{diff.label}: no changes[/dim]")
            return
        self._console.print(f"\n[bold]{diff.label}[/bold]")
        colors = {"added": "green", "removed": "red", "changed": "yellow"}
        symbols = {"added": "+", "removed": "-", "changed": "~"}
        for change in diff.changes:
            color = colors[change.kind]
            line = f"  [{color}]{symbols[change.kind]} {change.path}[/{color}]"
            if change.details:
                line += f" [dim]({', '.join(change.details)})[/dim]"
            self._console.print(line)

    def table(self, title: str, columns: list[str], rows: list[list[str]]) -> None:
        from rich.table import Table

        table = Table(title=title, title_justify="left")
        for column in columns:
            table.add_column(column)
        for row in rows:
            table.add_row(*row)
        self._console.print(table)
