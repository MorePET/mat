---
type: issue
state: open
created: 2026-04-17T11:06:29Z
updated: 2026-04-17T11:06:29Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/38
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-04-18T04:24:32.349Z
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
