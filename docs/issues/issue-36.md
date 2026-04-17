---
type: issue
state: open
created: 2026-04-16T19:54:12Z
updated: 2026-04-16T19:54:12Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/36
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-04-17T04:41:58.930Z
---

# [Issue 36]: [Data enrichment sources: Materials Project, Wikidata, NIST, etc.](https://github.com/MorePET/mat/issues/36)

## Context

Several external databases can enrich mat's TOML data at
**curation time** — adding physical properties, cross-references,
or validation data. These are NOT runtime dependencies. They're
tools that run once during data curation, and the results get
committed to the TOMLs.

## Sources to investigate

| Source | What it provides | License | Access |
|---|---|---|---|
| [Materials Project](https://next-gen.materialsproject.org) | Crystal structure, band gap, elasticity, thermodynamics | CC-BY-4.0 | API key required |
| [Wikidata](https://www.wikidata.org) | Cross-references, CAS numbers, density, melting point | CC0 | SPARQL, no auth |
| [NIST SRD](https://www.nist.gov/srd) | Reference physical constants, X-ray attenuation, stopping power | Public domain (US govt) | Varies by dataset |
| [PubChem](https://pubchem.ncbi.nlm.nih.gov) | Chemical properties, safety data, synonyms | Public domain | REST API, no auth |
| [KittyCAD/material-properties](https://github.com/KittyCAD/material-properties) | Mechanical props for common engineering materials | Apache-2.0 | JSON files on GitHub |

## How it works

A curation script (not shipped in the wheel, lives in `scripts/`
or a separate tool):

1. Queries the external source for a specific material
2. Extracts relevant fields (density, yield_strength, etc.)
3. Merges into the existing TOML, flagging source + date
4. Reviewer approves the TOML change via PR

No `pymatgen` or API client in mat's dependencies. The curation
script has its own requirements (possibly a `scripts/requirements-curation.txt`).

## Acceptance

- [ ] Survey which sources have usable APIs + acceptable licenses
- [ ] Prototype one enrichment script (e.g. Wikidata → density
      for metals that are missing it)
- [ ] Document the curation workflow in CONTRIBUTING.md
- [ ] Track provenance in TOML comments or a metadata field

## Not in scope

- Runtime API calls to any external database
- Any of these as pip dependencies of mat
- pymatgen as an extra (dropped per #34 discussion)
