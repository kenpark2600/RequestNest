# Publishing RequestNest to PyPI

A step-by-step runbook. There are two paths: the **automated** one (recommended —
a GitHub Release publishes for you via Trusted Publishing) and a **manual** one
(useful for the very first upload and for rehearsing on TestPyPI).

> ⚠️ **Versions are permanent.** You can never re-upload a version number to PyPI,
> even after deleting it. Bump `version` in `pyproject.toml` for every release.

---

## One-time setup

1. **Confirm the name is free.** Visit <https://pypi.org/project/requestnest/>.
   A 404 means it's available. If it's taken, change `name` in `pyproject.toml`.
2. **Create accounts** on [pypi.org](https://pypi.org) and
   [test.pypi.org](https://test.pypi.org). Enable 2FA (required).
3. **Set up Trusted Publishing** (no tokens needed) on PyPI:
   - PyPI → your project (or "Publishing" → "Add a pending publisher" if the
     project doesn't exist yet) → add a **GitHub** publisher:
     - Owner: `kenpark2600` · Repository: `RequestNest`
     - Workflow filename: `publish.yml`
     - Environment: `pypi`
   - This authorizes the workflow in `.github/workflows/publish.yml` to publish.

---

## Automated release (recommended)

1. Make sure `main` is green (CI passes) and `version` is bumped.
2. Tag and push:
   ```sh
   git tag v0.1.0
   git push origin v0.1.0
   ```
3. On GitHub: **Releases → Draft a new release** → choose the tag → write notes →
   **Publish release**.
4. The `Publish to PyPI` workflow builds, checks, and uploads automatically.
5. Verify: `pip install requestnest` (give the index a minute to update).

---

## Manual publish (first time / rehearsal)

```sh
pip install build twine

# 1. Build distributions into dist/
python -m build              # -> dist/requestnest-X.Y.Z.tar.gz + .whl

# 2. Sanity-check metadata
twine check dist/*

# 3. Rehearse on TestPyPI
twine upload --repository testpypi dist/*
pip install -i https://test.pypi.org/simple/ requestnest   # confirm it installs

# 4. The real upload
twine upload dist/*
```

For manual uploads you authenticate with a **PyPI API token** (Account settings →
API tokens). Use `__token__` as the username and the token as the password, or
put it in `~/.pypirc`.

---

## Release checklist

- [ ] `version` bumped in `pyproject.toml` (and CHANGELOG updated, if you keep one).
- [ ] CI green on `main`.
- [ ] `python -m build` succeeds; `twine check dist/*` passes.
- [ ] (First release) name confirmed free + Trusted Publisher configured.
- [ ] Tag pushed and GitHub Release published.
- [ ] `pip install requestnest` works from a clean environment.
