---
type: issue
state: open
created: 2026-05-04T19:55:48Z
updated: 2026-05-04T19:55:49Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/159
comments: 0
labels: data-source
assignees: none
milestone: Data Sources & Licensing
projects: none
parent: none
children: none
synced: 2026-05-05T04:54:17.635Z
---

# [Issue 159]: [Integrate NIST Chemistry WebBook (SRD 69) — gases & liquids](https://github.com/MorePET/mat/issues/159)

NIST SRD 69 covers thermophysical properties of ~74 fluids (Cp, viscosity, thermal conductivity, density vs T, P). US-government work, public domain in US per 17 U.S.C. §105 (foreign copyright may apply).

Action: scrape once for our gases.toml + liquids.toml entries (water, mineral_oil, glycerol, silicone_oil, N2, O2, Ar, He, Ne, Xe, CO2, methane, hydrogen, SF6). No public API — use the search interface. Cite as `source = "nist:srd69"` with the AS-IS / NIST notice in a top-level LICENSES-DATA.md.

Reference: https://webbook.nist.gov/chemistry/
