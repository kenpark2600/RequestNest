"""Shared application context passed from the CLI into the core."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .ui import UI


def _default_ui() -> UI:
    from .ui import RichUI

    return RichUI()


@dataclass
class AppContext:
    """Global flags, resolved paths, and the UI, threaded through every command.

    Created once by the CLI and handed to the UI-agnostic core in
    :mod:`requestnest.sync`. The core reaches the user only via ``ui`` and never
    reads ``click`` state directly — tests inject a fake ``ui``.
    """

    no_git: bool = False
    dry_run: bool = False
    verbose: bool = False
    repo_root: Path = field(default_factory=Path.cwd)
    ui: UI = field(default_factory=_default_ui)

    def __post_init__(self) -> None:
        # Keep the Rich UI's verbosity in sync with the flag.
        if hasattr(self.ui, "verbose"):
            self.ui.verbose = self.verbose
