---
type: issue
state: open
created: 2026-05-04T19:55:50Z
updated: 2026-05-04T19:55:51Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/160
comments: 0
labels: data-source
assignees: none
milestone: Data Sources & Licensing
projects: none
parent: none
children: none
synced: 2026-05-05T04:54:17.263Z
---

# [Issue 160]: [Integrate NIST Cryogenic Materials Property Database — low-T data](https://github.com/MorePET/mat/issues/160)

Free public-access database with polynomial fits for metals + structural plastics (G10, Kapton, PTFE, etc.) at 4–300 K. US-gov public domain.

Unique value: only authoritative source for low-T thermal conductivity, specific heat, and integrated thermal conductivity for cryogenic detector work (LYSO/SiPM cooling, LN2 dewars, LHe). Directly feeds the T-curve schema (#148).

Action: parse polynomial coefficients into `<prop>_curve` entries for: aluminum (6061-T6, 1100), copper (OFHC), stainless 304/316, Ti-6Al-4V, Invar, brass, lead, beryllium, G10, Kapton, PTFE.

Reference: https://trc.nist.gov/cryogenics/materials/materialproperties.htm
