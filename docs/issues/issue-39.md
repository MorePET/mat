---
type: issue
state: open
created: 2026-04-17T11:06:30Z
updated: 2026-04-17T11:06:30Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/39
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-04-18T04:24:31.911Z
---

# [Issue 39]: [CI workflow: auto-propose vis mappings on mat-vis release](https://github.com/MorePET/mat/issues/39)

## Context

`scripts/enrich_vis.py` exists and proposes [vis] TOML sections
by matching material scalars against the mat-vis index.

## Tasks

- [ ] `.github/workflows/enrich-vis.yml` — runs on mat-vis release
      dispatch or manual trigger
- [ ] Opens PR with proposed vis mappings for unmapped materials
- [ ] Human reviews and merges

## Deferred from

2.2.0 — script works, CI wiring deferred.
