---
type: issue
state: open
created: 2026-04-16T17:10:13Z
updated: 2026-04-16T20:55:03Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/35
comments: 3
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-04-17T04:41:59.258Z
---

# [Issue 35]: [Add Material.to_threejs() and Material.to_gltf() output adapters](https://github.com/MorePET/mat/issues/35)

> **NOTE:** The original body below is superseded by the
> [final API comment](https://github.com/MorePET/mat/issues/35#issuecomment-4263085761).
> Key change: PBR scalars STAY in `.properties.pbr`, adapters
> take `Material` (not `Vis`), `.vis` owns textures + source
> reference only.

## API design (final, see comment for authoritative version)

### Namespace

- `.properties.pbr` — PBR scalars from TOML (roughness, metallic, ior). Always available.
- `.vis` — mat-vis remote data (textures, source_id, fetch). Lazy, nullable.
- Adapters — standalone functions in `pymat.vis.adapters`:
  `to_threejs(material)`, `to_gltf(material)`, `export_mtlx(material, path)`.
  Signature takes Material, reads from both `.properties.pbr` and `.vis`.
- Shim — `pymat.vis.shim` fully exposed.

### Field name mapping

Canonical mapping between ecosystems:

| Concept | py-mat | mat-vis (index/rowmap/parquet) | Three.js | glTF |
|---|---|---|---|---|
| Metal scalar | `metallic` | `metalness` | `metalness` | `metallicFactor` |
| Roughness scalar | `roughness` | `roughness` | `roughness` | `roughnessFactor` |
| Base color | `base_color` (RGBA tuple) | `color_hex` (#RRGGBB) | `color` (hex int) | `baseColorFactor` |
| Color texture | — | `color` (channel) | `map` | `baseColorTexture` |
| Normal texture | — | `normal` (channel) | `normalMap` | `normalTexture` |
| Roughness texture | — | `roughness` (channel) | `roughnessMap` | (packed in metallicRoughnessTexture) |
| Metalness texture | — | `metalness` (channel) | `metalnessMap` | (packed in metallicRoughnessTexture) |
| AO texture | — | `ao` (channel) | `aoMap` | `occlusionTexture` |

Each adapter hardcodes its own translation using this table.
py-mat keeps `metallic` (established API, matches glTF's root term).
mat-vis keeps `metalness` (matches Three.js and upstream source naming).

### Material → vis source_id mapping

A `vis_source_id` field in the TOML data files links a py-mat
material to its mat-vis appearance:

```toml
[stainless.s316L]
name = "Stainless Steel 316L"
vis_source_id = "ambientcg/Metal_Brushed_001"
```

Nullable — materials without a mat-vis appearance simply have
`vis = None`. Curated manually as mat-vis publishes data.

### resolve() semantics

`vis.resolve(channel, pbr)` returns a `ResolvedChannel`:

```python
@dataclass
class ResolvedChannel:
    texture: bytes | None    # PNG bytes if texture exists
    scalar: float | None     # scalar fallback
    has_texture: bool
```

Adapters use this to decide: texture map or uniform value.

## Acceptance

- [ ] `Vis` class with source_id, tier, textures dict, resolve()
- [ ] `vis_source_id` field in Material + TOML schema
- [ ] Field name mapping table in a shared constants module
- [ ] `pymat.vis.shim` — get_manifest, fetch, rowmap_entry
- [ ] `pymat.vis.adapters` — to_threejs, to_gltf, export_mtlx
      (signature: takes Material, reads both namespaces)
- [ ] Tests for Vis, shim, resolve, each adapter
- [ ] Coordinate with @bernhard-42 on ocp_vscode

## Related

- [MorePET/mat-vis#3](https://github.com/MorePET/mat-vis/issues/3) — reference clients
- [MorePET/mat-vis#8](https://github.com/MorePET/mat-vis/issues/8) — M4: Python client
- [MorePET/mat-vis#1](https://github.com/MorePET/mat-vis/issues/1) — appearance ↔ physical material mapping
---

# [Comment #1]() by [gerchowl]()

_Posted on April 16, 2026 at 08:11 PM_

## Final API decision (2026-04-16)

**PBR scalars stay under `.properties.pbr`.** `.vis` owns textures, source reference, fetch mechanism, and a resolve helper for adapters.

```python
steel = Material("Stainless Steel 316L")

# Physical (TOML, always available)
steel.properties.pbr.roughness        # 0.3 (scalar)
steel.properties.pbr.metallic         # 1.0
steel.properties.pbr.ior              # 1.5 (derived from optical)

# Visual (mat-vis, lazy/nullable)
steel.vis.source_id                   # "ambientcg/Metal_Brushed_001"
steel.vis.textures["color"]           # PNG bytes
steel.vis.textures["roughness"]       # PNG texture map (spatial variation)
steel.vis.resolve("roughness")        # texture if available, scalar fallback

# Fetch control
steel.vis.fetch()
steel.vis.manifest                    # raw rowmap entry for DIY consumers

# Shim (standalone, no Material needed)
from pymat.vis import shim
shim.fetch("ambientcg", "Metal_Brushed_001", tier="1k")

# Adapters (functions, not methods)
from pymat.vis.adapters import to_threejs, to_gltf, export_mtlx
to_threejs(steel)  # reads from both .properties.pbr and .vis
```

Rationale: PBR scalars bridge physics → rendering (IOR from refractive_index). "roughness" as scalar (0.3) vs texture map (PNG) are different data — different namespaces is correct. No breaking change.

---

# [Comment #2]() by [gerchowl]()

_Posted on April 16, 2026 at 08:41 PM_

## Update: search lives in shim, not on Material

```python
from pymat.vis import shim

# Search is a mat-vis concern — uses the index, standalone
results = shim.search(category="metal", roughness=0.3)

# Material.vis holds the pointer, delegates fetch to shim
my_metal = Material(name="super-metal", metallic=1.0)
my_metal.vis.source_id = results[0]["id"]
my_metal.vis.textures["color"]  # fetches via shim
```

`Material.vis` is always a `Vis` object (never None). Starts with
`source_id=None` and empty textures for custom materials.
Populated from TOML `[vis]` section for registered materials.

No `.vis.search()` method on Material — keeps the domain object
clean. Search is `shim.search()`.

### Finishes for TOML-registered materials

```toml
[stainless.s316L.vis]
default = "brushed"

[stainless.s316L.vis.finishes]
brushed  = "ambientcg/Metal_Brushed_001"
polished = "ambientcg/Metal_Polished_002"
matte    = "polyhaven/metal_plate_matte"
```

```python
steel = Material("Stainless Steel 316L")
steel.vis.source_id       # "ambientcg/Metal_Brushed_001" (default)
steel.vis.finishes        # dict of finish → source_id
steel.vis.finish = "polished"  # switch
```

### Shim public API (final)

```python
from pymat.vis import shim

shim.search(category=..., roughness=..., metallic=...)  # index query
shim.fetch(source, id, tier)                            # textures
shim.rowmap_entry(source, id, tier)                     # raw offsets
shim.get_manifest(release_tag)                          # URL discovery
```

---

# [Comment #3]() by [gerchowl]()

_Posted on April 16, 2026 at 08:55 PM_

## Naming fix: `shim` → `vis` module

Public API is `from pymat import vis`, not `from pymat.vis import shim`.

```python
from pymat import vis

vis.search(category="metal", roughness=0.3)
vis.fetch("ambientcg", "Metal_Brushed_001", tier="1k")
vis.rowmap_entry("ambientcg", "Metal_Brushed_001", tier="1k")
vis.get_manifest(release_tag="v2026.04.0")
```

"shim" is an implementation detail, not a user-facing name.

