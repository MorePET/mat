---
type: issue
state: closed
created: 2026-05-04T19:56:06Z
updated: 2026-05-06T21:15:47Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/168
comments: 1
labels: data-source
assignees: none
milestone: Data Sources & Licensing
projects: none
parent: none
children: none
synced: 2026-05-07T05:23:46.951Z
---

# [Issue 168]: [Integrate HEPData (CC0) — opportunistic detector measurements](https://github.com/MorePET/mat/issues/168)

All HepData metadata + datasets are CC0 ([terms](https://www.hepdata.net/terms)). Format: YAML/JSON/ROOT/CSV. Coverage: HEP measurements; sparse for routine scintillator characterization.

Action: opportunistic — when adding a scintillator entry, search HepData for the relevant characterization paper. If a HepData record exists, cite it (DOI + record ID). Don't build a bulk pipeline — value/effort ratio is low for our scope.
---

# [Comment #1]() by [gerchowl]()

_Posted on May 6, 2026 at 09:15 PM_

Cut for 3.x release per Phase 4 design review (3 parallel reviewers, May 2026). HEPData — cut for 3.x: per-measurement curation work scales linearly with human hours; pays off only with a HEP-focused consumer we don't have. Revisit if a detector-physics user materializes.

The schema infra is in place — the _sources table accepts citations from this source ad-hoc when individual contributors find specific values. This issue is closed, not deferred — reopen if/when a consumer requires this.

