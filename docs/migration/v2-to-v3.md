# Migrating from 2.x to 3.0

py-materials 3.0 consolidates all PBR (physically-based rendering)
state under `material.vis`. `material.properties.pbr`, `PBRProperties`,
the `pbr={...}` constructor kwarg, and the TOML `[pbr]` section are
all removed.

The rationale — and the decision to skip a 2.3 deprecation cycle — is
tracked in [issue #40](https://github.com/MorePET/mat/issues/40).

## Rename cheat sheet

| 2.x | 3.0 |
|---|---|
| `material.properties.pbr.roughness` | `material.vis.roughness` |
| `material.properties.pbr.metallic` | `material.vis.metallic` |
| `material.properties.pbr.base_color` | `material.vis.base_color` |
| `material.properties.pbr.ior` | `material.vis.ior` |
| `material.properties.pbr.transmission` | `material.vis.transmission` |
| `material.properties.pbr.emissive` | `material.vis.emissive` |
| `material.properties.pbr.clearcoat` | `material.vis.clearcoat` |
| `Material(name="X", pbr={...})` | `Material(name="X", vis={...})` |
| `[material.pbr]` in TOML | `[material.vis]` |
| `from pymat import PBRProperties` | *removed — no replacement needed* |
| `properties.pbr.normal_map` | `material.vis.textures["normal"]` |
| `properties.pbr.roughness_map` | `material.vis.textures["roughness"]` |
| `properties.pbr.metallic_map` | `material.vis.textures["metallic"]` |
| `properties.pbr.ambient_occlusion_map` | `material.vis.textures["ao"]` |

## What stays the same

- Every other property group (`mechanical`, `thermal`, `electrical`,
  `optical`, `manufacturing`, `compliance`, `sourcing`) is unchanged.
- `material.density`, `material.molar_mass`, `material.apply_to(shape)`,
  `material.grade_()` / `.treatment_()` / `.temper_()` — all unchanged.
- `AllProperties()`, `load_toml(path)`, `load_category(name)` —
  unchanged.
- Direct-access materials (`from pymat import stainless, aluminum, …`)
  — unchanged.
- Factory functions (`water(t)`, `air(t, p)`, `saline(pct, t)`) —
  unchanged API; internally they now emit `vis={...}` in their
  `Material(...)` call, which is invisible at the callsite.

## TOML data

Our bundled TOMLs already carry PBR scalars in `[<material>.vis]`
sections (this was the 2.x migration). If you maintain your own
TOML files with `[<material>.pbr]` sections, move the contents
under `vis` — the loader raises `ValueError` on a `[pbr]` section
in 3.0.

```toml
# Before (2.x)
[my_material.pbr]
base_color = [0.8, 0.8, 0.8, 1.0]
metallic = 1.0
roughness = 0.3

# After (3.0)
[my_material.vis]
base_color = [0.8, 0.8, 0.8, 1.0]
metallic = 1.0
roughness = 0.3
```

## Texture maps

The legacy path-string fields (`normal_map`, `roughness_map`,
`metallic_map`, `ambient_occlusion_map`) on `PBRProperties` are
removed. They predated the `mat-vis` client and weren't used by
anything in the library for several releases. The modern equivalent
is a `[<material>.vis]` block with a `source_id` pointing at a
mat-vis entry — textures are then lazy-fetched as bytes:

```toml
[stainless.vis.finishes]
brushed = "ambientcg/Metal012"
polished = "ambientcg/Metal049A"
```

```python
from pymat import stainless
color_png_bytes = stainless.vis.textures["color"]
normal_png_bytes = stainless.vis.textures["normal"]
```

## Catching misuse

If you have leftover 2.x code paths, 3.0 will surface them quickly:

- **`AttributeError: 'AllProperties' object has no attribute 'pbr'`** —
  someone is still reading `material.properties.pbr`. Rename to `.vis`.
- **`TypeError: Material.__init__() got an unexpected keyword argument 'pbr'`** —
  a `Material(pbr={...})` call. Rename to `vis={...}`.
- **`ImportError: cannot import name 'PBRProperties' from 'pymat'`** —
  the class is gone. The `vis` scalars live on `Vis` in `pymat.vis._model`,
  but you shouldn't need to import that directly.
- **`ValueError: TOML [pbr] section is no longer supported in 3.0`** —
  a TOML file has a `[<material>.pbr]` block. Rename to `[<material>.vis]`.

## Why no deprecation cycle?

A 2.3 release would have added `DeprecationWarning`s on every
affected symbol before deleting them in 3.0. The hedge wasn't worth
it here: our two primary consumers (the `build123d` and
`vscode-ocp-cad-viewer` forks) upgrade in lockstep with us, and the
PyPI audience is small enough that the `AttributeError` + this guide
is a cleaner migration signal than a warning-emitting 2.3 interlude
would have been. See [issue #40](https://github.com/MorePET/mat/issues/40)
for the conversation.
