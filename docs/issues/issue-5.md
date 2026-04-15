---
type: issue
state: closed
created: 2026-03-25T00:21:52Z
updated: 2026-03-25T00:25:17Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/5
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-04-15T04:38:29.669Z
---

# [Issue 5]: [feat: embed TOML data files in crate via include_str!()](https://github.com/MorePET/mat/issues/5)

## Summary

The TOML material data files (~50 KB total) should be embedded directly in the crate so `MaterialDb` works without an external data directory.

## Problem

Currently `MaterialDb::open(data_dir)` requires a path to TOML files, and `from_pymat_data()` only works within the py-mat monorepo (uses `CARGO_MANIFEST_DIR` to find `../src/pymat/data/`). When used as a crates.io dependency, there's no built-in way to load materials.

## Proposal

Embed all 7 category TOML files via `include_str!()`:

```rust
const METALS_TOML: &str = include_str!("../data/metals.toml");
const SCINTILLATORS_TOML: &str = include_str!("../data/scintillators.toml");
const PLASTICS_TOML: &str = include_str!("../data/plastics.toml");
const CERAMICS_TOML: &str = include_str!("../data/ceramics.toml");
const ELECTRONICS_TOML: &str = include_str!("../data/electronics.toml");
const LIQUIDS_TOML: &str = include_str!("../data/liquids.toml");
const GASES_TOML: &str = include_str!("../data/gases.toml");

impl MaterialDb {
    /// Load the built-in material database (no external files needed).
    pub fn builtin() -> Self { ... }
}
```

## Justification

- Total data size is ~50 KB — negligible impact on binary size
- The material database IS the crate's core value — shipping without it defeats the purpose
- Every downstream user (e.g. strata) would otherwise need to vendor or symlink the TOML files
- `MaterialDb::builtin()` becomes the zero-config default; `open(path)` remains for custom/extended databases

## Context

Used by [strata](https://github.com/gerchowl/strata) (Rust MC transport engine) as the material definition layer alongside nucl-parquet for cross-section data.
