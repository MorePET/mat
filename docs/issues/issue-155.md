---
type: issue
state: open
created: 2026-05-04T19:50:29Z
updated: 2026-05-04T19:50:29Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/155
comments: 0
labels: enhancement, schema
assignees: none
milestone: Properties Schema Expansion
projects: none
parent: none
children: none
synced: 2026-05-05T04:54:19.203Z
---

# [Issue 155]: [Schema: new `magnetic` sub-table](https://github.com/MorePET/mat/issues/155)

Currently no magnetic data. Required for MR-PET hybrid systems (need χ < ~10 ppm for null artifacts). Add new `[<material>.magnetic]` sub-table with: `susceptibility_volumetric` (χ_v, SI, dimensionless), `permeability_relative` (μr), `saturation_field` (T, ferromagnetics). Reference values: Cu -9.6e-6, Ti -1.8e-6, mu-metal +20000.
