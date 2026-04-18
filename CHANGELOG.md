# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Breaking

* **Removed `material.properties.pbr` / `PBRProperties`.** All PBR scalars (`base_color`, `metallic`, `roughness`, `ior`, `transmission`, `clearcoat`, `emissive`) live on `material.vis` now. See [docs/migration/v2-to-v3.md](docs/migration/v2-to-v3.md) for the full rename table.
* **Removed `Material(pbr={...})` kwarg.** Use `Material(vis={...})` instead — same shape.
* **Removed `[<material>.pbr]` TOML section.** The loader raises `ValueError` on it. Bundled TOMLs already use `[<material>.vis]`; external TOMLs need to rename the block.
* **Removed legacy texture-path fields** (`normal_map`, `roughness_map`, `metallic_map`, `ambient_occlusion_map`) from what was `PBRProperties`. Use `material.vis.textures["color"|"normal"|"roughness"|…]` — lazy-fetched bytes from mat-vis.
* **Removed `PBRProperties` from `pymat` top-level imports**.
* **`mat-vis-client` floor raised to `>=0.4.0`.** Users with a warm `mat-vis-client` 0.2.x cache need to run `mat-vis-client cache clear` once — the 0.3.x manifest format requires `schema_version`. See the [v2-to-v3 migration guide](docs/migration/v2-to-v3.md#mat-vis-client-upgrade) for details.
* Internal: `Material._sync_vis_to_pbr()` deleted (the back-compat shim that kept `.vis` and `.properties.pbr` in sync). `AllProperties` no longer has a `pbr` field or property.
* No 2.3 deprecation-cycle release was shipped. The rationale is in [issue #40](https://github.com/MorePET/mat/issues/40).

### Added

* `pymat.vis.search()` now accepts a `tags=[...]` parameter that filters the index by tag-subset. Tag matches (`brushed`, `silver`, `oak`, `concrete`) produce far tighter vis assignments than category-alone — the previous category-only heuristic was effectively random.
* `pymat.vis.client()` factory exposes the lazy-initialized `MatVisClient` singleton. Future-proofs against new methods added upstream — any new `MatVisClient` capability is usable via `vis.client().new_method(...)` without a py-mat release.
* Curated `[vis.finishes]` mappings for 33 materials covering metals (stainless, aluminum, copper, titanium, brass, tungsten, lead), plastics (peek, delrin, ultem, ptfe, nylon, pla, abs, petg, tpu, vespel, torlon, pctfe, pmma, pe, pc), ceramics (alumina, zirconia, sic, macor, shapal, beryllia, yttria), electronics (copper_pcb, solder), and scintillators (plastic_scint). PLA and ABS carry full color variants (white/black/red/blue/green) matching 3D-printed reality.
* `_CATEGORY_BASES["ceramics"]` extended with `sic`, `shapal`, `beryllia`, `yttria` — they existed in `ceramics.toml` but never appeared in the catalog index.
* `scripts/enrich_from_wikidata.py` — cross-checks `density` + `melting_point` of base metals and plastics against Wikidata (CC0, no auth, SPARQL). Normalizes units (g/cm³ ↔ kg/m³, K ↔ °C) and flags relative divergence >5%. First run surfaced a Wikidata data-quality issue (tungsten listed as 7.2 g/cm³).
* `scripts/requirements-curation.txt` — isolates curation-time deps (`requests`) from runtime deps.
* `.github/workflows/visual-regression.yml` — runs the headless Three.js render tests on PRs touching `src/pymat/vis/**` or the adapter/test/HTML files. Installs Chromium via `playwright install --with-deps` and uploads rendered `.png` files + adapter JSON as artifacts.
* New tests covering the previously-untested vis.search paths: tag-subset filter, roughness/metalness range filters, scoring by scalar distance, source-iteration error swallowing, and the `vis.client()` factory. Brings `src/pymat/vis/__init__.py` from 75% to 100% line coverage.
* Catalog regenerated with 33 material thumbnails (128px, pre-baked from mat-vis's thumbnail tier).

### Changed

* `scripts/enrich_vis.py` walks the `Material._children` hierarchy top-down instead of the flat `load_all()` dict. Emits correct dotted TOML paths (`solder.Sn63Pb37` not bare `Sn63Pb37`) and skips descendants of already-mapped bases. Proposal count dropped from 40 (noisy) to 6 (all legitimate gaps).
* `CONTRIBUTING.md` — added a Curation tools table (enrich_vis, enrich_from_wikidata, generate_catalog), a step-by-step curation workflow, and an inline-comment provenance convention (`# density: Wikidata Q663, CC0`) so source attribution survives TOML reformatting.
* `tests/test_e2e_vis.py::test_toml_material_with_vis_mapping` loosened — no longer pins the polished finish to a specific ambientcg id; just verifies the id changes and stays within ambientcg/Metal*.

## [2.1.1](https://github.com/MorePET/mat/compare/v2.1.0...v2.1.1) (2026-04-18)

### Fixed

* **ci:** correct release-please extra-file type and manifest baseline ([#46](https://github.com/MorePET/mat/issues/46)) ([30208d0](https://github.com/MorePET/mat/commit/30208d0477a1c36410565a25ff50a3aab581203c)), closes [#43](https://github.com/MorePET/mat/issues/43)

## [2.1.0] - 2026-04-15

### Added

* `Material.molar_mass` computed `@property`, parsed from `self.formula` via a new local `pymat.elements.ATOMIC_WEIGHT` table that mirrors `rs-materials` for Python ↔ Rust parity. Supports fractional stoichiometry (`Lu1.8Y0.2SiO5`) and strips dopant suffixes (`LYSO:Ce` → `LYSO`).
* `Material.molar_mass_qty` — Pint-wrapped companion accessor following the existing `*_qty` pattern on other properties.
* `pymat.elements` module with `ATOMIC_WEIGHT`, `parse_formula()`, and `compute_molar_mass()`.
* Python 3.10 support via `tomli` shim in `src/pymat/loader.py`. Contributed by @bernhard-42 in [#6](https://github.com/MorePET/mat/pull/6), our first outside contribution.
* `Python :: 3.13` classifier.
* `docs/decisions/` — ADR infrastructure (Architectural Decision Records). First entry: `0001-derived-chemistry-properties-live-on-material.md` documents why derived chemistry properties live on `Material` as computed `@property` accessors rather than inside a new property group.

### Changed

* `requires-python` relaxed from `>=3.11` to `>=3.10`.
* `build123d` / `dev` / `all` extras now carry environment marker `python_version<'3.13'` so `pip install py-materials[build123d]` on Python 3.13+ silently drops `build123d` instead of erroring on missing `cadquery-ocp` / `vtk` wheels. The core library works on 3.13+; only the optional visualisation path is gated.
* `enrich_from_periodictable` docstring rewritten: now explicitly states that compound density is **not** derivable from periodictable (only pure elements have it). The code path is unchanged — it was already a no-op for compounds — but the previous docstring promised behavior that never worked. Use `enrich_from_matproj` for compound density instead.
* `enrich_from_periodictable` uses `logger.warning` for invalid formulas instead of `print`.
* `ImportError` in enrichers is now properly chained via `raise ... from e`.

### Fixed

* `src/pymat/__init__.py` `__version__` synced to `2.1.0` (was stuck at `2.0.4` after the 2.0.5 release — the file had never been updated alongside `pyproject.toml`).
* `uv.lock` regenerated for the `py-mat` → `py-materials` package rename from `cf4db36`. CI had been silently broken on `uv sync --frozen` since the rename because the lockfile still referenced the old package name; this PR makes `--frozen` usable again.
* Three latently-broken tests in `tests/test_enrichers.py` rewritten to check the behavior that actually works (composition extraction + computed molar mass via `Material.molar_mass`). Previously they were marked `xfail(strict=True)` as a stopgap; they are now proper passes.

### Infrastructure (not user-facing)

* Adopted the vigOS `dev` / `main` branching convention with GitHub rulesets. `main` and `dev` both require PRs with passing CI; force-push and deletion blocked; `commit-action-bot` and `vig-os-release-app` plus org/repo admins are in the bypass list.
* CI matrix expanded to Python 3.10 / 3.11 / 3.12 / 3.13, all with `--all-extras`. `build123d` installs on 3.10–3.12 and silently drops on 3.13+ via the environment marker.
* New `Rust (mat-rs)` PR-CI gate running `cargo fmt --check`, `cargo clippy -D warnings`, and `cargo test`. Previously the crate only ran in `release-rs-materials.yml` on tag push, so broken Rust changes could land undetected.
* `.typos.toml` added: ignores single/double-letter chemical element symbols and the `Macor` product name. Without this, the `typos` pre-commit hook would auto-"correct" `Nd` (Neodymium) → `And` in `mat-rs/src/elements.rs`, `Macor` (Corning brand) → `Macro` in the README + CHANGELOG + ceramics.toml, and similar damage across the repo.
* `sync-main-to-dev.yml` conflict detection switched from `git merge --no-commit --no-ff` to `git merge-tree --write-tree`. The old approach reported false-positive conflicts on degenerate merges (one side an ancestor of the other — which happens after every `dev → main` PR).
* Template refresh: bumped `github/codeql-action` pins in `codeql.yml` + `scorecard.yml`, bumped `actions/create-github-app-token` v2 → v3 in `sync-issues.yml`, bumped `vig-os/commit-action` v0.1.5 → v0.2.0 with `MAX_ATTEMPTS: "3"`.
* Dependabot security updates applied: `requests` 2.32.5 → 2.33.0 (CVE-2026-25645), `pillow` 12.1.1 → 12.2.0, `pygments` 2.19.2 → 2.20.0, `pytest` 9.0.2 → 9.0.3.
* `RELEASE_PROCESS.md` and `TEMPERATURE_UNITS_IMPLEMENTATION.md` rewritten to satisfy `pymarkdown` MD031 (upstream has a known fixer bug with fenced code blocks nested in list items — tracked in jackdewinter/pymarkdown#1568, fix merged but unreleased).

## [rs-materials 0.2.0] - 2026-03-25

### Added
* `MaterialDb::builtin()` — zero-config constructor with all TOML data embedded via `include_str!()`
* No external data directory needed when used as a crates.io dependency

## [rs-materials 0.1.0] - 2026-03-25

### Added
* Initial Rust crate for material database and formula parsing
* `MaterialDb::open(path)` — loads all 7 TOML category files with property inheritance
* `parse_formula()` — fractional stoichiometry support (e.g. `Lu1.8Y0.2SiO5`)
* `formula_to_mass_fractions()`, `mass_to_atom_fractions()`, `atom_to_mass_fractions()`
* `Material` struct with density, formula, composition, `OpticalProperties`
* `Send + Sync` for `Arc` sharing in multi-threaded transport engines
* Separate release workflow triggered on `rs-materials/v*` tags

## [2.0.4] - 2025-01-08

### Fixed
* **Fixed plastics.toml** to use explicit `*_value` and `*_unit` format for all properties
  * Eliminates "No unit specified" warnings on import

## [2.0.3] - 2025-01-08

### Fixed
* **Added explicit `transmission` to all PBR sections** in TOML data files
  * Metals, electronics: `transmission = 0.0` (opaque)
  * Plastics: opaque except PMMA (0.9) and PC (0.85)
  * Ceramics: opaque except glass (0.9) and BK7 (0.95)
  * Gases, liquids, scintillators: already had correct transparency values
* **Added transparency tests** for `apply_to()` to verify alpha is correctly derived from transmission

## [2.0.2] - 2025-01-08

### Fixed
* **Added `build123d` to dev dependencies** - enables running build123d integration tests
* **Fixed test case sensitivity** - path assertions now match TOML key casing (e.g., `s316L`)

## [2.0.1] - 2025-01-08

### Fixed
* **Corrected alpha calculation from transmission** in `apply_to()`
  * Alpha is now correctly calculated as `1 - transmission` (not `transmission`)
  * `transmission=0.0` (opaque) → `alpha=1.0`
  * `transmission=0.9` (90% transparent) → `alpha=0.1`
* **Simplified color assignment logic** - removed confusing fallback to `base_color[3]`

## [2.0.0] - 2025-01-08

### BREAKING CHANGES
* **Unit-aware TOML format**: All material data files now use explicit `*_value` and `*_unit` pairs
  * Example: `density = 8.0` → `density_value = 8.0` + `density_unit = "g/cm^3"`
  * This enables proper unit tracking and conversion via Pint
* **Pint dependency required**: `pint>=0.20` is now a required dependency
* **Updated all TOML data files** to use the new explicit unit format for consistency
* **Property dataclasses now include `*_unit` fields** for all unit-aware properties

### Added
* **Unit-aware properties with Pint integration**
  * All physical properties now have corresponding `*_qty` accessors returning Pint Quantities
  * Example: `material.properties.mechanical.density_qty` returns `Quantity(8.0, 'g/cm^3')`
  * Enables automatic unit conversion: `density_qty.to('kg/m^3')`

* **Temperature-dependent property calculations**
  * `thermal.thermal_conductivity_at(temp)` calculates k at given temperature
  * Uses reference temperature and linear coefficient for interpolation
  * Example: `k_at_100c = thermal.thermal_conductivity_at(373.15 * ureg.kelvin)`

* **Standard units module** (`pymat.units`)
  * Exports `ureg` (Pint UnitRegistry) for unit-aware calculations
  * Defines `STANDARD_UNITS` mapping for default units

* **Automatic PBR property defaulting from optical properties (DRY principle)**
  * `pbr.ior` now defaults to `optical.refractive_index` if not explicitly set
  * `pbr.transmission` now defaults to `optical.transparency / 100.0` if not explicitly set

* **Enhanced build123d transparency support**
  * `apply_to()` now properly applies `pbr.transmission` to build123d shape color alpha channel

### Changed
* All TOML data files updated to explicit unit format for v2.0.0 compatibility
* Property classes now include `*_unit` fields with sensible defaults
* Loader handles both legacy (single value) and new (value/unit pair) formats
* PBR properties now derive sensible defaults from optical (physics) properties

### Technical Details
* All 7 TOML data files (metals, plastics, ceramics, scintillators, electronics, liquids, gases) updated
* Backward compatibility: loader will auto-assign standard units for legacy format with warning
* Unit-aware `*_qty` properties return `None` if base value is `None`
* Temperature calculations use Kelvin internally to avoid Pint offset unit issues

## [1.1.0] - 2025-01-08

### Added
* **Automatic PBR property defaulting from optical properties (DRY principle)**
  * `pbr.ior` now defaults to `optical.refractive_index` if not explicitly set
  * `pbr.transmission` now defaults to `optical.transparency / 100.0` if not explicitly set
  * Eliminates redundancy while preserving ability to override for visualization purposes

* **Enhanced build123d transparency support**
  * `apply_to()` now properly applies `pbr.transmission` to build123d shape color alpha channel
  * Converts transmission (0-1 scale) directly to RGBA alpha for correct visualization
  * Fallback to `base_color` alpha if transmission not used
  * Ensures consistent transparency behavior across all material types

### Changed
* PBR properties now derive sensible defaults from optical (physics) properties
* build123d color assignment now includes transparency from `pbr.transmission`
* Material initialization order: explicit properties first, then apply defaults
* Better separation of concerns: physics drives rendering unless explicitly overridden

### Technical Details
* Defaulting logic in `Material.__post_init__()` checks for default values (ior==1.5, transmission==0.0)
* Only applies defaults when values are at defaults, preserving explicit overrides
* `apply_to()` logic refactored for clearer transparency handling
* All existing tests pass, new features verified with comprehensive tests

## [1.0.0] - 2025-01-08

### BREAKING CHANGES
* Material constructor now accepts property groups as keyword arguments (mechanical={}, thermal={}, optical={}, pbr={}, etc.)
* Clearer separation: **Optical properties** (physics/measured) are now separate from **PBR properties** (visualization/rendering)
* `density` and `color` remain as convenience parameters for backward compatibility
* Manual `__init__` approach replaced with `@dataclass` + comprehensive `__post_init__` handling

### Added
* Property group kwargs in Material constructor for all property domains
* Auto-generated README from integration tests (doc-as-tested-code paradigm)
* Comprehensive test suite `test_readme_examples.py` with 40+ examples
* README generator script (`scripts/generate_readme.py`)
* README template with clear documentation (`docs/README_TEMPLATE.md`)
* Improved docstrings clarifying optical (physics) vs PBR (visualization) distinction
* Full documentation of constructor usage patterns

### Changed
* Material constructor is now more flexible and discoverable
* All property groups can be set during initialization
* Better separation of concerns between physics and visualization properties
* Improved error handling in `apply_to()` method (already in v0.1.2)

### Documentation
* Comprehensive README generated from tested examples
* Clear examples for all major features
* Property group usage patterns documented
* Material category overview

## [0.1.2] - 2025-01-08

### Added
* Comprehensive error handling in `Material.apply_to()` method
* Support for applying materials to any object (not just build123d Shapes)
* New test suite `test_apply_to.py` with error handling tests
* Graceful fallback for non-Shape objects (only sets `.material` attribute)

### Changed
* `apply_to()` now works with custom objects, setting only the `.material` attribute
* Better error messages for immutable objects with helpful messages
* Type hints updated to use `TypeVar` for generic object support

### Fixed
* No longer crashes when applying material to objects without `volume` or `color` attributes
* Proper TypeError raised for immutable objects with helpful messages

## [0.1.1] - 2025-01-08

### Added
* **Gases category** with common gases and cryogenic liquids
* Air, Nitrogen (N2), Oxygen (O2), Argon, CO2, Helium, Hydrogen, Neon, Xenon, Methane
* Cryogenic variants: Liquid Nitrogen, Liquid Helium, Dry Ice
* Vacuum material (for reference)
* Properties at STP (20°C, 1 atm) by default
* Use `factories.air(temp, pressure)` for temperature/pressure-dependent properties

### Changed
* Updated README with gases category
* Added gases to material registry

## [0.1.0] - 2025-01-08

### Added
* Initial release of hierarchical material library
* **Core Features**:
  * Chainable material hierarchy (grades, tempers, treatments, vendors)
  * Property inheritance through hierarchy
  * Lazy loading of material categories
  * TOML-based material definitions
  * build123d integration with `apply_to()` and automatic mass calculation
  * PBR rendering properties for visualization

* **Material Categories**:
  * **Metals**: Stainless steel (304, 316L, 17-4 PH), Aluminum (6061, 7075, 2024), Copper (OFHC), Tungsten, Lead, Titanium, Brass
  * **Scintillators**: LYSO (Ce-doped, vendor variants), BGO, NaI(Tl), CsI (Tl, Na), LaBr3, PWO, Plastic scintillators
  * **Plastics**: PEEK, Delrin, Ultem, PTFE, ESR (3M Vikuiti), Nylon, PLA, ABS, PETG, TPU, Vespel, Torlon, PCTFE, PMMA, PE (HDPE, LDPE, UHMWPE), PC
  * **Ceramics**: Alumina (99.5%, 99.9%), Macor, Zirconia, Glass (borosilicate, fused silica, BK7), Beryllia, Yttria
  * **Electronics**: FR4, Rogers (4350B), Kapton, Copper PCB (1oz, 2oz, gold-plated), Solder (Sn63Pb37, SAC305), Ferrite, Epoxy potting
  * **Liquids**: Water (20°C default), Heavy Water (D2O), Mineral Oil, Glycerol, Silicone Oil, Ice

* **Property Groups**:
  * Mechanical: density, Young's modulus, yield strength, hardness, etc.
  * Thermal: melting point, thermal conductivity, expansion coefficient
  * Electrical: resistivity, conductivity, dielectric constant
  * Optical: refractive index, transparency, light yield (scintillators)
  * PBR: base color, metallic, roughness (for visualization)
  * Manufacturing: machinability, printability, weldability
  * Compliance: RoHS, REACH, food-safe, biocompatible
  * Sourcing: cost, availability, suppliers

* **Advanced Features**:
  * `periodictable` integration for formula-based property enrichment
  * Factory functions for temperature-dependent materials:
    * `water(temperature_c)` - water at specific temperature (0-100°C)
    * `air(temperature_c, pressure_atm)` - air at specific conditions
    * `saline(concentration_pct, temperature_c)` - saline solutions
  * Direct material access via registry
  * Full pytest test suite

* **Documentation**:
  * Comprehensive README with usage examples
  * Release process documentation with `latest` tag pattern
  * MIT License

### Technical Details
* Built with `hatchling` for easy installation
* Compatible with `uv` package manager
* Requires Python >= 3.11
* Optional dependencies: `periodictable`, `pymatgen`, `build123d`

---

## Release Notes

### Version Numbering
This project uses [Semantic Versioning](https://semver.org/):
* **MAJOR** version for incompatible API changes
* **MINOR** version for new features (backward compatible)
* **PATCH** version for bug fixes (backward compatible)

### Installation

```bash
# Install latest release
uv add git+https://github.com/MorePET/py-mat.git@latest

# Install specific version
uv add git+https://github.com/MorePET/py-mat.git@v2.0.1
```

### Links
* **GitHub**: https://github.com/MorePET/py-mat
* **Issues**: https://github.com/MorePET/py-mat/issues

[2.0.1]: https://github.com/MorePet/py-mat/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/MorePet/py-mat/compare/v1.1.0...v2.0.0
[1.1.0]: https://github.com/MorePet/py-mat/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/MorePet/py-mat/compare/v0.1.2...v1.0.0
[0.1.2]: https://github.com/MorePet/py-mat/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/MorePet/py-mat/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/MorePet/py-mat/releases/tag/v0.1.0
