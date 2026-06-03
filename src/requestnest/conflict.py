"""Detect git drift that a push would silently clobber.

The risk: you pulled, edited in Postman, and now push — but a teammate pushed
changes to the *same* resource file in the meantime. Pushing would discard
their work. We detect this by intersecting the files changed upstream (commits
you don't yet have) with the resource files this push is about to overwrite.

Kept pure and git-free so it's trivially testable; :mod:`requestnest.gitops`
supplies the inputs.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ConflictReport:
    behind: int  # upstream commits not in local HEAD
    affected: list[str]  # tracked resource paths changed upstream AND being pushed

    @property
    def has_conflict(self) -> bool:
        return self.behind > 0 and bool(self.affected)

    def message(self) -> str:
        if not self.has_conflict:
            if self.behind:
                return (
                    f"Remote is ahead by {self.behind} commit(s), but none touch the "
                    "resources you're pushing."
                )
            return "Up to date with remote."
        files = ", ".join(sorted(self.affected))
        return (
            f"Remote is ahead by {self.behind} commit(s) and changed resources you're "
            f"about to overwrite: {files}. Run `requestnest pull` first (or re-run with "
            "--force to clobber)."
        )


def assess(
    behind: int, upstream_changed_paths: list[str], pushing_paths: list[str]
) -> ConflictReport:
    """Return a report flagging overlap between upstream changes and this push."""
    upstream = set(upstream_changed_paths)
    affected = [p for p in pushing_paths if p in upstream]
    return ConflictReport(behind=behind, affected=affected)
