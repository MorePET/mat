---
type: issue
state: open
created: 2026-05-04T19:50:25Z
updated: 2026-05-04T19:50:25Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/153
comments: 0
labels: enhancement, schema
assignees: none
milestone: Properties Schema Expansion
projects: none
parent: none
children: none
synced: 2026-05-05T04:54:20.006Z
---

# [Issue 153]: [Schema: optical sub-table additions (scintillator-heavy)](https://github.com/MorePET/mat/issues/153)

Add to `optical`: `scattering_length` + `rayleigh_length` (cm — Geant4 needs these, currently entirely missing), `decay_components = [{tau_ns, fraction}, ...]` (LYSO has fast+slow components, scalar loses TOF info), `emission_spectrum = {wavelengths_nm, intensities}` (for SiPM PDE matching), `refractive_index_dispersion = {wavelengths_nm, n}` (Sellmeier-style for Geant4 ray tracing), `afterglow_pct_at_3ms` / `afterglow_pct_at_100ms` (count-rate ceiling), `non_proportionality` (% deviation 10 keV → 1 MeV), `intrinsic_resolution_pct_at_662keV`, `temperature_coefficient_light_yield` (%/K), `hygroscopic` (bool).
