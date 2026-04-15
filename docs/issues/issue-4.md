---
type: issue
state: closed
created: 2026-03-24T22:15:02Z
updated: 2026-03-25T00:23:53Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/4
comments: 1
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-04-15T04:38:29.930Z
---

# [Issue 4]: [feat: Rust crate (mat-rs) for material database + formula parsing](https://github.com/MorePET/mat/issues/4)

## Summary

Create a lightweight Rust crate that exposes py-mat's material database and formula parsing for use in Monte Carlo particle transport engines (specifically [strata](https://github.com/gerchowl/strata)).

## Motivation

strata (Rust MC transport engine) needs material definitions at runtime:
- Density, formula, elemental composition (for cross-section lookups via nucl-parquet)
- Optical/scintillator properties (refractive index, light yield, decay time, emission peak)
- Standard materials (LYSO, BGO, water, tissue, bone, air, etc.)

Currently this data lives in py-mat's TOML files and is only accessible from Python. A Rust crate would enable strata to load materials without a Python intermediary.

## Scope

### In scope (port to Rust)
- **TOML material database reader** — parse `metals.toml`, `scintillators.toml`, `plastics.toml`, `ceramics.toml`, `electronics.toml`, `liquids.toml`, `gases.toml`
- **Material struct** — density, formula, elemental composition, optical properties
- **Formula parser** — `"Lu1.8Y0.2SiO5"` → `[(Lu, 1.8), (Y, 0.2), (Si, 1.0), (O, 5.0)]` (currently in hyrr, not py-mat)
- **Mass fraction ↔ atom fraction conversion** (currently in hyrr)
- **Scintillator properties struct** — light_yield (photons/MeV), decay_time (ns), emission_peak (nm), refractive_index

### Out of scope
- build123d/CAD integration (Python-only)
- PBR rendering properties
- Manufacturing/compliance/sourcing properties
- Pint unit system (use plain f64 with documented units)
- periodictable/pymatgen enrichment

## Proposed API

```rust
use mat_rs::{MaterialDb, Material};

let db = MaterialDb::open("path/to/py-mat/data")?;  // reads TOML files

let lyso = db.get("lyso")?;
assert_eq!(lyso.density(), 7.1);  // g/cm³
assert_eq!(lyso.formula(), "Lu1.8Y0.2SiO5");

let fractions = lyso.mass_fractions();  // Vec<(Element, f64)>
let optical = lyso.optical().unwrap();
assert_eq!(optical.light_yield, 32000.0);  // photons/MeV
assert_eq!(optical.refractive_index, 1.82);

// Formula parsing (standalone, no DB needed)
let elems = mat_rs::parse_formula("Lu1.8Y0.2SiO5")?;
// → [(Lu, 1.8), (Y, 0.2), (Si, 1.0), (O, 5.0)]
let mass_fracs = mat_rs::to_mass_fractions(&elems)?;
```

## Integration

- **Standalone crate** (not bundled into nucl-parquet) — material identity is a separate concern from physics data
- strata-materials would depend on both `mat-rs` (what is LYSO?) and `nucl-parquet` (what's the Compton XS of Lu?)
- `Send + Sync` — load once, share via `Arc`

## Dependencies

Minimal: `serde`, `toml`, `thiserror`. No FFI, no Python.
---

# [Comment #1]() by [gerchowl]()

_Posted on March 25, 2026 at 12:23 AM_

Implemented in 82630d4, published as rs-materials v0.1.0 on crates.io.

