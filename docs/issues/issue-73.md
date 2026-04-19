---
type: issue
state: closed
created: 2026-04-18T23:32:02Z
updated: 2026-04-19T01:00:17Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/73
comments: 1
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-04-19T04:44:00.186Z
---

# [Issue 73]: [3.2: migrate to mat-vis-client 0.5.0 (MtlxSource.xml() + typed errors + get_client)](https://github.com/MorePET/mat/issues/73)

Tracking issue for py-mat's migration to mat-vis-client 0.5.0 once it ships.
Upstream tracking: [mat-vis#85](https://github.com/MorePET/mat-vis/issues/85) on branch \`refactor/85-client-v05-api-ux\`.

## What breaks in py-mat

### 1. \`MtlxSource.xml\` becomes a method — **BREAKING for consumers**

0.4.x: \`source.xml\` (property, network IO on attribute access)
0.5.0: \`source.xml()\` (explicit method call — JS/Rust-portable)

**py-mat impact: docstrings only.** We don't call \`.xml\` in code; only in class docstrings:

- \`src/pymat/core.py:212\` — \`_MaterialInternal.vis\` property docstring
- \`src/pymat/vis/_model.py:107\` — \`Vis\` class docstring
- \`src/pymat/vis/_model.py:348\` — \`Vis.mtlx\` property docstring

Downstream consumers who followed the 3.1 guidance (\`steel.vis.mtlx.xml\`) WILL break. Migration guide must call this out.

### 2. \`_get_client\` → \`get_client\` — soft-deprecated

0.4.x: \`from mat_vis_client import _get_client\` (reaches past the underscore; see [mat-vis#84](https://github.com/MorePET/mat-vis/issues/84))
0.5.0: \`from mat_vis_client import get_client\`; \`_get_client\` emits \`DeprecationWarning\` for one release.

**py-mat impact: 4 import sites to rename:**

- \`src/pymat/vis/__init__.py:59, 86, 158\` (three call sites)
- \`src/pymat/vis/_model.py:338\` (\`Vis.client\` property)

Non-breaking during the 0.5.x cycle (the deprecated alias works), but do the rename now to silence the warning.

### 3. Typed error hierarchy replaces raw \`urllib.HTTPError\` leakage

0.4.x: \`client.fetch_all_textures\` and friends can raise \`urllib.error.HTTPError\` directly
0.5.0: wrapped in typed subclasses of \`MatVisError\`:

- \`HTTPFetchError\` — generic 4xx/5xx with \`url\` + \`code\` + \`reason\`
- \`NotFoundError\` (and typed subclasses: \`MaterialNotFoundError\`, \`SourceNotFoundError\`, \`TierNotFoundError\`, \`ChannelNotFoundError\`)
- \`NetworkError\` — connection failures
- \`RateLimitError\` (already exists)

**py-mat impact: `tests/test_e2e_vis.py` `_skip_on_upstream_outage`.**

Currently catches \`urllib.error.HTTPError\` with \`exc.code\` check. After 0.5.0, real errors arrive as \`HTTPFetchError\` / \`NetworkError\`. Update the guard to catch \`MatVisError\` subclasses (grab \`.code\` if present, otherwise skip on any \`NetworkError\` / \`HTTPFetchError\`).

\`tests/test_e2e_vis.py::TestSkipOnUpstreamOutage\` also synthesizes \`HTTPError\` with \`code=502\` / \`404\` — those specific exception types are no longer what the guard sees in production, so the synthesizer needs to emit the new types too.

### 4. Non-breaking additions (no py-mat changes required)

- \`client.at(tag)\` — alternate client scoped to a specific release tag. Useful for future multi-release workflows; we don't need it in 3.2.
- Per-operation \`tag=\` kwarg on \`client.fetch\` / \`search\` / \`prefetch\` / \`mtlx\`. Additive.
- \`cache=False\` mode on \`MatVisClient(...)\`. Additive.
- \`client.search\` unified signature — new \`tier=\` and \`tag=\` kwargs, existing roughness/metalness/range args preserved. Additive.
- Internal \`schema.py\` registry — no consumer-visible surface.

## Scope of py-mat 3.2

### Code changes

- [ ] Rename 4 \`_get_client\` imports → \`get_client\` (src/pymat/vis/__init__.py, _model.py)
- [ ] Update 3 docstrings \`.mtlx.xml\` → \`.mtlx.xml()\` (core.py, _model.py)
- [ ] Update \`tests/test_e2e_vis.py::_skip_on_upstream_outage\` to catch \`MatVisError\` subclasses (\`NetworkError\`, \`HTTPFetchError\`, \`NotFoundError\` with 5xx codes)
- [ ] Update \`TestSkipOnUpstreamOutage\` to synthesize the new exception types
- [ ] Bump \`mat-vis-client>=0.5.0\` in \`pyproject.toml\`

### Test changes

- [ ] Regression test that \`pymat.vis.fetch\` surfaces typed errors (e.g. \`MaterialNotFoundError\` for bad IDs) — replaces the implicit "something urllib-y happens" contract
- [ ] Thread-safety race reproducer in \`tests/test_vis.py::TestModuleShape\` uses \`mat_vis_client._client\` monkeypatch — confirm the internal attribute name didn't rename

### Doc changes

- [ ] \`docs/migration/v2-to-v3.md\` — add a 3.1 → 3.2 section covering the \`.mtlx.xml()\` breakage
- [ ] ADR-0002 — no changes (delegation sugar still wraps the same methods)
- [ ] CHANGELOG \`[3.2.0]\` section

## Timing

Blocked on mat-vis 0.5.0 PyPI publish. Watch [mat-vis#85](https://github.com/MorePET/mat-vis/issues/85) for the release tag. Once it lands:

1. File the PR against py-mat with all items above
2. Test locally: \`uv pip install mat-vis-client==0.5.0 && pytest tests/\`
3. Ship as 3.2.0 (breaking — \`.mtlx.xml()\` is user-visible)
---

# [Comment #1]() by [gerchowl]()

_Posted on April 18, 2026 at 11:37 PM_

## Phase 1 complete (code migration)

Landed on \`feature/73-mat-vis-client-0.5\` (stacked on \`feature/58-vis-identity-split\`), commit \`52bde58\`. Verified locally against \`/Users/larsgerchow/Projects/mat-vis/clients/python\` on \`refactor/85-client-v05-api-ux\` (commit \`da335c9\`, version 0.5.0-dev). 268 passing, zero DeprecationWarnings.

### What's done

- \`_get_client\` → \`get_client\` with try/except fallback — keeps 0.4.x floor intact
- \`material.vis.mtlx.xml\` → \`material.vis.mtlx.xml()\` in all 3 docstrings
- \`_skip_on_upstream_outage\` catches typed \`MatVisError\` subclasses (\`HTTPFetchError\`, \`NetworkError\`) alongside \`urllib.error.HTTPError\`
- 2 new tests pin the typed-error skip paths (skipped on <0.5 installs)
- Migration guide section \`3.1 → 3.2\` written
- CHANGELOG \`[Unreleased]\` section with pending floor + version bumps

### Phase 2 (blocks release)

- [ ] \`mat-vis-client\` PyPI publish of \`0.5.0\` (tracking: [mat-vis#85](https://github.com/MorePET/mat-vis/issues/85))
- [ ] \`pyproject.toml\` floor: \`mat-vis-client>=0.5.0\`
- [ ] \`__version__\` bump \`3.1.2\` → \`3.2.0\`
- [ ] Close \`[Unreleased]\` in CHANGELOG as \`[3.2.0]\` + date

Branch is ready to flip the moment 0.5.0 hits PyPI — Phase 2 is ~5 LOC.

