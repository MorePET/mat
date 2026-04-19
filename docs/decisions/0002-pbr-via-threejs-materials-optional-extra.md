# 0002. PBR integration via threejs-materials as optional `[pbr]` extra

- Status: Accepted
- Date: 2026-04-15
- Deciders: @gerchowl
- Context issue: [#3](https://github.com/MorePET/mat/issues/3)

## Context

Issue #3 (from Roger Maitland / @gumyr, author of build123d) asks for
`py-materials` to become the material layer for build123d, with
support for loading PBR (physically-based rendering) materials from
the four major open MaterialX libraries — ambientcg, polyhaven,
gpuopen, physicallybased.info — so build123d shapes can carry
texture-driven materials and render in `ocp_vscode` with full PBR.

Investigation turned up [`bernhard-42/threejs-materials`][tjm], a
pure-Python Apache-2.0 library (v1.0.0) that **already does all the
heavy lifting**:

- Loaders for all four MaterialX sources
- MaterialX shader-graph baking into flat textures
- Texture cache + `resolution` tier selection
- Output as Three.js `MeshPhysicalMaterial`-shaped JSON

`ocp_vscode` already consumes it directly — the example at
`bernhard-42/vscode-ocp-cad-viewer/examples/material-object.py` has

```python
shader_ball.material = PbrProperties.from_gpuopen("Stainless Steel Brushed")
```

with a `FutureWarning` saying *"the required type of
`build123d`'s `shape.material` will change"*. That warning is
explicitly waiting for `py-materials` to become the canonical
carrier type.

**Design question**: how should `py-materials` integrate with
`threejs-materials` and `build123d`?

## Decision

`py-materials` **depends on `threejs-materials` as an optional
`[pbr]` extra** and defines a narrow `PbrSource` typing `Protocol`
that both the native lite `PBRProperties` dataclass and
`threejs_materials.PbrProperties` conform to. `Material` gains an
optional `pbr_source` field typed as `Optional[PbrSource]` that
carries the rich backend when present, alongside the existing
`properties.pbr` (the lite native in-tree dataclass).

Concretely:

```python
# pymat/pbr/_protocol.py
@runtime_checkable
class PbrSource(Protocol):
    def to_dict(self) -> dict: ...

# pymat/pbr/__init__.py
try:
    from threejs_materials import PbrProperties  # when [pbr] extra installed
except ImportError:
    pass
```

```python
# pymat/core.py
@dataclass
class _MaterialInternal:
    ...
    pbr_source: Optional["PbrSource"] = None

    def to_three_js_material_dict(self) -> dict:
        """Pick the right backend and emit Three.js JSON."""
        if self.pbr_source is not None:
            return self.pbr_source.to_dict()
        return self.properties.pbr.to_dict()
```

Usage:

```python
from pymat import Material
from pymat.pbr import PbrProperties  # requires [pbr] extra

steel = Material(
    name="Brushed Steel",
    density=7.85,
    formula="Fe",
    pbr_source=PbrProperties.from_gpuopen("Stainless Steel Brushed"),
)
shape.material = steel  # future build123d.Shape.material integration

# Both consumers read from the same object:
json_for_viewer = steel.to_three_js_material_dict()
density_for_mass = steel.density
molar_mass_for_radiation = steel.molar_mass  # see ADR-0001
```

## Backfill pattern (graceful enhancement for existing consumers)

Setting `Material.pbr_source` also **projects the rich backend's
serialized fields onto the lite `properties.pbr` dataclass** via an
internal `_backfill_pbr_from_source()` pass in `__post_init__`. This
copies the overlapping fields (color, metalness, roughness, ior,
emissive, transmission, clearcoat, normal/roughness/metalness/ao
maps) from `pbr_source.to_dict()` into the lite dataclass
one-way at construction time.

Why: existing downstream renderers that read
`material.properties.pbr.<field>` directly — for example,
`ocp_vscode`'s `_extract_materials_from_node()` in `show.py`, which
reads `base_color`, `metallic`, `roughness`, `normal_map`, etc. —
pick up the rich-backend data **without any code change on their
side**. A user can assign
`material.pbr_source = PbrProperties.from_gpuopen("...")` and
`ocp_vscode.show()` will render with the MaterialX textures today.

Fields on the rich source that don't have a corresponding lite
field (sheen, anisotropy, iridescence, dispersion, clearcoat
normal/roughness maps, specular, thickness, displacement, etc.)
are dropped in the projection — the lite dataclass is a lossy
subset. Consumers that can handle the full fidelity should read
`material.pbr_source` directly or call
`material.to_three_js_material_dict()`, which delegates to the
rich source first and so preserves every field.

The backfill is a one-way copy at `__post_init__` — it does not
keep the lite dataclass in sync if the rich source is mutated
later. That's intentional: mutating a loaded PBR material after
assignment is unusual, and re-assigning `pbr_source` will re-run
the backfill.

## Consequences

**Enables**:

- **Physics users stay lean.** `pip install py-materials` does not
  pull `pillow`, `pygltflib`, `requests`, or any of the
  texture-library HTTP surface. Monte Carlo particle-transport
  users (the README's primary use case) are unaffected by this
  ADR.
- **PBR users get full MaterialX support** with a single extra:
  `pip install py-materials[pbr]`. Downloads, caches, baking, and
  Three.js output are all handled by `threejs-materials` without
  `py-materials` maintaining the HTTP / texture / MaterialX
  code.
- **The canonical type for `shape.material` is `pymat.Material`**,
  carrying both physics (density, thermal, molar mass) AND PBR
  (via `pbr_source`). `ocp_vscode` / build123d viewers call
  `material.to_three_js_material_dict()` and get uniform output
  regardless of backend.
- **Zero cross-repo code duplication.** `threejs-materials` stays
  the single source of truth for PBR loading. `py-materials` stays
  the single source of truth for materials science. `build123d`
  stays the single source of truth for CAD shapes.
- **Independent release cadences.** Each library evolves on its
  own schedule. Version-compat is a semver pin, managed by
  dependabot.
- **Protocol-based typing** lets users plug in custom PBR backends
  (for example, a future `pymat.pbr` loader for a proprietary
  texture library) without touching py-materials.

**Costs**:

- **Two parallel PBR code paths** on py-materials' side. The lite
  `PBRProperties` dataclass stays (for TOML-authored materials and
  users without the extra) and grows a `to_dict()`
  method that implements the Protocol. The rich path is the
  optional extra. Some duplication of intent between the two
  serializers is unavoidable; their outputs may drift on edge
  cases unless consciously kept in sync.
- **`threejs-materials` v2.x release would be a coordinated
  update** with a dependabot PR + CI matrix check. Not much effort
  but requires attention.
- **First-time users of the `[pbr]` extra pay a cold-install
  cost**: `pillow`, `pygltflib`, `requests` plus their transitive
  deps. ~10-20 MB added to the environment.

**Rules out**:

- **Vendoring `threejs-materials` into `py-materials`** (the
  "absorb" option). That would require py-materials to track
  Bernhard's changes manually, duplicate ~3000 lines of code,
  and compete with a library that's actively maintained by
  someone else.
- **Making `threejs-materials` depend on `py-materials`**
  (reverse direction). Semantically wrong — the physics layer
  shouldn't be a transitive dep of a rendering loader.
- **A required `threejs-materials` dep on `py-materials`**.
  Bloats the physics-only install.

## Alternatives considered

- **Option I — required dep**: `threejs-materials` in
  `dependencies`. Rejected: bloats physics-only users who don't
  care about PBR rendering.
- **Option III — reverse dep**: `threejs-materials` depends on
  `py-materials`. Rejected: conceptually backwards, couples
  Bernhard's library to our release cadence.
- **Option IV — Protocol-only, no dep either way**: users install
  both libraries manually and the Protocol is the only
  connection. Rejected as the first user experience:
  `pip install py-materials[pbr]` is the obvious wire.
- **Option V — absorb `threejs-materials` into `py-materials`**:
  vendor the code. Rejected for the reasons above.
- **Option VI — no PBR integration**: py-materials stays
  physics-only. Rejected: violates the spirit of issue #3 and
  the build123d integration story.

See the session discussion on [#3][#3] for the full
option-matrix and first-principles analysis.

## Upgrade trigger

Revisit this ADR if any of these happen:

1. **`threejs-materials` adds a hard dep that py-materials users
   object to** (e.g., a GPU-accelerated texture baker). Might
   force reverting to a vendored or proxied approach.
2. **A second PBR backend emerges** (e.g., an OpenUSD-native
   loader) that users want alongside `threejs-materials`. The
   Protocol already supports this — just update the docs and
   `pymat.pbr.__init__` to pick up the second backend when
   installed.
3. **Bernhard steps away from `threejs-materials`**. py-materials
   may then need to either fork or rewrite. The Protocol boundary
   means either option keeps the downstream API stable.
4. **The `[pbr]` install cost becomes painful for common users**
   (e.g., Pillow stops being pure-Python). Might need to trim or
   split the extra.

[tjm]: https://github.com/bernhard-42/threejs-materials
[#3]: https://github.com/MorePET/mat/issues/3
