"""UI-agnostic orchestration core.

Each public function implements one CLI command end-to-end. The user is reached
only through ``app.ui`` (the :class:`~requestnest.ui.UI` protocol) and git only
through :mod:`requestnest.gitops`, so the same logic can back a TUI / web UI.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import config as cfg
from . import secrets as secretslib
from . import semantic_diff
from .conflict import assess
from .context import AppContext
from .gitops import GitRepo
from .normalize import dumps, normalize, normalized_obj
from .postman import PostmanClient


class SyncError(Exception):
    """A user-facing error in a sync operation (mapped to a clean CLI message)."""


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slug(name: str) -> str:
    return _SLUG_RE.sub("-", name.strip().lower()).strip("-") or "unnamed"


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #


def _require_client(app: AppContext, state: cfg.LocalState) -> PostmanClient:
    key = cfg.resolve_api_key(state)
    if not key:
        raise SyncError("No Postman API key. Run `requestnest init` or set REQUESTNEST_API_KEY.")
    return PostmanClient(key)


def _open_git(app: AppContext) -> GitRepo | None:
    if app.no_git:
        return None
    repo = GitRepo(app.repo_root)
    return repo if repo.is_repo() else None


def _targets(
    config: cfg.Config, names: tuple[str, ...]
) -> tuple[list[cfg.Collection], list[cfg.Environment]]:
    if not names:
        return list(config.collections), list(config.environments)
    wanted = set(names)
    cols = [c for c in config.collections if c.name in wanted]
    envs = [e for e in config.environments if e.name in wanted]
    found = {c.name for c in cols} | {e.name for e in envs}
    unknown = wanted - found
    if unknown:
        raise SyncError(f"Unknown resource(s): {', '.join(sorted(unknown))}")
    return cols, envs


def _read_committed(root: Path, rel_path: str) -> dict[str, Any] | None:
    path = root / rel_path
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_committed(root: Path, rel_path: str, obj: dict[str, Any]) -> None:
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(normalize(obj), encoding="utf-8")


def _required_secret_keys(root: Path, config: cfg.Config) -> dict[str, list[str]]:
    """Secret keys each environment needs, read from the committed (sanitized) JSON."""
    required: dict[str, list[str]] = {}
    for env in config.environments:
        obj = _read_committed(root, env.path)
        if obj is None:
            continue
        keys = secretslib.needed_secret_keys(obj, env.secrets)
        if keys:
            required[env.name] = keys
    return required


# --------------------------------------------------------------------------- #
# init / setup
# --------------------------------------------------------------------------- #


def init(app: AppContext) -> None:
    root = app.repo_root
    if not GitRepo(root).is_repo():
        app.ui.warn("This directory is not a git repository; git sync will be unavailable.")
    if cfg.config_exists(root):
        _init_join(app)
    else:
        _init_fresh(app)


def _authenticate(app: AppContext, state: cfg.LocalState) -> PostmanClient:
    """Resolve or prompt for an API key and validate it."""
    key = cfg.resolve_api_key(state)
    if not key:
        key = app.ui.prompt("Postman API key", password=True).strip()
    client = PostmanClient(key)
    user = client.me()
    app.ui.success(f"Authenticated as Postman user {user.get('username') or user.get('id')}.")
    state.api_key = key
    return client


def _init_fresh(app: AppContext) -> None:
    root = app.repo_root
    state = cfg.load_state(root)
    client = _authenticate(app, state)

    collections = client.list_collections()
    environments = client.list_environments()

    chosen_cols = app.ui.select(
        "Collections to track",
        [(c["uid"], c.get("name", c["uid"])) for c in collections],
    )
    chosen_envs = app.ui.select(
        "Environments to track",
        [(e["uid"], e.get("name", e["uid"])) for e in environments],
    )

    config = cfg.Config()
    by_uid_c = {c["uid"]: c for c in collections}
    by_uid_e = {e["uid"]: e for e in environments}

    for uid in chosen_cols:
        name = slug(by_uid_c[uid].get("name", uid))
        config.collections.append(cfg.Collection(name=name, path=cfg.default_collection_path(name)))
        state.set_uid("collections", name, uid)
    for uid in chosen_envs:
        name = slug(by_uid_e[uid].get("name", uid))
        config.environments.append(
            cfg.Environment(name=name, path=cfg.default_environment_path(name))
        )
        state.set_uid("environments", name, uid)

    cfg.save_config(root, config)
    cfg.save_state(root, state)
    added = cfg.ensure_gitignored(root)
    if added:
        app.ui.detail(f"Added to .gitignore: {', '.join(added)}")
    app.ui.success(
        f"Initialized RequestNest: {len(config.collections)} collection(s), "
        f"{len(config.environments)} environment(s). Run `requestnest push` to publish."
    )


def _init_join(app: AppContext) -> None:
    root = app.repo_root
    config = cfg.load_config(root)
    state = cfg.load_state(root)
    client = _authenticate(app, state)

    existing_c = {slug(c.get("name", "")): c["uid"] for c in client.list_collections()}
    existing_e = {slug(e.get("name", "")): e["uid"] for e in client.list_environments()}

    mapped = 0
    for c in config.collections:
        if c.name in existing_c:
            state.set_uid("collections", c.name, existing_c[c.name])
            mapped += 1
    for e in config.environments:
        if e.name in existing_e:
            state.set_uid("environments", e.name, existing_e[e.name])
            mapped += 1

    cfg.save_state(root, state)
    cfg.ensure_gitignored(root)
    app.ui.success(
        f"Joined existing config: {mapped} resource(s) matched in your workspace; "
        "the rest will be created on `requestnest pull`."
    )


def setup(app: AppContext) -> None:
    root = app.repo_root
    if not cfg.config_exists(root):
        raise SyncError(
            "No .requestnest.yaml here. Clone the shared repo first, or run "
            "`requestnest init` to create one."
        )
    app.ui.info("Setting up RequestNest for this shared repo...")
    _init_join(app)
    pull(app, names=(), prompt_secrets=True)
    app.ui.success("Setup complete. You're ready to work.")


# --------------------------------------------------------------------------- #
# push
# --------------------------------------------------------------------------- #


def push(
    app: AppContext,
    names: tuple[str, ...],
    allow_unmarked_secrets: bool = False,
    force: bool = False,
) -> None:
    root = app.repo_root
    config = cfg.load_config(root)
    state = cfg.load_state(root)
    secrets = cfg.load_secrets(root)
    client = _require_client(app, state)
    cols, envs = _targets(config, names)

    planned: list[tuple[str, dict[str, Any]]] = []  # (rel_path, stripped_obj)
    findings: list[tuple[str, Any]] = []

    for c in cols:
        uid = state.uid_for("collections", c.name)
        if not uid:
            raise SyncError(f"Collection '{c.name}' is not mapped to your workspace. Run init.")
        app.ui.detail(f"Fetching collection {c.name}...")
        obj = normalized_obj(client.get_collection(uid))
        planned.append((c.path, obj))
        findings += [(c.path, f) for f in secretslib.safety_scan(obj)]

    for e in envs:
        uid = state.uid_for("environments", e.name)
        if not uid:
            raise SyncError(f"Environment '{e.name}' is not mapped to your workspace. Run init.")
        app.ui.detail(f"Fetching environment {e.name}...")
        sanitized, captured = secretslib.sanitize_environment(
            client.get_environment(uid), e.secrets
        )
        obj = normalized_obj(sanitized)
        planned.append((e.path, obj))
        findings += [(e.path, f) for f in secretslib.safety_scan(obj)]
        if captured:
            secrets.setdefault(e.name, {}).update(captured)

    if findings and not allow_unmarked_secrets:
        for path, finding in findings:
            app.ui.error(
                f"{path}: token-shaped value at {finding.location} "
                f"[{finding.pattern}: {finding.preview}]"
            )
        raise SyncError(
            "Refusing to push: unmarked secret-shaped values found. Mark them as "
            "'secret' in Postman, add them to the env's `secrets:` list, or re-run "
            "with --allow-unmarked-secrets."
        )

    pushing_paths = [p for p, _ in planned]
    _check_conflicts(app, config, pushing_paths, force)

    if app.dry_run:
        _show_push_dryrun(app, root, cols, envs, planned)
        return

    for rel_path, obj in planned:
        _write_committed(root, rel_path, obj)
    cfg.save_secrets(root, secrets)
    required = _required_secret_keys(root, config)
    cfg.write_secrets_example(root, required)
    cfg.save_state(root, state)

    app.ui.success(f"Wrote {len(planned)} resource file(s).")
    _commit_and_push(app, config, pushing_paths)
    _report_secret_handoff(app, required, secrets)


def _check_conflicts(
    app: AppContext, config: cfg.Config, pushing_paths: list[str], force: bool
) -> None:
    repo = _open_git(app)
    if repo is None or not repo.has_remote(config.git.remote):
        return
    app.ui.detail("Checking remote for conflicting changes...")
    repo.fetch(config.git.remote)
    behind = repo.behind_count(config.git.remote, config.git.branch)
    changed = repo.upstream_changed_files(config.git.remote, config.git.branch)
    report = assess(behind, changed, pushing_paths)
    if report.has_conflict and not force:
        raise SyncError(report.message())
    if report.behind:
        app.ui.warn(report.message())


def _commit_and_push(app: AppContext, config: cfg.Config, pushing_paths: list[str]) -> None:
    repo = _open_git(app)
    if repo is None:
        return
    add_paths = [
        p
        for p in [*pushing_paths, cfg.SECRETS_EXAMPLE_FILENAME, cfg.CONFIG_FILENAME]
        if (app.repo_root / p).exists()
    ]
    repo.add(add_paths)
    if not config.git.auto_commit:
        app.ui.info("Staged changes (auto_commit is off). Commit when ready.")
        return
    committed = repo.commit(f"requestnest: push {len(pushing_paths)} resource(s)")
    if not committed:
        app.ui.info("No changes to commit.")
        return
    app.ui.success("Committed.")
    if config.git.auto_push and repo.has_remote(config.git.remote):
        repo.push(config.git.remote, config.git.branch)
        app.ui.success(f"Pushed to {config.git.remote}/{config.git.branch}.")


def _report_secret_handoff(
    app: AppContext, required: dict[str, list[str]], secrets: dict[str, dict[str, str]]
) -> None:
    if not required:
        return
    app.ui.warn(
        "Secrets are NOT committed to git. Share these values with teammates "
        "securely (e.g. 1Password):"
    )
    for env, keys in sorted(required.items()):
        app.ui.info(f"  {env}: {', '.join(sorted(keys))}")


def _show_push_dryrun(
    app: AppContext,
    root: Path,
    cols: list[cfg.Collection],
    envs: list[cfg.Environment],
    planned: list[tuple[str, dict[str, Any]]],
) -> None:
    app.ui.info("[dry-run] No files written, no commits made. Planned changes:")
    by_path = dict(planned)
    for c in cols:
        old = _read_committed(root, c.path) or {}
        app.ui.show_diff(semantic_diff.diff_collections(old, by_path[c.path], label=c.name))
    for e in envs:
        old = _read_committed(root, e.path) or {}
        app.ui.show_diff(semantic_diff.diff_environments(old, by_path[e.path], label=e.name))


# --------------------------------------------------------------------------- #
# pull
# --------------------------------------------------------------------------- #


def pull(app: AppContext, names: tuple[str, ...], prompt_secrets: bool = False) -> None:
    root = app.repo_root
    config = cfg.load_config(root)
    state = cfg.load_state(root)
    secrets = cfg.load_secrets(root)
    client = _require_client(app, state)
    cols, envs = _targets(config, names)

    if not app.dry_run:
        _git_pull(app, config)

    imported = 0
    all_missing: dict[str, list[str]] = {}

    for c in cols:
        obj = _read_committed(root, c.path)
        if obj is None:
            app.ui.warn(f"Skipping collection '{c.name}': {c.path} not found.")
            continue
        if app.dry_run:
            _show_pull_dryrun_collection(app, client, state, c, obj)
            continue
        _upsert_collection(app, client, state, c, obj)
        imported += 1

    for e in envs:
        obj = _read_committed(root, e.path)
        if obj is None:
            app.ui.warn(f"Skipping environment '{e.name}': {e.path} not found.")
            continue
        restored, missing = secretslib.desanitize_environment(
            obj, secrets.get(e.name, {}), e.secrets
        )
        if missing and prompt_secrets and not app.dry_run:
            for key in missing:
                value = app.ui.prompt(f"Secret value for {e.name}.{key}", password=True).strip()
                if value:
                    secrets.setdefault(e.name, {})[key] = value
            restored, missing = secretslib.desanitize_environment(
                obj, secrets.get(e.name, {}), e.secrets
            )
        if missing:
            all_missing[e.name] = missing
        if app.dry_run:
            _show_pull_dryrun_environment(app, client, state, e, obj)
            continue
        _upsert_environment(app, client, state, e, restored)
        imported += 1

    if app.dry_run:
        app.ui.info("[dry-run] No workspace changes made.")
        return

    cfg.save_state(root, state)
    cfg.save_secrets(root, secrets)
    app.ui.success(f"Imported {imported} resource(s) into your workspace.")
    if all_missing:
        app.ui.warn("Missing secret values (get them from a teammate / 1Password):")
        for env, keys in sorted(all_missing.items()):
            app.ui.info(f"  {env}: {', '.join(keys)}")


def _git_pull(app: AppContext, config: cfg.Config) -> None:
    repo = _open_git(app)
    if repo is None or not config.git.auto_pull or not repo.has_remote(config.git.remote):
        return
    app.ui.detail("git pull...")
    repo.pull(config.git.remote, config.git.branch)


def _upsert_collection(
    app: AppContext, client: PostmanClient, state: cfg.LocalState, c: cfg.Collection, obj: dict
) -> None:
    uid = state.uid_for("collections", c.name)
    if uid:
        client.update_collection(uid, obj)
        app.ui.detail(f"Updated collection {c.name}.")
    else:
        created = client.create_collection(obj)
        state.set_uid("collections", c.name, created.get("uid", ""))
        app.ui.detail(f"Created collection {c.name}.")


def _upsert_environment(
    app: AppContext, client: PostmanClient, state: cfg.LocalState, e: cfg.Environment, obj: dict
) -> None:
    uid = state.uid_for("environments", e.name)
    if uid:
        client.update_environment(uid, obj)
        app.ui.detail(f"Updated environment {e.name}.")
    else:
        created = client.create_environment(obj)
        state.set_uid("environments", e.name, created.get("uid", ""))
        app.ui.detail(f"Created environment {e.name}.")


def _show_pull_dryrun_collection(app, client, state, c, file_obj) -> None:
    uid = state.uid_for("collections", c.name)
    live = normalized_obj(client.get_collection(uid)) if uid else {}
    app.ui.show_diff(semantic_diff.diff_collections(live, file_obj, label=f"{c.name} (workspace)"))


def _show_pull_dryrun_environment(app, client, state, e, file_obj) -> None:
    uid = state.uid_for("environments", e.name)
    if uid:
        live, _ = secretslib.sanitize_environment(client.get_environment(uid), e.secrets)
    else:
        live = {}
    app.ui.show_diff(semantic_diff.diff_environments(live, file_obj, label=f"{e.name} (workspace)"))


# --------------------------------------------------------------------------- #
# diff
# --------------------------------------------------------------------------- #


def diff(app: AppContext, names: tuple[str, ...]) -> None:
    root = app.repo_root
    config = cfg.load_config(root)
    state = cfg.load_state(root)
    client = _require_client(app, state)
    cols, envs = _targets(config, names)
    any_output = False

    for c in cols:
        committed = _read_committed(root, c.path)
        uid = state.uid_for("collections", c.name)
        if committed is None and not uid:
            continue
        live = normalized_obj(client.get_collection(uid)) if uid else {}
        app.ui.show_diff(semantic_diff.diff_collections(committed or {}, live, label=c.name))
        any_output = True

    for e in envs:
        committed = _read_committed(root, e.path)
        uid = state.uid_for("environments", e.name)
        if committed is None and not uid:
            continue
        if uid:
            live, _ = secretslib.sanitize_environment(client.get_environment(uid), e.secrets)
        else:
            live = {}
        app.ui.show_diff(semantic_diff.diff_environments(committed or {}, live, label=e.name))
        any_output = True

    if not any_output:
        app.ui.info("Nothing to diff.")


# --------------------------------------------------------------------------- #
# list / status
# --------------------------------------------------------------------------- #


def list_resources(app: AppContext) -> None:
    root = app.repo_root
    config = cfg.load_config(root)
    state = cfg.load_state(root)
    secrets = cfg.load_secrets(root)
    required = _required_secret_keys(root, config)

    rows: list[list[str]] = []
    for c in config.collections:
        imported = "yes" if state.uid_for("collections", c.name) else "no"
        rows.append([c.name, "collection", c.path, imported, "-"])
    for e in config.environments:
        imported = "yes" if state.uid_for("environments", e.name) else "no"
        missing = secretslib.find_missing_secrets({e.name: required.get(e.name, [])}, secrets).get(
            e.name
        )
        secrets_state = "missing" if missing else ("ok" if required.get(e.name) else "none")
        rows.append([e.name, "environment", e.path, imported, secrets_state])

    if not rows:
        app.ui.info("No tracked resources. Run `requestnest init`.")
        return
    app.ui.table("Tracked resources", ["name", "kind", "path", "imported", "secrets"], rows)


def status(app: AppContext) -> None:
    root = app.repo_root
    config = cfg.load_config(root)
    secrets = cfg.load_secrets(root)

    missing_ignore = cfg.missing_gitignore_entries(root)
    if missing_ignore:
        app.ui.warn(f"Not gitignored (secrets could leak!): {', '.join(missing_ignore)}")
    else:
        app.ui.success("Local secret files are gitignored.")

    repo = _open_git(app)
    if repo and repo.has_remote(config.git.remote):
        repo.fetch(config.git.remote)
        behind = repo.behind_count(config.git.remote, config.git.branch)
        if behind:
            app.ui.warn(f"Behind {config.git.remote}/{config.git.branch} by {behind} commit(s).")
        else:
            app.ui.success("Up to date with remote.")

    required = _required_secret_keys(root, config)
    missing = secretslib.find_missing_secrets(required, secrets)
    if missing:
        app.ui.warn("Missing secret values:")
        for env, keys in sorted(missing.items()):
            app.ui.info(f"  {env}: {', '.join(keys)}")
    elif required:
        app.ui.success("All required secrets are present locally.")


# --------------------------------------------------------------------------- #
# verify / secrets check
# --------------------------------------------------------------------------- #


def verify(app: AppContext) -> None:
    root = app.repo_root
    config = cfg.load_config(root)
    problems: list[str] = []

    for resource in [*config.collections, *config.environments]:
        path = root / resource.path
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as exc:
            problems.append(f"{resource.path}: invalid JSON ({exc})")
            continue
        if dumps(normalized_obj(obj)) != text:
            problems.append(f"{resource.path}: not normalized (run `requestnest push`)")
        for finding in secretslib.safety_scan(obj):
            problems.append(
                f"{resource.path}: secret-shaped value at {finding.location} [{finding.pattern}]"
            )

    if problems:
        for problem in problems:
            app.ui.error(problem)
        raise SyncError(f"verify failed: {len(problems)} problem(s).")
    app.ui.success("verify passed: all committed JSON is normalized and secret-free.")


def secrets_check(app: AppContext) -> None:
    root = app.repo_root
    config = cfg.load_config(root)
    secrets = cfg.load_secrets(root)
    required = _required_secret_keys(root, config)
    missing = secretslib.find_missing_secrets(required, secrets)
    if missing:
        app.ui.error("Missing required secret values:")
        for env, keys in sorted(missing.items()):
            app.ui.info(f"  {env}: {', '.join(keys)}")
        raise SyncError("secrets check failed.")
    app.ui.success("All required secret values are present.")
