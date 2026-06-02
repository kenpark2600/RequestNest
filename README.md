# RequestNest

Share Postman collections and environments across a team **for free**, using a
git repo as the shared workspace instead of a paid Postman team plan.

Each teammate keeps their own free Postman account. RequestNest syncs each
person's **personal Postman workspace** (via the Postman REST API) with a
**shared git repo** — git is the source of truth, and secrets never land in it.

```
shared git repo  <->  your personal Postman workspace
```

## Why

The Postman free plan has no shared workspaces, but free accounts *can* use a
personal API key against their personal workspace. RequestNest leans on that:
publish your collections to git, and teammates import them into their own
workspaces — no paid seats required.

## Install

```sh
pip install -e ".[dev]"      # from a clone; installs `requestnest` (alias `rn`)
```

You'll need a Postman API key (Postman → Account → API keys). Provide it when
`init`/`setup` prompts, or set `REQUESTNEST_API_KEY`.

## Workflows

### Publisher — share a new collection

```sh
# Build your collection + environment in Postman first. Mark secret variables
# as type "secret" in the Postman UI.
requestnest init      # pick which collections/environments to track
requestnest push      # sanitize secrets, write JSON, commit & push
```

`push` prints which secret *values* to share with teammates out-of-band (e.g.
1Password) — they are never committed to git.

### Consumer — use a shared collection

```sh
git clone <the shared repo> && cd <repo>
requestnest setup     # join config + import into your workspace + prompt for secrets
# ...work the ticket, edit in Postman...
requestnest diff      # preview what changed vs git
requestnest push      # share your fixes back
```

## Commands

| Command | What it does |
|---|---|
| `requestnest init` | Set up tracking (fresh) or join an existing shared config. |
| `requestnest setup` | One-shot consumer onboarding: join + pull + secret prompts. |
| `requestnest push [names...]` | Workspace → git: fetch, sanitize, safety-scan, commit, push. |
| `requestnest pull [names...]` | Git → workspace: pull, restore secrets, import. |
| `requestnest diff [names...]` | Semantic diff between your live workspace and git. |
| `requestnest list` | Tracked resources, whether imported, and secret status. |
| `requestnest status` | Divergence, missing secrets, and the gitignore guard. |
| `requestnest verify` | CI check: committed JSON is normalized and secret-free. |
| `requestnest secrets check` | Verify all required secret values are present locally. |

Global flags: `--no-git` (skip all git), `--dry-run` (preview, no writes/commits),
`-v/--verbose`. `push` also has `--allow-unmarked-secrets` and `--force`.

## How secrets stay safe

1. **Auto-detected** — any Postman variable of type `secret` is sanitized.
2. **Config override** — extra keys can be forced via an environment's `secrets:` list.
3. **Safety net** — `push`/`verify` refuse token-shaped values (PMAK-, AWS keys,
   JWTs, long hex) that aren't marked secret.

Committed values become `{{key}}` placeholders; real values live only in the
gitignored `.requestnest.secrets.yaml` and are restored on `pull`.

## Files

| File | Committed? | Purpose |
|---|---|---|
| `.requestnest.yaml` | yes | What to track + secret policy + git settings. |
| `.requestnest.secrets.example.yaml` | yes | Required secret **keys** (no values) — onboarding scaffold. |
| `collections/*.json`, `environments/*.json` | yes | Normalized, sanitized exports. |
| `.requestnest.state.yaml` | **no** | Your API key + your workspace UID mappings. |
| `.requestnest.secrets.yaml` | **no** | Real secret values. |

## CI / pre-commit

Run `requestnest verify` in CI to keep the repo clean. To block leaks locally:

```sh
cp hooks/pre-commit .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
```

## Development

```sh
pytest          # tests (httpx mocked via respx; git via temp repos)
ruff check .    # lint
```

Architecture: the orchestration core (`sync.py`) is UI-agnostic and talks to the
user only through the `UI` protocol (`ui.py`), so a TUI or web UI can be added
later as a thin layer. See [docs/project-brief.md](docs/project-brief.md).
