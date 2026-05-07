---
type: issue
state: open
created: 2026-05-04T19:55:55Z
updated: 2026-05-06T21:16:34Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/162
comments: 1
labels: data-source, deferred-4.x
assignees: none
milestone: Data Sources & Licensing
projects: none
parent: none
children: none
synced: 2026-05-07T05:23:49.279Z
---

# [Issue 162]: [Integrate NASA GSFC Outgassing Database — vacuum sub-table](https://github.com/MorePET/mat/issues/162)

**Unique source** — only free DB for ASTM E595 TML/CVCM/WVR. US-gov, public domain in US. No API; HTML-rendered, scrapeable.

Coverage: adhesives, coatings, foams, lubricants, potting compounds, elastomers. Directly populates the new `vacuum` sub-table (#155) for: epoxy_potting, silicone_potting, kapton, ptfe, peek, delrin, viton, polyurethane foam, EPO-TEK 301.

Action: one-time scrape of relevant entries; cite as `source = "nasa:gsfc-etd-outgassing"`.

Reference: https://etd.gsfc.nasa.gov/capabilities/outgassing-database/
---

# [Comment #1]() by [gerchowl]()

_Posted on May 6, 2026 at 09:16 PM_

Deferred to a future 4.x minor release per Phase 4 design review (3 parallel reviewers, May 2026). NASA GSFC Outgassing Database — deferred to 4.x: UHV detector enclosure niche. Vacuum sub-table (#156) shipped the schema slots; populating from NASA's PDF-encoded vendor-coded data is high effort vs. current-consumer payoff.

Not closed — the issue stays open with the `deferred-4.x` label so it surfaces in future planning.

