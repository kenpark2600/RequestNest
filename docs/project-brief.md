# Project Brief — RequestNest

> Status: **MVP implemented** (2026-06-02). Captures the design decisions from
> brainstorming; see the [home page](index.md) for usage. Update as decisions evolve.

## Implementation status (2026-06-02)

The naming question is resolved: **RequestNest** throughout (command `requestnest`,
alias `rn`, config `.requestnest.yaml`). The full MVP is built and tested
(`pytest`, `ruff`):

- **Modules** (`src/requestnest/`): `cli.py` (Click, presentation only),
  `ui.py` (UI protocol + `RichUI`), `context.py`, `config.py`, `normalize.py`,
  `postman.py`, `secrets.py`, `semantic_diff.py`, `conflict.py`, `gitops.py`,
  `sync.py` (UI-agnostic core). Layering rule holds: logic in `sync.py`, the
  user is reached only via the `UI` protocol — a TUI/web UI stays a thin layer.
- **Commands**: `init` (fresh + join), `setup`, `push`, `pull`, `diff`, `list`,
  `status`, `verify`, `secrets check`. Git is driven by default, gated by
  `config.git.auto_*` + a `--no-git` flag; `--dry-run` previews everywhere.
- **Secret detection** primary signal is Postman's native `type: "secret"` flag
  (not just a declared list), backed by the config override list and the
  `safety_scan` token guard. Distribution = scaffolding + checks (manual via
  1Password); 1Password-reference and Slack-webhook bundles remain deferred.
- **Robustness note**: `ui.py` reconfigures stdout/stderr to UTF-8 and uses
  ASCII status markers so output never crashes on legacy Windows (cp1252) consoles.

## One-liner
A CLI tool that lets a team share Postman collections and environments for free,
using **git as the shared workspace** instead of a paid Postman team plan.

## Problem
Postman repriced team accounts out of budget. The free plan has **no shared
workspaces**. But free Postman accounts *can*:
- generate a personal **API key**, and
- access their **personal workspace** via the Postman REST API.

So every team member has a programmable personal workspace even on the free tier.

## Core concept
**Git is the source of truth.** Each member keeps their own free Postman account.
The CLI syncs between each person's personal Postman workspace (via the Postman
API) and a shared git repo.

```
shared git repo  ⇄  each person's personal Postman workspace
```

Everyone treats their **personal Postman workspace as the working copy**. Editing
exported JSON directly causes divergence — the tool only works if workflow
discipline matches.

## CLI commands
Command `requestnest` (alias `rn`):
- `init` — set up a repo (fresh) or join an existing one; validates the API key,
  selects workspace resources, writes config + local state, enforces `.gitignore`.
- `setup` — guided one-command consumer onboarding (join + pull + secret prompts).
- `push` — workspace → normalized, sanitized JSON in git (then auto commit/push).
- `pull` — git → desanitized import back into your personal workspace.
- `diff` — normalized, human-readable semantic diff between workspace and git.
- `list` / `status` — tracked resources, import state, secret presence, divergence.
- `verify` — CI/pre-commit check that committed JSON is normalized and secret-free.
- `secrets check` — confirm all required secret values are present locally.

Git is driven by default (gated by `config.git.auto_*` + a global `--no-git`);
`--dry-run` previews everywhere.

## Config
A **`.requestnest.yaml`** at the repo root (committed, UID-free) defines which
collections and environments to track plus the secret policy. Per-person state
(API key, logical-name→workspace-UID map) and real secret values live in
gitignored local files (`.requestnest.state.yaml`, `.requestnest.secrets.yaml`).
The schema is implemented; see the [home page](index.md) for the current shape.

## Stack
- **Recommended:** Python + [`click`](https://click.palletsprojects.com) (CLI) +
  [`httpx`](https://www.python-httpx.org) (HTTP). Chosen for easy contribution,
  no build step.
- **Alternative:** Node/TypeScript.

## Most important design decision — secrets handling (the main footgun)
Postman environments frequently contain API keys/tokens. Two-layer approach
(implemented):
1. **Sanitized env files committed to git** — secret values replaced with
   `{{SECRET_NAME}}` placeholders, with `type: secret` preserved.
2. **Local secret files (.gitignored)** merged back in on `pull`/import.

Detection is three layers, primary signal first: Postman's native `type: "secret"`
flag, the config override list, and a pre-push `safety_scan` that blocks
token-shaped values (`PMAK-`, `AKIA`, JWT, long hex/base64). Distribution in v1
is scaffolding + checks (real values shared out-of-band via the team's existing
secret manager); 1Password-reference and Slack-bundle backends remain deferred.

## Postman free-plan capabilities (already researched)
- **Export/import:** Collections & environments export as JSON (v2.1) — diff-friendly.
- **Postman REST API:** Available on free plan w/ personal API key, but only reaches
  *your personal* workspace.
- **Newman:** CI runner only — not useful for syncing.
- **Postman CLI:** Cloud-run-focused — not file-sync-focused.

## Current status
The MVP is built and tested, the repo is public at
[github.com/kenpark2600/RequestNest](https://github.com/kenpark2600/RequestNest),
and these docs are live at [requestnest.dev](https://requestnest.dev). Remaining
before a public release: manual end-to-end testing, company sign-off, then the
first PyPI publish (`pip install requestnest`).

## Deferred / future
- Secret backends beyond the local file: 1Password CLI reference, Slack-webhook
  encrypted-bundle distribution.
- TUI / local web UI (`requestnest ui`) — the core is UI-agnostic to allow it.
- `watch` (live auto-sync), semantic `log <name>`, collection lint,
  Newman/CI environment export.
- Conflict *resolution* beyond detect-and-warn (3-way merge).
