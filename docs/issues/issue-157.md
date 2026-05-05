---
type: issue
state: open
created: 2026-05-04T19:50:32Z
updated: 2026-05-04T19:50:33Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/157
comments: 0
labels: enhancement, schema
assignees: none
milestone: Properties Schema Expansion
projects: none
parent: none
children: none
synced: 2026-05-05T04:54:18.426Z
---

# [Issue 157]: [Schema: new `nuclear` sub-table — scalar identity only (delegate tables to nucl-parquet)](https://github.com/MorePET/mat/issues/157)

Move radiation_length / interaction_length / moliere_radius (currently miscategorized under `optical`) into a new `[<material>.nuclear]` sub-table. Add: `Z_eff`, `mean_excitation_energy_eV` (Geant4 `SetMeanExcitationEnergy`), `intrinsic_activity_Bq_per_g` (LYSO 176Lu ≈ 39).

**Out of scope — delegate to nucl-parquet**: mass attenuation tables, neutron cross-sections, decay chains, activation products, stopping power. Add lazy accessor `mat.nuclear.mu_rho(energy_keV=511)` that imports nucl-parquet on first use; data downloaded via `nucl_parquet.download()` to ~/.nucl-parquet/ (50 KB pip loader, data fetched on demand). Declare as optional extra: `pip install py-mat[nuclear]`. Document the boundary in CONTRIBUTING.md.
