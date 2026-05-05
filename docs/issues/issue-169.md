---
type: issue
state: open
created: 2026-05-04T19:56:07Z
updated: 2026-05-04T19:56:07Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/169
comments: 0
labels: data-source
assignees: none
milestone: Data Sources & Licensing
projects: none
parent: none
children: none
synced: 2026-05-05T04:54:13.870Z
---

# [Issue 169]: [SCOAP3 / arXiv (CC-BY) — extract values from open-access papers](https://github.com/MorePET/mat/issues/169)

SCOAP3 mandates CC-BY for HEP journals (PRD, EPJC, JHEP, PLB, NIM-A subset). Allows TDM. arXiv preprints have author-set licenses — check per paper.

Workflow:
1. Identify scintillator paper (often via LBNL Scintillator Library citation lists)
2. Verify CC-BY license tag on paper
3. Extract numeric values; cite paper DOI + license

Specifically valuable for: light yield, decay components, emission spectra, non-proportionality of LYSO/GAGG/LaBr3/CeBr3 — values vendor datasheets won't redistribute.

Action: document the workflow in CONTRIBUTING.md curation section. Manual per-material until volume justifies tooling.
