"""Command-line entry point for RequestNest.

This module is a thin *presentation* layer: it parses arguments, builds an
:class:`~requestnest.context.AppContext`, and delegates all real work to the
UI-agnostic core in :mod:`requestnest.sync`. Keeping logic out of here is what
makes a future TUI / web UI a cheap addition (see the plan's layering rule).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import click

from . import __version__

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


def _dispatch(app: Any, fn: Callable[..., None], **kwargs: Any) -> None:
    """Run a core function, mapping domain errors to a clean message + exit 1."""
    from .config import ConfigError
    from .gitops import GitError
    from .postman import PostmanError
    from .sync import SyncError

    try:
        fn(app, **kwargs)
    except (SyncError, ConfigError, PostmanError, GitError) as exc:
        app.ui.error(str(exc))
        raise SystemExit(1) from exc


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(__version__, prog_name="requestnest")
@click.option("--no-git", is_flag=True, help="Do not run any git commands (overrides config).")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would happen without writing files, calling the API, or committing.",
)
@click.option("-v", "--verbose", is_flag=True, help="Verbose output.")
@click.pass_context
def main(ctx: click.Context, no_git: bool, dry_run: bool, verbose: bool) -> None:
    """RequestNest: sync your personal Postman workspace with a shared git repo."""
    from .config import find_repo_root
    from .context import AppContext

    ctx.obj = AppContext(
        no_git=no_git,
        dry_run=dry_run,
        verbose=verbose,
        repo_root=find_repo_root(),
    )


@main.command()
@click.pass_obj
def init(app) -> None:
    """Set up RequestNest in this repo (fresh) or join an existing config."""
    from . import sync

    _dispatch(app, sync.init)


@main.command()
@click.pass_obj
def setup(app) -> None:
    """Guided onboarding for an existing shared repo: join + pull + secrets."""
    from . import sync

    _dispatch(app, sync.setup)


@main.command()
@click.argument("names", nargs=-1)
@click.option(
    "--allow-unmarked-secrets",
    is_flag=True,
    help="Push even if the safety scan finds token-shaped values not marked as secret.",
)
@click.option("--force", is_flag=True, help="Push even if it would clobber upstream changes.")
@click.pass_obj
def push(app, names: tuple[str, ...], allow_unmarked_secrets: bool, force: bool) -> None:
    """Publish workspace resources to git (workspace -> git)."""
    from . import sync

    _dispatch(
        app,
        sync.push,
        names=names,
        allow_unmarked_secrets=allow_unmarked_secrets,
        force=force,
    )


@main.command()
@click.argument("names", nargs=-1)
@click.pass_obj
def pull(app, names: tuple[str, ...]) -> None:
    """Import shared resources into your workspace (git -> workspace)."""
    from . import sync

    _dispatch(app, sync.pull, names=names)


@main.command()
@click.argument("names", nargs=-1)
@click.pass_obj
def diff(app, names: tuple[str, ...]) -> None:
    """Show a semantic diff between your live workspace and the git version."""
    from . import sync

    _dispatch(app, sync.diff, names=names)


@main.command(name="list")
@click.pass_obj
def list_(app) -> None:
    """List tracked resources, whether you've imported them, and secret status."""
    from . import sync

    _dispatch(app, sync.list_resources)


@main.command()
@click.pass_obj
def status(app) -> None:
    """Show divergence, missing secrets, and the gitignore guard state."""
    from . import sync

    _dispatch(app, sync.status)


@main.command()
@click.pass_obj
def verify(app) -> None:
    """CI check: committed JSON is normalized and free of secret-shaped values."""
    from . import sync

    _dispatch(app, sync.verify)


@main.group()
def secrets() -> None:
    """Manage local secret values and the committable secrets template."""


@secrets.command(name="check")
@click.pass_obj
def secrets_check(app) -> None:
    """Verify all required secret values are present locally."""
    from . import sync

    _dispatch(app, sync.secrets_check)


if __name__ == "__main__":  # pragma: no cover
    main()
