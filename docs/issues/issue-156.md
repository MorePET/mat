---
type: issue
state: open
created: 2026-05-04T19:50:30Z
updated: 2026-05-04T19:50:30Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/156
comments: 0
labels: enhancement, schema
assignees: none
milestone: Properties Schema Expansion
projects: none
parent: none
children: none
synced: 2026-05-05T04:54:18.818Z
---

# [Issue 156]: [Schema: new `vacuum` sub-table](https://github.com/MorePET/mat/issues/156)

Add new `[<material>.vacuum]` sub-table for UHV detector enclosures and Geant4 vacuum modeling: `outgassing_rate_torr_l_per_s_cm2` (after 1h, 10h pumping), `tml_pct` (total mass loss) + `cvcm_pct` (collected volatile condensable material) per ASTM E595 / NASA std, `bakeout_temp_max_C`, `permeation_he_cm3_mm_per_cm2_s_atm`, `vacuum_class` ("UHV"/"HV"/"rough"). Particularly relevant for: PEEK, Delrin (notably bad in UHV), Viton, Kapton, all elastomers, epoxies.
