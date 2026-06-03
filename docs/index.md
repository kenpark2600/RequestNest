# RequestNest

**Keep Postman. Skip the per-seat cost. Collaborate through git.**

RequestNest lets a team share Postman collections and environments **for free** by
using a git repo as the shared workspace — so you don't have to migrate to a
different API client *or* pay for a Postman team plan.

Each teammate keeps their own free Postman account. RequestNest syncs each
person's **personal Postman workspace** (via the Postman REST API) with a
**shared git repo** — git is the source of truth, and secrets never land in it.

```
shared git repo  <->  your personal Postman workspace
```

## Why it exists

As of **March 2026**, Postman's free plan is single-user with no shared
workspaces, and team collaboration runs **$23/user/month** (monthly; $19 annual).
Postman's own native git sync **requires a paid team workspace** — it doesn't work
with the personal workspaces free users have. The alternative is migrating to a
git-native client (Bruno, Apidog, Requestly), which means leaving Postman behind.

RequestNest is for teams that want to **stay on Postman**: publish your collections
to git, let teammates import them into their own workspaces — no migration, no paid
seats — and it **sanitizes secrets automatically** so tokens never reach the repo.

See the [Market analysis](market-analysis.md) for the full picture.

## How it works

RequestNest is a Python 3.10+ CLI (`click` for commands, `httpx` for the Postman
REST API, `pyyaml`, and `rich` for output) that treats a git repo as the shared
workspace. A publisher runs `init` then `push` to share a collection; a teammate
runs `setup` to import it into their own workspace. The committed repo is the
source of truth, and the CLI drives git for you (auto commit/pull/push, gated by
config and a `--no-git` flag), with `diff` and `--dry-run` previews so nothing
changes before you see it.

Behind the scenes:

- **Sync model** — each command talks to `api.getpostman.com` with your personal
  `PMAK-` key, syncing your personal Postman workspace ⇄ the repo. Free Postman
  accounts can use the API against their own workspace, which is the whole basis
  for the tool.
- **Clean diffs** — before anything is written, collections and environments run
  through a normalization pass: volatile `id`/timestamp fields are stripped,
  object keys are deterministically ordered, and array order is preserved. Diffs
  stay readable and commits don't churn.
- **Secret safety** — any Postman variable marked `type: secret` (plus an
  optional config override list) is replaced with a `{{placeholder}}` in the
  committed JSON; the real value lives only in a gitignored local file and is
  restored on `pull`. A pre-push safety scan additionally blocks anything
  token-shaped (PMAK-, AWS keys, JWTs, long hex) that wasn't marked, so
  credentials never reach the repo.
- **Per-account identity** — Postman resource UIDs differ per account, so the
  committed config is UID-free (logical names only) and each person's
  name→UID mapping is kept in gitignored local state.
- **Architecture** — git is driven via subprocess (no libgit dependency), and
  the orchestration core is UI-agnostic, so a TUI or web UI could be layered on
  later. See the [project brief](project-brief.md) for the full design.

## Install

```sh
pip install requestnest        # or: pipx install requestnest
requestnest --version
```

If `requestnest` isn't found afterward, pip's scripts folder isn't on your
`PATH` (common on Windows) — run it as a module instead, which needs no PATH
change:

```sh
python -m requestnest --version
```

See the [README install notes](https://github.com/kenpark2600/RequestNest#install)
for PATH and virtualenv tips.

You'll need a Postman API key (Postman → Settings → API keys). Provide it when
`init`/`setup` prompts, or set the `REQUESTNEST_API_KEY` environment variable:

PowerShell:

```powershell
$env:REQUESTNEST_API_KEY = "PMAK-..."
```

Bash / Zsh:

```bash
export REQUESTNEST_API_KEY="PMAK-..."
```

## Quickstart

**Publisher — share collections you built in Postman:**

```sh
requestnest init      # pick which collections/environments to track
requestnest push      # sanitize secrets, write JSON, commit & push
```

**Consumer — use collections a teammate shared:**

```sh
requestnest setup     # import into your workspace + prompt for secrets
```

**Day to day:** `pull` to receive, edit in Postman, `diff` to preview, `push` to
share. Git is handled for you.

## Learn more

- [Project brief](project-brief.md) — design and architecture
- [Manual test checklist](manual-test-checklist.md) — hands-on walkthrough
- [Publishing](publishing.md) — releasing to PyPI
- [Source on GitHub](https://github.com/kenpark2600/RequestNest)
