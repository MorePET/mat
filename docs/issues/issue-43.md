---
type: issue
state: closed
created: 2026-04-18T16:21:44Z
updated: 2026-04-18T16:50:09Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/43
comments: 0
labels: enhancement, question
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-04-19T04:44:06.594Z
---

# [Issue 43]: [ci: enable rs-materials crates.io publishing](https://github.com/MorePET/mat/issues/43)

## Context

`release-please.yml` now manages version bumps and tags for both `py-materials` (Python → PyPI) and `rs-materials` (Rust → crates.io). The Python publish path is live; the Rust one is **gated off** until crates.io is wired up.

## What's blocking

- No `CARGO_REGISTRY_TOKEN` secret configured
- No coordination yet with downstream Rust consumers about expected cadence, MSRV, or semver contract of `rs-materials`

## Current state

`.github/workflows/release-rs-materials.yml` has the publish job guarded:

\`\`\`yaml
publish-crates-io:
  if: vars.CRATES_IO_PUBLISH_ENABLED == 'true'
\`\`\`

Until the variable flips, tags in the form \`rs-materials/vX.Y.Z\` still push (from release-please), the crate still tests, the GitHub Release still publishes with notes — only the crates.io upload is skipped. This keeps the pipeline green and reversible.

## To enable

1. Create a crates.io account (or reuse existing) with publish rights for \`rs-materials\`
2. Generate a scoped API token at https://crates.io/settings/tokens (scope: publish-update only, not publish-new — the crate already exists)
3. Add it as a repo secret: \`gh secret set CARGO_REGISTRY_TOKEN\`
4. Flip the gate: \`gh variable set CRATES_IO_PUBLISH_ENABLED --body true\`
5. Trigger a release (next \`feat:\`/\`fix:\` touching \`mat-rs/**\` → release-please Release PR → merge → tag → publish)

## Coordination with other consumers

Before flipping the gate, verify:

- [ ] Any downstream crate that depends on \`rs-materials\` via git ref migrates to the crates.io version
- [ ] MSRV is documented in \`mat-rs/Cargo.toml\` (\`rust-version\` field)
- [ ] API surface is semver-stable enough for 0.3 / 1.0 commitment

This intentionally defers to align with the JS/TS decision point in #42 — both are "external consumer" questions that benefit from being settled together.

## Refs

Related: #42 (JS/TS consumer decision)

Refs: #42
