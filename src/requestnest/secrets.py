"""Secret sanitization, restoration, and the leak safety-net.

The plan's three-layer secret detection:

1. **Primary** — Postman's native ``type == "secret"`` variable flag.
2. **Override** — keys listed under an environment's ``secrets:`` in config.
3. **Safety net** — :func:`safety_scan` blocks a push if any *non*-secret value
   looks like a token (PMAK-, AWS key, JWT, long hex/base64).

On push, secret values become ``{{key}}`` placeholders (the variable's own key)
and the real values are captured for the local secrets file. On pull, the
placeholders are restored from that file.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

#: A committed secret value is exactly the variable's own key as a Postman var.
PLACEHOLDER_RE = re.compile(r"^\{\{([A-Za-z0-9_.\-]+)\}\}$")

#: Token-shaped patterns the safety net refuses to commit (name -> regex).
TOKEN_PATTERNS: dict[str, re.Pattern[str]] = {
    "postman-key": re.compile(r"PMAK-[0-9a-fA-F]{24}-[0-9a-fA-F]{34}"),
    "aws-access-key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "jwt": re.compile(r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"),
    "long-hex": re.compile(r"\b[0-9a-fA-F]{32,}\b"),
    "high-entropy-b64": re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\b"),
}


@dataclass
class SecretFinding:
    """A token-shaped value the safety scan flagged in a not-marked-secret place."""

    location: str
    pattern: str
    preview: str


def placeholder_for(key: str) -> str:
    return f"{{{{{key}}}}}"


def parse_placeholder(value: Any) -> str | None:
    """Return the placeholder name if ``value`` is exactly ``{{name}}``, else None."""
    if not isinstance(value, str):
        return None
    match = PLACEHOLDER_RE.match(value)
    return match.group(1) if match else None


def _is_secret_entry(entry: dict[str, Any], override_keys: Iterable[str]) -> bool:
    return entry.get("type") == "secret" or entry.get("key") in set(override_keys)


def needed_secret_keys(env_obj: dict[str, Any], override_keys: Iterable[str] = ()) -> list[str]:
    """Keys an environment requires secret values for (order-preserving, deduped).

    Detects placeholders in committed JSON plus secret-typed / overridden keys.
    """
    override = set(override_keys)
    keys: list[str] = []
    for entry in env_obj.get("values", []) or []:
        if not isinstance(entry, dict):
            continue
        placeholder = parse_placeholder(entry.get("value", ""))
        if placeholder:
            keys.append(placeholder)
        elif _is_secret_entry(entry, override):
            key = entry.get("key")
            if key:
                keys.append(str(key))
    # Dedupe, preserve first-seen order.
    seen: set[str] = set()
    return [k for k in keys if not (k in seen or seen.add(k))]


def sanitize_environment(
    env_obj: dict[str, Any], override_keys: Iterable[str] = ()
) -> tuple[dict[str, Any], dict[str, str]]:
    """Replace secret values with ``{{key}}`` placeholders.

    Returns ``(sanitized_env, captured)`` where ``captured`` maps key -> the real
    value pulled out (only for non-empty, non-placeholder values).
    """
    override = set(override_keys)
    sanitized = copy.deepcopy(env_obj)
    captured: dict[str, str] = {}
    for entry in sanitized.get("values", []) or []:
        if not isinstance(entry, dict) or not _is_secret_entry(entry, override):
            continue
        key = str(entry.get("key", ""))
        if not key:
            continue
        value = entry.get("value", "")
        if isinstance(value, str) and value and parse_placeholder(value) is None:
            captured[key] = value
        entry["value"] = placeholder_for(key)
        entry["type"] = "secret"  # mark so the next reader treats it as secret too
    return sanitized, captured


def desanitize_environment(
    env_obj: dict[str, Any],
    env_secrets: dict[str, str],
    override_keys: Iterable[str] = (),
) -> tuple[dict[str, Any], list[str]]:
    """Restore real secret values from ``env_secrets``.

    Returns ``(restored_env, missing_keys)``. A key is *missing* when it is needed
    but absent/empty in ``env_secrets``.
    """
    override = set(override_keys)
    restored = copy.deepcopy(env_obj)
    missing: list[str] = []
    for entry in restored.get("values", []) or []:
        if not isinstance(entry, dict):
            continue
        placeholder = parse_placeholder(entry.get("value", ""))
        if placeholder:
            target = placeholder
        elif _is_secret_entry(entry, override) and not entry.get("value"):
            target = str(entry.get("key", ""))
        else:
            continue
        if not target:
            continue
        value = env_secrets.get(target)
        if value:
            entry["value"] = value
        elif target not in missing:
            missing.append(target)
    return restored, missing


def safety_scan(obj: Any) -> list[SecretFinding]:
    """Recursively flag token-shaped strings (the un-marked-secret leak guard).

    Placeholders (``{{...}}``) never match the token patterns, so a properly
    sanitized environment is clean; this catches secrets hardcoded elsewhere
    (e.g. an Authorization header baked into a collection request).
    """
    findings: list[SecretFinding] = []
    _scan(obj, "$", findings)
    return findings


def _scan(value: Any, path: str, findings: list[SecretFinding]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            _scan(child, f"{path}.{key}", findings)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan(child, f"{path}[{index}]", findings)
    elif isinstance(value, str):
        if parse_placeholder(value):
            return
        for name, pattern in TOKEN_PATTERNS.items():
            match = pattern.search(value)
            if match:
                findings.append(SecretFinding(path, name, _mask(match.group(0))))
                return  # one finding per value is enough to block


def _mask(token: str) -> str:
    if len(token) <= 8:
        return "*" * len(token)
    return f"{token[:4]}...{token[-4:]} ({len(token)} chars)"


def find_missing_secrets(
    required: dict[str, list[str]], secrets: dict[str, dict[str, str]]
) -> dict[str, list[str]]:
    """Compare required keys against present values; return ``{env: [missing]}``."""
    missing: dict[str, list[str]] = {}
    for env, keys in required.items():
        present = secrets.get(env, {})
        absent = [k for k in keys if not present.get(k)]
        if absent:
            missing[env] = absent
    return missing
