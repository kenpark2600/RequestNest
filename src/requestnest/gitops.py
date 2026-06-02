"""Git operations via subprocess (no extra dependency).

A small wrapper so :mod:`requestnest.sync` can drive git seamlessly. Every
method runs ``git`` in the repo root and raises :class:`GitError` on failure
(except where a non-zero exit is a meaningful answer, e.g. ``commit`` with
nothing staged).
"""

from __future__ import annotations

import subprocess
from pathlib import Path


class GitError(Exception):
    """A git command failed."""


class GitRepo:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        proc = subprocess.run(
            ["git", *args],
            cwd=self.root,
            capture_output=True,
            text=True,
        )
        if check and proc.returncode != 0:
            raise GitError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
        return proc

    # -- inspection -------------------------------------------------------- #

    def is_repo(self) -> bool:
        if not self.root.is_dir():
            return False
        proc = self._run("rev-parse", "--is-inside-work-tree", check=False)
        return proc.returncode == 0 and proc.stdout.strip() == "true"

    def has_remote(self, remote: str) -> bool:
        return remote in self._run("remote").stdout.split()

    def current_branch(self) -> str:
        return self._run("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()

    def remote_ref_exists(self, remote: str, branch: str) -> bool:
        proc = self._run("rev-parse", "--verify", "--quiet", f"{remote}/{branch}", check=False)
        return proc.returncode == 0

    def is_dirty(self, paths: list[str] | None = None) -> bool:
        args = ["status", "--porcelain", *(paths or [])]
        return bool(self._run(*args).stdout.strip())

    def file_at_head(self, path: str) -> str | None:
        proc = self._run("show", f"HEAD:{path}", check=False)
        return proc.stdout if proc.returncode == 0 else None

    # -- drift detection (inputs for requestnest.conflict) ----------------- #

    def behind_count(self, remote: str, branch: str) -> int:
        """Commits on ``remote/branch`` not in local HEAD (0 if ref missing)."""
        if not self.remote_ref_exists(remote, branch):
            return 0
        out = self._run("rev-list", "--count", f"HEAD..{remote}/{branch}").stdout.strip()
        return int(out or "0")

    def upstream_changed_files(self, remote: str, branch: str) -> list[str]:
        if not self.remote_ref_exists(remote, branch):
            return []
        out = self._run("diff", "--name-only", f"HEAD..{remote}/{branch}").stdout
        return [line.strip() for line in out.splitlines() if line.strip()]

    # -- mutations --------------------------------------------------------- #

    def fetch(self, remote: str) -> None:
        self._run("fetch", remote)

    def add(self, paths: list[str]) -> None:
        if paths:
            self._run("add", "--", *paths)

    def commit(self, message: str) -> bool:
        """Commit staged changes. Returns False if there was nothing to commit."""
        proc = self._run("commit", "-m", message, check=False)
        if proc.returncode == 0:
            return True
        if "nothing to commit" in (proc.stdout + proc.stderr).lower():
            return False
        raise GitError(f"git commit failed: {proc.stderr.strip() or proc.stdout.strip()}")

    def push(self, remote: str, branch: str) -> None:
        self._run("push", remote, branch)

    def pull(self, remote: str, branch: str) -> None:
        self._run("pull", remote, branch)
