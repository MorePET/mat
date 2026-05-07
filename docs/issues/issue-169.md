---
type: issue
state: closed
created: 2026-05-04T19:56:07Z
updated: 2026-05-06T21:15:50Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/169
comments: 1
labels: data-source
assignees: none
milestone: Data Sources & Licensing
projects: none
parent: none
children: none
synced: 2026-05-07T05:23:46.566Z
---

# [Issue 169]: [SCOAP3 / arXiv (CC-BY) — extract values from open-access papers](https://github.com/MorePET/mat/issues/169)

SCOAP3 mandates CC-BY for HEP journals (PRD, EPJC, JHEP, PLB, NIM-A subset). Allows TDM. arXiv preprints have author-set licenses — check per paper.

Workflow:
1. Identify scintillator paper (often via LBNL Scintillator Library citation lists)
2. Verify CC-BY license tag on paper
3. Extract numeric values; cite paper DOI + license

Specifically valuable for: light yield, decay components, emission spectra, non-proportionality of LYSO/GAGG/LaBr3/CeBr3 — values vendor datasheets won't redistribute.

Action: document the workflow in CONTRIBUTING.md curation section. Manual per-material until volume justifies tooling.
---

# [Comment #1]() by [gerchowl]()

_Posted on May 6, 2026 at 09:15 PM_

Cut for 3.x release per Phase 4 design review (3 parallel reviewers, May 2026). SCOAP3 / arXiv — cut for 3.x: per-paper extraction is the most labor-intensive path on the Phase 4 list; trivially deferrable. The _sources schema (#150) supports DOI citations directly when contributors find them, so we don't need a bulk pipeline.

The schema infra is in place — the _sources table accepts citations from this source ad-hoc when individual contributors find specific values. This issue is closed, not deferred — reopen if/when a consumer requires this.

