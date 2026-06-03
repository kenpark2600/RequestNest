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
