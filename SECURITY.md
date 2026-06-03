# Security Policy

RequestNest handles Postman API keys and secret environment values, so we take
security reports seriously.

## Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Instead, report privately via one of:

- GitHub's **[Private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)**
  (repo → **Security** tab → **Report a vulnerability**), or
- email **security@requestnest.dev** with details and reproduction steps.

We'll acknowledge receipt, investigate, and coordinate a fix and disclosure
timeline with you.

## Scope worth flagging

Because the tool's whole purpose is keeping secrets out of git, reports about
the following are especially valuable:

- A path where a secret value could be written to a committed file.
- A way the pre-push safety scan can be bypassed for token-shaped values.
- The gitignore guard failing to protect the local secrets/state files.

## Supported versions

This is pre-1.0 software; only the latest released version receives fixes.
