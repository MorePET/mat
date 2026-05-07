---
type: issue
state: open
created: 2026-05-04T19:55:50Z
updated: 2026-05-06T21:16:28Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/160
comments: 1
labels: data-source, deferred-4.x
assignees: none
milestone: Data Sources & Licensing
projects: none
parent: none
children: none
synced: 2026-05-07T05:23:50.108Z
---

# [Issue 160]: [Integrate NIST Cryogenic Materials Property Database — low-T data](https://github.com/MorePET/mat/issues/160)

Free public-access database with polynomial fits for metals + structural plastics (G10, Kapton, PTFE, etc.) at 4–300 K. US-gov public domain.

Unique value: only authoritative source for low-T thermal conductivity, specific heat, and integrated thermal conductivity for cryogenic detector work (LYSO/SiPM cooling, LN2 dewars, LHe). Directly feeds the T-curve schema (#148).

Action: parse polynomial coefficients into `<prop>_curve` entries for: aluminum (6061-T6, 1100), copper (OFHC), stainless 304/316, Ti-6Al-4V, Invar, brass, lead, beryllium, G10, Kapton, PTFE.

Reference: https://trc.nist.gov/cryogenics/materials/materialproperties.htm
---

# [Comment #1]() by [gerchowl]()

_Posted on May 6, 2026 at 09:16 PM_

Deferred to a future 4.x minor release per Phase 4 design review (3 parallel reviewers, May 2026). NIST Cryogenic Materials Database — deferred to 4.x: low-T data is a niche use case with zero current-consumer signal (build123d doesn't care about cryogenic property variations). Schema infra (T-curves from #148) is in place; populates whenever a cryo consumer materializes.

Not closed — the issue stays open with the `deferred-4.x` label so it surfaces in future planning.

