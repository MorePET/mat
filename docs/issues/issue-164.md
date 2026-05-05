---
type: issue
state: open
created: 2026-05-04T19:55:58Z
updated: 2026-05-04T19:55:58Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/164
comments: 0
labels: data-source
assignees: none
milestone: Data Sources & Licensing
projects: none
parent: none
children: none
synced: 2026-05-05T04:54:15.738Z
---

# [Issue 164]: [Integrate refractiveindex.info (CC0) — n,k dispersion library](https://github.com/MorePET/mat/issues/164)

Polyanskiy database is **CC0** per [GitHub README](https://github.com/polyanskiy/refractiveindex.info-database). Bulk YAML download. Drop-in source for the new `refractive_index_dispersion` schema (#152).

Coverage: NaCl, CsI, NaI, BGO, BaF2, YAG/YAP/LuAG, sapphire, fused silica, PMMA, polystyrene, metals (Au, Ag, Cu, Al, Ti, etc). Sparse for LYSO/GAGG/LaBr3.

Action: vendor as a git submodule under `scripts/data/refractiveindex` or pull on demand. Tag `_sources` with `license = "CC0"` and `url` to specific YAML.
