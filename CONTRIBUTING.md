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

[my_material.pbr]
base_color = [0.1, 0.1, 0.1, 1.0]   # RGBA, 0-1
metallic = 0.8                        # 0 = dielectric, 1 = metal
roughness = 0.5                       # 0 = glossy, 1 = rough

# Visual appearance mapping (optional — mat-vis must have matching textures)
[my_material.vis]
default = "natural"

[my_material.vis.finishes]
natural = "ambientcg/Metal_SomeID"    # mat-vis source ID
```

#### What's required

- `name` — human-readable
- `density` — in `g/cm³` (needed for `compute_mass()`)
- `base_color`, `metallic`, `roughness` — for rendering

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
vis.search(category="metal", roughness=0.3)
```

Add the match to the `[vis]` section of the TOML. If you're
unsure, leave it out — the `enrich_vis.py` script proposes
matches automatically.

[request]: https://github.com/MorePET/mat/issues/new?template=material-request.yml
[correction]: https://github.com/MorePET/mat/issues/new?template=material-correction.yml
[issues]: https://github.com/MorePET/mat/issues
[mat-vis]: https://github.com/MorePET/mat-vis
