---
type: issue
state: open
created: 2026-05-04T19:50:23Z
updated: 2026-05-04T19:50:23Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/152
comments: 0
labels: enhancement, schema
assignees: none
milestone: Properties Schema Expansion
projects: none
parent: none
children: none
synced: 2026-05-05T04:54:20.394Z
---

# [Issue 152]: [Schema: thermal sub-table additions](https://github.com/MorePET/mat/issues/152)

Add to `thermal`: `emissivity` (0-1, **critical for cryogenic radiation shielding budgets** — polished Al ≈ 0.04, anodized ≈ 0.8), `thermal_diffusivity` (mm²/s), `min_use_temp_K` + `cryogenic_compatible` (bool — Delrin/PEEK get brittle below ~-50 C), `integrated_thermal_conductivity` (W/m, ∫k dT, NIST style for cryo heat-leak), `latent_heat_fusion` / `latent_heat_vaporization` (kJ/kg, for liquids/coolants).
