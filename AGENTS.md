<!-- Generated from AGENTS.src.md. Edit the source, then copy its body here. -->

# SerrebiFdroid

Signed binary F-Droid repository for serrebidev's published Android apps.

- apps.json is the explicit application allowlist. Never discover or publish apps automatically.
- Import original stable APKs only. Verify release size, SHA-256 sidecar when present, package ID, and pinned APK certificate before indexing.
- Never resign APKs, replace a published version with different bytes, or commit private signing material.
- Keep metadata AllowedAPKSigningKeys consistent with apps.json.
- Runtime signing config and keystore stay outside the public web root and Git.
- Standard fdroidserver handles indexes and repository signatures.
- Tests: python -m unittest discover -s tests -v.
- Server paths and deployment steps are documented in README.md.
- Forgejo (git.serrebiradio.com) is the source of truth: code, releases, issues, CI. A GitHub copy, if any, is a push mirror only; never point apps.json or URLs back at it.

## Agent skills

### Issue tracker

Issues are tracked in this repo's Forgejo Issues at git.serrebiradio.com, via the `tea` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
