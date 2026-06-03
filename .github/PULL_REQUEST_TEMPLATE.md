## What & why

Briefly describe the change and the motivation.

Closes #<issue-number> (if applicable)

## Changes

-

## Checklist

- [ ] `pytest` passes
- [ ] `ruff check .` is clean
- [ ] Added/updated tests for the change
- [ ] Updated docs/README if behavior changed
- [ ] No weakening of secret handling (sanitize-on-push, safety scan, gitignore guard)
- [ ] Logic stays in the core (`sync.py`); `cli.py`/`ui.py` remain a thin layer
