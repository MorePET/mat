---
type: issue
state: open
created: 2026-05-04T19:56:06Z
updated: 2026-05-04T19:56:06Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/168
comments: 0
labels: data-source
assignees: none
milestone: Data Sources & Licensing
projects: none
parent: none
children: none
synced: 2026-05-05T04:54:14.227Z
---

# [Issue 168]: [Integrate HEPData (CC0) — opportunistic detector measurements](https://github.com/MorePET/mat/issues/168)

All HepData metadata + datasets are CC0 ([terms](https://www.hepdata.net/terms)). Format: YAML/JSON/ROOT/CSV. Coverage: HEP measurements; sparse for routine scintillator characterization.

Action: opportunistic — when adding a scintillator entry, search HepData for the relevant characterization paper. If a HepData record exists, cite it (DOI + record ID). Don't build a bulk pipeline — value/effort ratio is low for our scope.
