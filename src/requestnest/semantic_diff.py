"""Human-readable structural diffs of Postman collections and environments.

Raw JSON diffs are noisy, so this compares at meaningful granularity: per
*request* for collections (flattened to ``Folder/Request`` paths) and per
*variable* for environments. Secret values are never printed — a changed
secret is reported as "changed", not shown.

Inputs are normalized first (volatile ids/timestamps stripped) so identity
churn never shows up as a change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .normalize import normalized_obj

#: Request sub-objects compared to describe *what* changed within a request.
REQUEST_ASPECTS = ("method", "url", "header", "body", "auth")


@dataclass
class Change:
    kind: str  # "added" | "removed" | "changed"
    path: str
    details: list[str] = field(default_factory=list)


@dataclass
class DiffResult:
    label: str
    changes: list[Change] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.changes

    def summary(self) -> list[str]:
        """Plain-text lines (used in tests and non-Rich contexts)."""
        symbol = {"added": "+", "removed": "-", "changed": "~"}
        lines = []
        for change in self.changes:
            line = f"{symbol[change.kind]} {change.path}"
            if change.details:
                line += f" ({', '.join(change.details)})"
            lines.append(line)
        return lines


def _flatten_items(items: list[dict[str, Any]] | None, prefix: str = "") -> dict[str, dict]:
    """Flatten a collection item tree to ``{path: request_obj}``."""
    result: dict[str, dict] = {}
    for item in items or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "<unnamed>"))
        path = f"{prefix}/{name}" if prefix else name
        if "item" in item:  # folder
            result.update(_flatten_items(item.get("item"), path))
        else:
            result[path] = item.get("request", {}) or {}
    return result


def diff_collections(old: dict[str, Any], new: dict[str, Any], label: str = "") -> DiffResult:
    old_n = normalized_obj(old)
    new_n = normalized_obj(new)
    old_reqs = _flatten_items(old_n.get("item"))
    new_reqs = _flatten_items(new_n.get("item"))

    result = DiffResult(label=label)
    for path in sorted(set(old_reqs) - set(new_reqs)):
        result.changes.append(Change("removed", path))
    for path in sorted(set(new_reqs) - set(old_reqs)):
        result.changes.append(Change("added", path))
    for path in sorted(set(old_reqs) & set(new_reqs)):
        details = [a for a in REQUEST_ASPECTS if old_reqs[path].get(a) != new_reqs[path].get(a)]
        if details:
            result.changes.append(Change("changed", path, details))
    return result


def diff_environments(old: dict[str, Any], new: dict[str, Any], label: str = "") -> DiffResult:
    old_vars = {v["key"]: v for v in normalized_obj(old).get("values", []) if "key" in v}
    new_vars = {v["key"]: v for v in normalized_obj(new).get("values", []) if "key" in v}

    result = DiffResult(label=label)
    for key in sorted(set(old_vars) - set(new_vars)):
        result.changes.append(Change("removed", key))
    for key in sorted(set(new_vars) - set(old_vars)):
        result.changes.append(Change("added", key))
    for key in sorted(set(old_vars) & set(new_vars)):
        details = [
            a for a in ("value", "enabled", "type") if old_vars[key].get(a) != new_vars[key].get(a)
        ]
        if details:
            # Don't leak values; just name the aspects that changed.
            result.changes.append(Change("changed", key, details))
    return result
