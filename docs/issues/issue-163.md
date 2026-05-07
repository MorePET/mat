---
type: issue
state: closed
created: 2026-05-04T19:55:57Z
updated: 2026-05-06T21:15:45Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/163
comments: 1
labels: data-source
assignees: none
milestone: Data Sources & Licensing
projects: none
parent: none
children: none
synced: 2026-05-07T05:23:48.931Z
---

# [Issue 163]: [Integrate Materials Project (CC-BY 4.0) — DFT elastic constants + band gaps](https://github.com/MorePET/mat/issues/163)

REST API + pymatgen. Strong on DFT-computed properties for ~150k inorganic crystalline phases (formation energy, band gap, full elastic tensor, bulk/shear modulus). Weak for amorphous, polymers, alloys-as-mixtures.

Action: pre-fetch elastic constants + band gaps for ceramics/substrates: alumina, sapphire, AlN, Si3N4, SiC, ZrO2, BeO, Y2O3, BGO, LYSO host (Lu2SiO5), GAGG host (Gd3Al2Ga3O12), MgO. Attribute "© Materials Project, CC-BY 4.0" in LICENSES-DATA.md and per-record `attribution` field.

Reference: https://next-gen.materialsproject.org/about/terms
---

# [Comment #1]() by [gerchowl]()

_Posted on May 6, 2026 at 09:15 PM_

Cut for 3.x release per Phase 4 design review (3 parallel reviewers, May 2026). Materials Project — cut for 3.x: API key acquisition friction, CC-BY 4.0 per-record attribution UX we don't have, and DFT values shift between MP database releases (reproducibility hole). High cost, zero current-consumer signal — build123d (the only known active consumer) doesn't read DFT data. Revisit if/when a consumer materializes that needs live MP lookup.

The schema infra is in place — the _sources table accepts citations from this source ad-hoc when individual contributors find specific values. This issue is closed, not deferred — reopen if/when a consumer requires this.

