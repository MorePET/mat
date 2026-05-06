# Contributing to mat (py-materials)

## Ways to contribute

### Request a material

Don't have the data? [Open a material request][request] — tell us
what you need and why. We'll source the properties from literature
and datasheets.

### Add a material

Have the data? Open a PR adding a TOML entry. Here's the template:

```toml
# src/pymat/data/<category>.toml
# Add under the appropriate category file (metals.toml, plastics.toml, etc.)

[my_material]
name = "My Material Name"
formula = "Fe3O4"                    # optional — chemical formula
composition = {Fe = 0.72, O = 0.28}  # optional — element mass fractions

[my_material.mechanical]
density_value = 5.17
density_unit = "g/cm^3"
youngs_modulus_value = 200           # optional
youngs_modulus_unit = "GPa"

[my_material.thermal]
melting_point_value = 1597           # optional
melting_point_unit = "degC"

# Visual appearance — PBR scalars + optional mat-vis texture mapping.
# Since 3.0 all visual state lives under [vis], NOT [pbr].
[my_material.vis]
base_color = [0.1, 0.1, 0.1, 1.0]   # RGBA, 0-1
metallic = 0.8                        # 0 = dielectric, 1 = metal
roughness = 0.5                       # 0 = glossy, 1 = rough
default = "natural"                  # which finish to use by default

# Since 3.1 finishes are inline tables (source + id), NOT slashed strings.
[my_material.vis.finishes]
natural = { source = "ambientcg", id = "Metal_SomeID" }
```

#### What's required

- `name` — human-readable
- `density` — in `g/cm³` (needed for `compute_mass()`)
- `[vis]` with `base_color`, `metallic`, `roughness` — for rendering

Everything else is optional. More data is better, but partial
entries are welcome — we can enrich later.

#### Hierarchy

Materials support parent → child hierarchy:

```toml
[aluminum]
name = "Aluminum"
# base properties...

[aluminum.a6061]
name = "Aluminum 6061-T6"
grade = "6061"
temper = "T6"
# only overrides — inherits everything from parent
```

### Fix a value

Spotted an error? [Open a correction issue][correction] with the
correct value and a source citation. Or open a PR directly —
edit the TOML, cite your source in the commit message.

### Improve the code

See the [open issues][issues] for bugs, features, and
refactoring tasks. The standard workflow:

1. Fork the repo
2. Create a branch from `dev`
3. Make your changes
4. Run tests: `pytest tests/ -v`
5. Run linter: `ruff check src/ tests/`
6. Open a PR against `dev`

## Data quality

- **Cite your sources.** Every property value should be traceable
  to a datasheet, handbook, or paper. Include the reference in the
  commit message or PR description.
- **Use SI-compatible units** with the `_value` / `_unit` suffix
  pattern (e.g. `density_value = 8.0`, `density_unit = "g/cm^3"`).
- **Don't fabricate values.** If a property isn't known, leave it
  out. `None` is better than a guess.
- **PBR values can be approximate.** Rendering properties are
  visual, not physical measurements. Matching "looks like steel"
  is fine.

## Visual appearance (vis)

Materials can optionally link to [mat-vis][mat-vis] textures for
PBR rendering. To find matching textures:

```python
from pymat import vis
vis.search(category="metal", tags=["brushed", "silver"])
```

Prefer searching by **tags** (brushed, silver, oak, concrete, etc.)
over category alone — tags encode the actual appearance and give
far better matches than category, which only narrows the pool.

Add the match to a `[<material>.vis.finishes]` block in the TOML.
Since 3.1 each finish is an inline table with explicit `source` + `id`
fields (matching mat-vis-client's two-positional-arg signature):

```toml
[stainless.vis.finishes]
brushed  = { source = "ambientcg", id = "Metal012" }   # first finish is the default
polished = { source = "ambientcg", id = "Metal049A" }
dirty    = { source = "ambientcg", id = "Metal049B" }
```

If you're unsure which texture to pick, `scripts/enrich_vis.py`
walks every material, tag-matches against the live mat-vis index,
and prints TOML blocks you can paste directly.

Holding a TOML with the old 3.0 slashed-string form
(`brushed = "ambientcg/Metal012"`)? Run
`python scripts/migrate_toml_finishes.py` to auto-rewrite. The loader
raises `ValueError` on the old form since 3.1 — see
[docs/migration/v2-to-v3.md](docs/migration/v2-to-v3.md).

## Nuclear data (optional extra)

`[<material>.nuclear]` holds scalar identity (`radiation_length`,
`interaction_length`, `moliere_radius`, `Z_eff`,
`mean_excitation_energy_eV`, `intrinsic_activity_Bq_per_g`).

Cross-section tables, neutron data, decay chains, activation products,
and stopping-power tables live in the
[`nucl-parquet`](https://pypi.org/project/nucl-parquet/) package — not
in py-mat. The `mat.properties.nuclear.mu_rho(energy_keV=511)` accessor
imports `nucl_parquet` lazily on first call.

To enable:

```bash
pip install 'py-materials[nuclear]'
```

Without the extra installed, `mu_rho()` raises `ImportError` with a
hint. The core schema (the scalar fields) works either way.

> Note: `nucl-parquet` requires Python 3.11+. On 3.10 the extra resolves
> to nothing and `mu_rho()` is unavailable; the scalar fields still work.

The 3 length fields previously lived on `[<material>.optical]` (in
3.x and earlier). They moved to `[nuclear]` in this release for
semantic accuracy. In-tree TOMLs migrated automatically.

## Curation tools

Curation-time utilities live in `scripts/` and are **not** runtime
deps of mat. Install their shared dependencies with:

```bash
pip install -r scripts/requirements-curation.txt
```

| Script | Purpose |
|---|---|
| `scripts/enrich_vis.py` | Propose `[vis.finishes]` blocks for unmapped materials via tag-matching against the mat-vis index |
| `scripts/enrich_from_wikidata.py` | Cross-check density + melting point of base metals against Wikidata (CC0, no auth) |
| `scripts/generate_previews.py` | Render per-material sphere/cube PBR previews (light + dark themes) via headless Three.js |
| `scripts/generate_catalog.py` | Regenerate `docs/catalog/` markdown pages; prefers rendered previews, falls back to flat thumbnails |

### Curation workflow

1. Add or edit a material in the appropriate `src/pymat/data/*.toml` file.
2. For visual mapping, run `python scripts/enrich_vis.py` to get a
   proposed `[vis.finishes]` block. Paste it into the TOML — adjust
   the finish names to match physical reality (e.g. `brushed`,
   `polished`, `oxidized`) rather than the script's generic default.
3. For metals, run `python scripts/enrich_from_wikidata.py` to
   cross-check density and melting point. Resolve any DIFF rows
   with a literature source before merging.
4. Render previews (one-time Playwright install required — see
   `scripts/requirements-curation.txt`):

   ```bash
   python scripts/generate_previews.py --changed-only
   python scripts/generate_catalog.py
   ```

   `--changed-only` parses the git diff against `origin/main` and
   re-renders only the materials whose TOML category changed. Drop
   the flag for a full regen (~3 min for 66 images at 512px).
5. Run `pytest tests/` and commit.

CI re-runs previews automatically on any PR touching `src/pymat/data/`,
`src/pymat/vis/`, the render HTML, or the curation scripts. The
`Catalog Previews` workflow uploads the rendered pages as a
downloadable artifact for review.

### Provenance

Use the `[<material>._sources]` table to attach structured citations
to property values. Every entry MUST include a `license` field
([§ Allowed licenses](docs/data-policy.md#allowed-licenses)).

```toml
[aluminum.al6061.mechanical]
density_value = 2.70
density_unit = "g/cm^3"

[aluminum.al6061._sources._default]
citation = "asm_handbook_v2"
kind = "handbook"
ref = "ASM Handbook vol.2 p.62"
license = "proprietary-reference-only"

[aluminum.al6061._sources."mechanical.density"]
citation = "wikidata_aluminum"
kind = "qid"
ref = "Q663"
license = "CC0"
```

`mat.cite("density")` then emits a BibTeX entry; `mat.source_of(...)`
returns the `Source` record. The `_default` entry is the fallback
when no per-property source is set. Inheritance: child material
sources overlay parent sources.

**Allowed `license` values**: `CC0`, `PD-USGov`, `CC-BY-4.0`,
`CC-BY-SA-4.0`, `proprietary-reference-only`. The transitional
value `unknown` is parseable but **blocked at merge** by
`scripts/check_licenses.py` (CI gate).

**Off-limits sources** and the full policy: see
[docs/data-policy.md](docs/data-policy.md). Single-value citations
from proprietary sources (vendor datasheets, ASM Handbook) are OK
with `license = "proprietary-reference-only"`. **Bulk-pasting tables
is never allowed** — see the off-limits list.

Don't fabricate provenance — if you measured it or took it from a
datasheet, say so.

[request]: https://github.com/MorePET/mat/issues/new?template=material-request.yml
[correction]: https://github.com/MorePET/mat/issues/new?template=material-correction.yml
[issues]: https://github.com/MorePET/mat/issues
[mat-vis]: https://github.com/MorePET/mat-vis
