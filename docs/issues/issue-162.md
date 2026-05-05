---
type: issue
state: open
created: 2026-05-04T19:55:55Z
updated: 2026-05-04T19:55:55Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/162
comments: 0
labels: data-source
assignees: none
milestone: Data Sources & Licensing
projects: none
parent: none
children: none
synced: 2026-05-05T04:54:16.524Z
---

# [Issue 162]: [Integrate NASA GSFC Outgassing Database — vacuum sub-table](https://github.com/MorePET/mat/issues/162)

**Unique source** — only free DB for ASTM E595 TML/CVCM/WVR. US-gov, public domain in US. No API; HTML-rendered, scrapeable.

Coverage: adhesives, coatings, foams, lubricants, potting compounds, elastomers. Directly populates the new `vacuum` sub-table (#155) for: epoxy_potting, silicone_potting, kapton, ptfe, peek, delrin, viton, polyurethane foam, EPO-TEK 301.

Action: one-time scrape of relevant entries; cite as `source = "nasa:gsfc-etd-outgassing"`.

Reference: https://etd.gsfc.nasa.gov/capabilities/outgassing-database/
