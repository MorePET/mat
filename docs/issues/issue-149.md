---
type: issue
state: open
created: 2026-05-04T19:50:18Z
updated: 2026-05-04T19:50:18Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/149
comments: 0
labels: enhancement, schema
assignees: none
milestone: Properties Schema Expansion
projects: none
parent: none
children: none
synced: 2026-05-05T04:54:21.534Z
---

# [Issue 149]: [Schema: per-property uncertainty (`_stddev`)](https://github.com/MorePET/mat/issues/149)

Add `<prop>_stddev` siblings to capture vendor spread. Example: LYSO light yield Saint-Gobain 33k vs SICCAS 30k photons/MeV. Lets simulations propagate uncertainty rather than treating values as exact. Optional field — absence ⇒ unknown.
