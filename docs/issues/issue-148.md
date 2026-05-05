---
type: issue
state: open
created: 2026-05-04T19:50:16Z
updated: 2026-05-04T19:50:16Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/148
comments: 0
labels: enhancement, schema
assignees: none
milestone: Properties Schema Expansion
projects: none
parent: none
children: none
synced: 2026-05-05T04:54:21.894Z
---

# [Issue 148]: [Schema: T-dependent property curves](https://github.com/MorePET/mat/issues/148)

Today `<prop>_value`/`<prop>_unit` is scalar-only. Cryogenic SiPM (-40 to -80 C), LN2 (77 K), and LHe (4 K) work all need temperature-dependent curves. Proposal: add `<prop>_curve = {temps_K=[...], values=[...]}` with linear interpolation in `properties.py`. Apply to: thermal_conductivity, specific_heat, thermal_expansion, youngs_modulus, yield_strength, resistivity, refractive_index, light_yield, decay_time. LYSO light yield shifts ~+15% from 20 C to -40 C — this is load-bearing for TOF-PET. Backwards-compatible: scalar form continues to work; curve takes precedence when present.
