---
type: pull_request
state: closed (merged)
branch: feat/composition-and-target-materials → main
created: 2026-03-09T15:56:57Z
updated: 2026-03-09T16:17:37Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/pull/2
comments: 0
labels: none
assignees: none
milestone: none
projects: none
merged: 2026-03-09T16:17:35Z
synced: 2026-04-15T04:38:32.159Z
---

# [PR 2](https://github.com/MorePET/mat/pull/2) Add elemental compositions and target materials for radiation physics

## Summary

- Add `composition` dicts (element → mass fraction) to existing alloys that were missing them: stainless steel grades (304, 316L, 17-4PH), aluminum alloys (6061, 7075), tungsten W90, brass, Ti-6Al-4V
- Add `formula` fields to pure metals that were missing them (Al, Cu, Ti)
- Add 14 new materials commonly used as cyclotron targets, backings, and windows in isotope production: havar, niobium, silver, gold, molybdenum, gallium, bismuth, rhodium, yttrium, radium, nickel, iron, zinc, tin

## Motivation

The `composition` field exists on `Material` and the loader reads it from TOML, but no material in the database actually populated it. This data is needed by downstream consumers (e.g. hyrr) that resolve materials into elemental breakdowns for radiation transport calculations.

The new target materials are standard in medical isotope production (cyclotron targets, beam windows, backing foils) and were missing from the catalog entirely.

## What changed

- **`src/pymat/data/metals.toml`** — compositions on 9 existing alloys, formulas on 3 pure metals, 14 new material entries with full properties (mechanical, thermal, PBR)
- **`tests/test_loader.py`** — 6 new tests validating compositions sum to ~1.0, spot-checking key alloys, and verifying all new materials have density + formula

## Test plan

- [x] All existing tests pass (102 passed, 5 pre-existing factory failures unrelated to this PR)
- [x] New `TestCompositionData` tests pass (6/6)
- [x] TOML validates with `tomllib`
- [x] `load_all()` loads 127 materials without errors
- [x] All composition dicts sum to ~1.0


---
---

## Commits

### Commit 1: [5e883bf](https://github.com/MorePET/mat/commit/5e883bf43d32b278e0bd27b9c6b95aa27498b805) by [gerchowl](https://github.com/gerchowl) on March 9, 2026 at 03:54 PM
Add elemental compositions and target materials for radiation physics, 503 files modified (src/pymat/data/metals.toml, tests/test_loader.py)
