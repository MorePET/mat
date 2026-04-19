---
type: issue
state: closed
created: 2026-04-17T11:06:30Z
updated: 2026-04-18T08:07:05Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/39
comments: 1
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-04-19T04:44:07.961Z
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
---

# [Comment #1]() by [gerchowl]()

_Posted on April 18, 2026 at 08:07 AM_

Done on `docs/refresh-readme-2.1.0` (commit 60c318f): `.github/workflows/enrich-vis.yml` runs on `mat-vis-release` dispatch + manual trigger. Uses tag-based matching (commit 4e4eb2f) for much better proposals than category alone. Opens PR with proposed [vis] sections for human review.

