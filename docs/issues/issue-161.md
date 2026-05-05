---
type: issue
state: open
created: 2026-05-04T19:55:53Z
updated: 2026-05-04T19:55:53Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/161
comments: 0
labels: data-source
assignees: none
milestone: Data Sources & Licensing
projects: none
parent: none
children: none
synced: 2026-05-05T04:54:16.901Z
---

# [Issue 161]: [Integrate NIST PhysRefData / XCOM / FFAST — radiation length & X-ray attenuation](https://github.com/MorePET/mat/issues/161)

NIST X-ray databases: XCOM (photon cross-sections), FFAST (form factor / attenuation), Atomic Weights / Isotopic Compositions. US-gov, effectively public domain for redistribution; scalar fields py-mat keeps (radiation_length_cm, interaction_length_cm, mean_excitation_energy_eV) live here.

Note: tabular cross-section data goes to nucl-parquet, not py-mat (#157). Only ingest scalars into py-mat.

Reference: https://www.nist.gov/pml/xcom-photon-cross-sections-database, https://www.nist.gov/pml/x-ray-form-factor-attenuation-and-scattering-tables
