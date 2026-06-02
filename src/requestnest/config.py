"""Config, local state, and secrets file handling.

Three layers, mirroring the per-account-UID split in the plan:

* ``.requestnest.yaml`` — committed. *What* to track + secret policy + git
  settings. UID-free and shareable.
* ``.requestnest.state.yaml`` — gitignored. *Personal*: API key + this user's
  logical-name -> workspace-UID mappings.
* ``.requestnest.secrets.yaml`` — gitignored. Secret values, namespaced by
  environment.

Plus a generated, committable ``.requestnest.secrets.example.yaml`` listing the
required secret *keys* (no values) so newcomers know what to supply.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

CONFIG_FILENAME = ".requestnest.yaml"
STATE_FILENAME = ".requestnest.state.yaml"
SECRETS_FILENAME = ".requestnest.secrets.yaml"
SECRETS_EXAMPLE_FILENAME = ".requestnest.secrets.example.yaml"

COLLECTIONS_DIR = "collections"
ENVIRONMENTS_DIR = "environments"

API_KEY_ENV_VAR = "REQUESTNEST_API_KEY"

#: Local files that must never be committed. ``init``/``push`` enforce this.
GITIGNORED_FILES = (STATE_FILENAME, SECRETS_FILENAME)

CONFIG_VERSION = 1


class ConfigError(Exception):
    """Raised when a config/state/secrets file is missing or malformed."""


class ConfigNotFoundError(ConfigError):
    """Raised when the committed ``.requestnest.yaml`` does not exist."""


# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #


@dataclass
class Collection:
    name: str
    path: str


@dataclass
class Environment:
    name: str
    path: str
    secrets: list[str] = field(default_factory=list)


@dataclass
class GitConfig:
    remote: str = "origin"
    branch: str = "main"
    auto_commit: bool = True
    auto_push: bool = True
    auto_pull: bool = True


@dataclass
class Config:
    version: int = CONFIG_VERSION
    collections: list[Collection] = field(default_factory=list)
    environments: list[Environment] = field(default_factory=list)
    git: GitConfig = field(default_factory=GitConfig)


@dataclass
class LocalState:
    """Personal, gitignored state."""

    api_key: str | None = None
    workspace_id: str | None = None
    # {"collections": {name: uid}, "environments": {name: uid}}
    mappings: dict[str, dict[str, str]] = field(
        default_factory=lambda: {"collections": {}, "environments": {}}
    )

    def uid_for(self, kind: str, name: str) -> str | None:
        return self.mappings.get(kind, {}).get(name)

    def set_uid(self, kind: str, name: str, uid: str) -> None:
        self.mappings.setdefault(kind, {})[name] = uid


# Secrets are a plain ``{env_name: {key: value}}`` mapping; no dataclass needed.
Secrets = dict[str, dict[str, str]]


# --------------------------------------------------------------------------- #
# Path helpers
# --------------------------------------------------------------------------- #


def config_path(root: Path) -> Path:
    return root / CONFIG_FILENAME


def state_path(root: Path) -> Path:
    return root / STATE_FILENAME


def secrets_path(root: Path) -> Path:
    return root / SECRETS_FILENAME


def secrets_example_path(root: Path) -> Path:
    return root / SECRETS_EXAMPLE_FILENAME


def default_collection_path(name: str) -> str:
    return f"{COLLECTIONS_DIR}/{name}.json"


def default_environment_path(name: str) -> str:
    return f"{ENVIRONMENTS_DIR}/{name}.json"


def config_exists(root: Path) -> bool:
    return config_path(root).exists()


# --------------------------------------------------------------------------- #
# Load / save
# --------------------------------------------------------------------------- #


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:  # pragma: no cover - defensive
        raise ConfigError(f"{path.name} is not valid YAML: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"{path.name} must contain a YAML mapping at the top level.")
    return data


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    text = yaml.safe_dump(data, sort_keys=False, default_flow_style=False, allow_unicode=True)
    path.write_text(text, encoding="utf-8")


def load_config(root: Path) -> Config:
    path = config_path(root)
    if not path.exists():
        raise ConfigNotFoundError(
            f"No {CONFIG_FILENAME} found in {root}. Run `requestnest init` first."
        )
    data = _read_yaml(path)

    version = data.get("version", CONFIG_VERSION)
    if version != CONFIG_VERSION:
        raise ConfigError(f"Unsupported config version {version!r} (expected {CONFIG_VERSION}).")

    collections = [_parse_collection(item) for item in data.get("collections", []) or []]
    environments = [_parse_environment(item) for item in data.get("environments", []) or []]
    git = _parse_git(data.get("git", {}) or {})
    return Config(version=version, collections=collections, environments=environments, git=git)


def _parse_collection(item: Any) -> Collection:
    if not isinstance(item, dict) or "name" not in item:
        raise ConfigError(f"Invalid collection entry: {item!r} (needs at least a 'name').")
    name = str(item["name"])
    return Collection(name=name, path=str(item.get("path") or default_collection_path(name)))


def _parse_environment(item: Any) -> Environment:
    if not isinstance(item, dict) or "name" not in item:
        raise ConfigError(f"Invalid environment entry: {item!r} (needs at least a 'name').")
    name = str(item["name"])
    secrets = [str(s) for s in (item.get("secrets") or [])]
    return Environment(
        name=name,
        path=str(item.get("path") or default_environment_path(name)),
        secrets=secrets,
    )


def _parse_git(data: dict[str, Any]) -> GitConfig:
    defaults = GitConfig()
    return GitConfig(
        remote=str(data.get("remote", defaults.remote)),
        branch=str(data.get("branch", defaults.branch)),
        auto_commit=bool(data.get("auto_commit", defaults.auto_commit)),
        auto_push=bool(data.get("auto_push", defaults.auto_push)),
        auto_pull=bool(data.get("auto_pull", defaults.auto_pull)),
    )


def save_config(root: Path, config: Config) -> None:
    data: dict[str, Any] = {
        "version": config.version,
        "collections": [{"name": c.name, "path": c.path} for c in config.collections],
        "environments": [
            {"name": e.name, "path": e.path, **({"secrets": e.secrets} if e.secrets else {})}
            for e in config.environments
        ],
        "git": {
            "remote": config.git.remote,
            "branch": config.git.branch,
            "auto_commit": config.git.auto_commit,
            "auto_push": config.git.auto_push,
            "auto_pull": config.git.auto_pull,
        },
    }
    _write_yaml(config_path(root), data)


def load_state(root: Path) -> LocalState:
    path = state_path(root)
    if not path.exists():
        return LocalState()
    data = _read_yaml(path)
    mappings = data.get("mappings") or {}
    mappings.setdefault("collections", {})
    mappings.setdefault("environments", {})
    return LocalState(
        api_key=data.get("api_key"),
        workspace_id=data.get("workspace_id"),
        mappings={
            "collections": dict(mappings.get("collections") or {}),
            "environments": dict(mappings.get("environments") or {}),
        },
    )


def save_state(root: Path, state: LocalState) -> None:
    data: dict[str, Any] = {}
    if state.api_key is not None:
        data["api_key"] = state.api_key
    if state.workspace_id is not None:
        data["workspace_id"] = state.workspace_id
    data["mappings"] = state.mappings
    _write_yaml(state_path(root), data)


def load_secrets(root: Path) -> Secrets:
    path = secrets_path(root)
    if not path.exists():
        return {}
    data = _read_yaml(path)
    return {
        str(env): {str(k): str(v) for k, v in (values or {}).items()}
        for env, values in data.items()
    }


def save_secrets(root: Path, secrets: Secrets) -> None:
    _write_yaml(secrets_path(root), {env: values for env, values in secrets.items()})


def resolve_api_key(state: LocalState, env: dict[str, str] | None = None) -> str | None:
    """Return the API key, with the ``REQUESTNEST_API_KEY`` env var taking precedence."""
    import os

    source = env if env is not None else os.environ
    return source.get(API_KEY_ENV_VAR) or state.api_key


# --------------------------------------------------------------------------- #
# Secrets scaffold (committable example with keys only, no values)
# --------------------------------------------------------------------------- #


def secrets_example_text(required: dict[str, list[str]]) -> str:
    """Render the secrets template: every required key mapped to an empty value."""
    header = (
        "# RequestNest secrets template (committable — KEYS ONLY, no values).\n"
        "# Copy to .requestnest.secrets.yaml and fill in real values (from 1Password).\n"
    )
    body = {env: {key: "" for key in sorted(keys)} for env, keys in sorted(required.items())}
    dumped = yaml.safe_dump(body, sort_keys=False, default_flow_style=False, allow_unicode=True)
    return header + dumped


def write_secrets_example(root: Path, required: dict[str, list[str]]) -> None:
    secrets_example_path(root).write_text(secrets_example_text(required), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Gitignore guard
# --------------------------------------------------------------------------- #


def gitignore_path(root: Path) -> Path:
    return root / ".gitignore"


def missing_gitignore_entries(root: Path) -> list[str]:
    """Return which of :data:`GITIGNORED_FILES` are not covered by .gitignore."""
    path = gitignore_path(root)
    if not path.exists():
        return list(GITIGNORED_FILES)
    lines = {line.strip() for line in path.read_text(encoding="utf-8").splitlines()}
    return [f for f in GITIGNORED_FILES if f not in lines and f"/{f}" not in lines]


def ensure_gitignored(root: Path) -> list[str]:
    """Append any missing local-secret files to .gitignore. Returns what was added."""
    missing = missing_gitignore_entries(root)
    if not missing:
        return []
    path = gitignore_path(root)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    block = "\n# RequestNest local files (never commit secrets)\n" + "\n".join(missing) + "\n"
    prefix = "" if existing.endswith("\n") or not existing else "\n"
    path.write_text(existing + prefix + block, encoding="utf-8")
    return missing
