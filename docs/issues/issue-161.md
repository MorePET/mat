---
type: issue
state: open
created: 2026-05-04T19:55:53Z
updated: 2026-05-06T21:16:31Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/161
comments: 1
labels: data-source, deferred-4.x
assignees: none
milestone: Data Sources & Licensing
projects: none
parent: none
children: none
synced: 2026-05-07T05:23:49.712Z
---

# [Issue 161]: [Integrate NIST PhysRefData / XCOM / FFAST — radiation length & X-ray attenuation](https://github.com/MorePET/mat/issues/161)

NIST X-ray databases: XCOM (photon cross-sections), FFAST (form factor / attenuation), Atomic Weights / Isotopic Compositions. US-gov, effectively public domain for redistribution; scalar fields py-mat keeps (radiation_length_cm, interaction_length_cm, mean_excitation_energy_eV) live here.

Note: tabular cross-section data goes to nucl-parquet, not py-mat (#157). Only ingest scalars into py-mat.

Reference: https://www.nist.gov/pml/xcom-photon-cross-sections-database, https://www.nist.gov/pml/x-ray-form-factor-attenuation-and-scattering-tables
---

# [Comment #1]() by [gerchowl]()

_Posted on May 6, 2026 at 09:16 PM_

Deferred to a future 4.x minor release per Phase 4 design review (3 parallel reviewers, May 2026). NIST PhysRefData / XCOM / FFAST — deferred to 4.x: radiation length tables are detector-physics specific. The optional [nuclear] extra (#157) already delegates this concern to nucl-parquet (~50 KB per element of XCOM data). When a consumer needs it, py-mat[nuclear] is the path; no need to bulk-import into core TOMLs.

Not closed — the issue stays open with the `deferred-4.x` label so it surfaces in future planning.

