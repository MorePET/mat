---
type: issue
state: open
created: 2026-04-16T19:54:12Z
updated: 2026-04-18T10:26:40Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/36
comments: 1
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-04-19T04:44:09.015Z
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
---

# [Comment #1]() by [gerchowl]()

_Posted on April 18, 2026 at 10:26 AM_

Progress — first prototype landed: [`scripts/enrich_from_wikidata.py`](scripts/enrich_from_wikidata.py) (commit b649e87).

**What it does**
- SPARQL against `query.wikidata.org` for the 7 base metals (Al, Cu, Ti, W, Pb, brass, stainless)
- Cross-checks `density` (P2054) and `melting_point` (P2101) against mat's TOML values
- Normalizes units (g/cm³ ↔ kg/m³, K ↔ °C)
- Flags relative divergence >5% per cell

**No runtime impact** — lives in `scripts/`, pulls in only `requests` via a new `scripts/requirements-curation.txt`. mat's runtime deps are untouched.

**First-run findings**
```
aluminum   OK   ours=2.7    wd=2.7      Δ=0       (0.0%)
copper     OK   ours=8.96   wd=8.94     Δ=0.02    (0.2%)
tungsten   DIFF ours=19.3   wd=7.2      Δ=12.1    (62.7%)   ← Wikidata wrong
lead       OK   ours=11.34  wd=11.34    Δ=0       (0.0%)
brass      OK   ours=8.5    wd=8.56     Δ=0.06    (0.7%)
titanium   wd missing
stainless  wd missing
```
Tungsten divergence is a Wikidata data-quality issue (pure W is 19.25 g/cm³, Wikidata has 7.2 with NormalRank only). The tool correctly surfaces it for review rather than auto-merging — this is exactly the behavior we want.

**Checkbox update (from the issue body)**
- [x] Survey which sources have usable APIs + acceptable licenses → Wikidata validated (CC0, no auth, SPARQL works)
- [x] Prototype one enrichment script → Wikidata for metals
- [ ] Document the curation workflow in CONTRIBUTING.md
- [ ] Track provenance in TOML comments or a metadata field

**Next candidates** (pick one next round):
- PubChem for plastic chemical properties (formula / CAS cross-check)
- KittyCAD/material-properties for mechanical props cross-check on alloys
- Decide on a `[source]` or comment convention for provenance tracking

