# RequestNest — Manual Test Checklist

A hands-on walkthrough against a **real Postman account** and a **scratch git
repo**. Go through it in order; for each step there's the command, what you
should see, and a **Friction?** line — jot anything that felt clunky, surprising,
or that you had to think about. That's the raw material for making this mindless.

> Tip: keep two terminals open — one for the "publisher" repo dir, one for the
> "consumer" repo dir (Part 3).

---

## Part 0 — Prerequisites (one time)

- [ ] `python --version` shows 3.10 or newer.
- [ ] `git --version` works, and `git config --global user.name` / `user.email` are set.
- [ ] RequestNest installed: `requestnest --version` prints a version.
- [ ] You have a **Postman API key** (`PMAK-…`) from Settings → API keys.
- [ ] (Ideal) A **second free Postman account** + its API key, to play the
      "consumer" in Part 3. *(Fallback: reuse the same account — noted inline.)*
- [ ] An empty **remote** git repo you can push to (GitHub/GitLab), e.g.
      `git@github.com:you/rn-scratch.git`.

**Friction?** ______________________________________________

---

## Part 1 — Publisher: first-time setup & publish

Set up source material in Postman first:

- [ ] In Postman, create **two** collections (e.g. `Orders API`, `Billing API`),
      each with a request or two.
- [ ] Create an environment (e.g. `Staging`) with a normal variable (`base_url`)
      and a **secret** variable — set its **Type = secret** (e.g. `api_token`).

Now wire up the repo:

- [ ] Clone your empty remote and enter it:
      `git clone <remote> rn-pub && cd rn-pub`
- [ ] `requestnest init`
  - Expected: prompts for your API key → "Authenticated as …" → lists your
    collections, then environments → you pick the two collections + `Staging`.
  - Expected: ends with "Initialized RequestNest: 2 collection(s), 1
    environment(s). Run `requestnest push` to publish."
- [ ] Confirm files exist: `.requestnest.yaml`, `.requestnest.state.yaml`, and
      `.gitignore` now lists the local files.

**Friction?** ______________________________________________

- [ ] `requestnest push`
  - Expected: "Wrote 3 resource file(s)." → "Committed." → "Pushed to origin/main."
  - Expected: a **warning** listing secrets to share out-of-band, e.g.
    `staging: api_token`.
- [ ] Inspect the committed environment file:
      `collections/` + `environments/staging.json`.
  - [ ] The real token value is **NOT** present.
  - [ ] `api_token` shows `"{{api_token}}"`.
  - [ ] `.requestnest.secrets.example.yaml` exists and lists `api_token` (no value).
- [ ] Confirm the secret value *was* captured locally (gitignored):
      open `.requestnest.secrets.yaml` → it has the real `api_token`.
- [ ] `git log --oneline` shows the RequestNest commit; `git status` is clean.

**Friction?** ______________________________________________

---

## Part 2 — Safety features (publisher repo)

- [ ] **Dry run**: change a request in Postman, then `requestnest push --dry-run`.
  - Expected: a semantic diff preview; "No files written, no commits made."
  - Expected: `git status` still clean afterwards.
- [ ] **Diff**: `requestnest diff`
  - Expected: human-readable `+ / - / ~` changes (e.g. `~ Orders API/get-order (method)`),
    **not** raw JSON. Secret values never shown.
- [ ] **Verify**: `requestnest verify` → "verify passed".
- [ ] **Unmarked-secret guard**: in Postman, put a fake token that *looks* real
      (e.g. an `Authorization: Bearer AKIAIOSFODNN7EXAMPLE` header) into a
      request, then `requestnest push`.
  - Expected: it **refuses**, points at the location, and writes nothing.
  - [ ] Remove the fake token afterwards.
- [ ] **Secrets check**: `requestnest secrets check` → "All required secret
      values are present." (You have them locally as the publisher.)
- [ ] **List / status**: `requestnest list` and `requestnest status` render
      readable tables/summaries with sensible values.

**Friction?** ______________________________________________

---

## Part 3 — Consumer: onboarding a teammate

Use the **second Postman account's API key** here (or reuse the first — see note).

- [ ] In a new directory, clone the same remote:
      `git clone <remote> rn-consumer && cd rn-consumer`
- [ ] `requestnest setup`
  - Expected: prompts for the (consumer's) API key → "Joined existing config…" →
    imports collections/environments into that workspace → **prompts for the
    missing secret** `staging.api_token`.
  - [ ] Paste the real value (the one the publisher shared) when prompted.
  - Expected: "Imported 3 resource(s)…", then "Setup complete."
- [ ] Open the **consumer's** Postman workspace:
  - [ ] The two collections and `Staging` environment are present.
  - [ ] `Staging.api_token` holds the real value (resolved from your local secrets).

> **Single-account fallback:** if you reused the first account, `setup` will just
> re-map/update the same resources rather than create new ones — still a valid
> check of the join + secret-prompt path, just not a true "fresh workspace".

**Friction?** ______________________________________________

---

## Part 4 — The day-to-day loop & conflict handling

Simulate two people editing.

- [ ] In the **consumer** repo: edit a request in that workspace, then
      `requestnest push`. Confirm it commits & pushes.
- [ ] In the **publisher** repo: `requestnest pull`
  - Expected: it `git pull`s and imports the consumer's change into your workspace.
  - [ ] Verify the change appears in your Postman.
- [ ] **Conflict guard**: now make the publisher and consumer each edit the *same*
      request without pulling, and have the **second** one to `push` hit the guard.
  - Expected: "Remote is ahead … changed resources you're about to overwrite …
    run `requestnest pull` first." Nothing is clobbered.
  - [ ] `requestnest pull`, reconcile in Postman, then `push` succeeds.
  - [ ] (Optional) confirm `push --force` would override the guard.

**Friction?** ______________________________________________

---

## Part 5 — Cleanup

- [ ] Delete the scratch repos (`rn-pub`, `rn-consumer`) and the remote if you made
      it just for this.
- [ ] (Optional) Remove the test collections/environments from your Postman account(s).

---

## Overall impressions

- Biggest friction point: ____________________________________
- Anything you expected the tool to do automatically but it didn't: ____________
- Anything that felt risky / unclear about secrets: ____________
- Naming / wording that confused you: ____________
- Would you trust this for real team use yet? ____________
