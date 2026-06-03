# Contributing to RequestNest

Thanks for your interest! RequestNest is a small, no-build-step Python CLI, so
getting set up is quick.

## Development setup

```sh
git clone https://github.com/kenpark2600/RequestNest && cd RequestNest
python -m venv .venv && . .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Before you open a PR

```sh
pytest          # all tests must pass
ruff check .    # lint must be clean
ruff format .   # (optional) auto-format
```

## Architecture (so changes land in the right place)

The orchestration core (`src/requestnest/sync.py`) is **UI-agnostic**: it reaches
the user only through the `UI` protocol in `ui.py`, and git only through
`gitops.py`. Please keep it that way — put logic in `sync.py`/the core modules,
and keep `cli.py` + `ui.py` as a thin presentation layer. This is what lets a TUI
or web UI be added later without touching the core.

- `cli.py` — Click commands (arg parsing only)
- `ui.py` — `UI` protocol + `RichUI`
- `sync.py` — command logic
- `config.py`, `normalize.py`, `postman.py`, `secrets.py`, `semantic_diff.py`,
  `conflict.py`, `gitops.py` — focused helpers
- `tests/` — `pytest`; Postman API is mocked with `respx`, git with temp repos

## Guidelines

- Add or update tests for any behavior change.
- Match the surrounding style; keep comments purposeful.
- **Never** weaken the secret-handling guarantees (sanitize on push, safety scan,
  gitignore guard) without discussion — secrets must never reach git.
- Keep commits focused; write a clear PR description of the what and why.

## Reporting bugs / proposing features

Use the GitHub issue templates. For anything security-related, see
[SECURITY.md](SECURITY.md) — please don't open a public issue for vulnerabilities.
