---
type: issue
state: open
created: 2026-05-04T19:55:57Z
updated: 2026-05-04T19:55:57Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/163
comments: 0
labels: data-source
assignees: none
milestone: Data Sources & Licensing
projects: none
parent: none
children: none
synced: 2026-05-05T04:54:16.125Z
---

# [Issue 163]: [Integrate Materials Project (CC-BY 4.0) — DFT elastic constants + band gaps](https://github.com/MorePET/mat/issues/163)

REST API + pymatgen. Strong on DFT-computed properties for ~150k inorganic crystalline phases (formation energy, band gap, full elastic tensor, bulk/shear modulus). Weak for amorphous, polymers, alloys-as-mixtures.

Action: pre-fetch elastic constants + band gaps for ceramics/substrates: alumina, sapphire, AlN, Si3N4, SiC, ZrO2, BeO, Y2O3, BGO, LYSO host (Lu2SiO5), GAGG host (Gd3Al2Ga3O12), MgO. Attribute "© Materials Project, CC-BY 4.0" in LICENSES-DATA.md and per-record `attribution` field.

Reference: https://next-gen.materialsproject.org/about/terms
