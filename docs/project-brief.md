# Project Brief — RequestNest

> Status: **MVP implemented** (2026-06-02). Captures the design decisions from
> brainstorming; see [../README.md](../README.md) for usage. Update as decisions evolve.

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

## CLI commands (designed so far)
- `sync push` — read local Postman workspace via API → write JSON to git repo →
  commit/push.
- `sync pull` — fetch latest from git → import into personal Postman workspace via
  API.
- `sync diff` — normalized, human-readable diff between local workspace and the
  git version (raw JSON diffs are too noisy).

## Config
A `.postman-sync.yaml` at the repo root defines which collections and environments
to track. **Schema not yet designed** — this is the immediate next task.

## Stack
- **Recommended:** Python + [`click`](https://click.palletsprojects.com) (CLI) +
  [`httpx`](https://www.python-httpx.org) (HTTP). Chosen for easy contribution,
  no build step.
- **Alternative:** Node/TypeScript.

## Most important design decision — secrets handling (the main footgun)
Postman environments frequently contain API keys/tokens. Two-layer approach:
1. **Sanitized env files committed to git** — secret values replaced with empty
   strings or `{{SECRET_NAME}}` placeholders.
2. **Local secret files (.gitignored)** merged in at import time, like `.env`.

> This must be **fully designed before implementation begins.**

## Postman free-plan capabilities (already researched)
- **Export/import:** Collections & environments export as JSON (v2.1) — diff-friendly.
- **Postman REST API:** Available on free plan w/ personal API key, but only reaches
  *your personal* workspace.
- **Newman:** CI runner only — not useful for syncing.
- **Postman CLI:** Cloud-run-focused — not file-sync-focused.

## Where we left off
Overall design is agreed. Immediate next steps:
1. Sketch the `.postman-sync.yaml` config schema.
2. Finalize the CLI command structure.
…before writing any code.

## Open questions
- **Naming:** repo/README is "RequestNest"; recap calls the tool "postman-sync".
  Reconcile product name vs. CLI command vs. package name.
