---
type: issue
state: closed
created: 2026-04-17T11:06:29Z
updated: 2026-04-18T08:07:04Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/38
comments: 1
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-04-19T04:44:08.330Z
---

# [Issue 38]: [Material catalog with thumbnails (docs/catalog/)](https://github.com/MorePET/mat/issues/38)

## Context

`scripts/generate_catalog.py` exists and generates a markdown tree
with per-category + per-material pages. Thumbnails fetch from
mat-vis's 128px tier (no Pillow needed).

## Tasks

- [ ] Generate `docs/catalog/` and commit to repo
- [ ] CI workflow (`catalog.yml`) to regenerate on TOML changes
- [ ] Thumbnails from mat-vis 128px tier once available
- [ ] Link from README (already done: "docs/catalog/" section)

## Deferred from

2.2.0 — waiting for mat-vis thumbnail tiers to land.
---

# [Comment #1]() by [gerchowl]()

_Posted on April 18, 2026 at 08:07 AM_

Done on `docs/refresh-readme-2.1.0` (commits c15f4ce, 60c318f, 4e4eb2f): `docs/catalog/` generated with 96 materials across 7 categories. `.github/workflows/catalog.yml` regenerates on TOML changes. Thumbnails from mat-vis 128px tier now working — 4 materials have thumbnails (aluminum, brass, copper, titanium). More will follow as [vis] mappings are curated.

