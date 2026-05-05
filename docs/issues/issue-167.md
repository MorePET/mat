---
type: issue
state: open
created: 2026-05-04T19:56:04Z
updated: 2026-05-04T19:56:04Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/167
comments: 0
labels: data-source
assignees: none
milestone: Data Sources & Licensing
projects: none
parent: none
children: none
synced: 2026-05-05T04:54:14.600Z
---

# [Issue 167]: [Mirror Geant4 G4NistManager constants (BSD-like) — composition baselines](https://github.com/MorePET/mat/issues/167)

Geant4 ships ~300 NIST compounds in `G4NistMaterialBuilder.cc` (NaI, CsI, BGO, polystyrene, plastic-scintillator base, etc). Geant4 license is BSD-like — redistributable with attribution.

Coverage: density, mean excitation energy, composition for elemental/structural baselines. Does NOT include light yield, decay, emission spectra (those need primary literature).

Action: extract canonical values for our scintillator + plastic entries; this is the upstream Geant4 itself uses, so values match what simulation code expects.

Reference: https://geant4.web.cern.ch/download/license.html
