---
type: issue
state: closed
created: 2026-05-04T19:56:11Z
updated: 2026-05-06T21:15:52Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/171
comments: 1
labels: data-source
assignees: none
milestone: Data Sources & Licensing
projects: none
parent: none
children: none
synced: 2026-05-07T05:23:45.761Z
---

# [Issue 171]: [PDG Atomic & Nuclear Properties — cite individual values](https://github.com/MorePET/mat/issues/171)

[pdg.lbl.gov/AtomicNuclearProperties/](https://pdg.lbl.gov/AtomicNuclearProperties/) — ~300 materials with density, radiation length, nuclear interaction length, dE/dx, Cherenkov refractive index. License **not explicit**; PDG tables traditionally allowed reproduction with citation.

Recommendation: cite individual values with attribution; do **not** bulk-import. Treat as authoritative cross-check for radiation_length and interaction_length scalars.
---

# [Comment #1]() by [gerchowl]()

_Posted on May 6, 2026 at 09:15 PM_

Cut for 3.x release per Phase 4 design review (3 parallel reviewers, May 2026). PDG cite-only — cut for 3.x: there's nothing to cite until detector-physics values flow in via #168/#169 (also cut). Co-cut.

The schema infra is in place — the _sources table accepts citations from this source ad-hoc when individual contributors find specific values. This issue is closed, not deferred — reopen if/when a consumer requires this.

