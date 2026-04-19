---
type: issue
state: closed
created: 2026-04-17T11:27:26Z
updated: 2026-04-18T19:33:31Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/40
comments: 1
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-04-19T04:44:07.620Z
---

# [Issue 40]: [3.0: Move PBR scalars from properties.pbr to .vis](https://github.com/MorePET/mat/issues/40)

## Context

PBR scalars (roughness, metallic, base_color, ior, transmission,
clearcoat, emissive) are rendering parameters derived from
MaterialX source graphs. By our design principle, all
visual/rendering state belongs under `.vis`.

## Current (2.x)

```python
steel.properties.pbr.roughness        # rendering scalar (wrong namespace)
steel.properties.pbr.normal_map       # legacy texture path
steel.vis.textures["normal"]          # mat-vis texture bytes
steel.vis.source_id                   # mat-vis pointer
```

## Target (3.0)

```python
# PBR is the primary interface — flattened on .vis
steel.vis.roughness                   # scalar
steel.vis.metallic                    # scalar
steel.vis.base_color                  # (r, g, b, a)
steel.vis.ior                         # derived from optical.refractive_index
steel.vis.textures["normal"]          # baked PNG bytes

# MaterialX is the source/provenance — tucked under .vis.source
steel.vis.source                      # MaterialX graph (raw)
steel.vis.source.export(path)         # write .mtlx + PNGs to disk
steel.vis.source.xml                  # raw XML string

# mat-vis pointers
steel.vis.source_id                   # "ambientcg/Metal032"
steel.vis.finishes                    # {"brushed": "...", ...}
steel.vis.discover()                  # search mat-vis index
```

### Why PBR flat on `.vis`, MaterialX under `.vis.source`

PBR metallic-roughness is a subset of what MaterialX can describe
(MaterialX also covers Phong, Disney BSDF, subsurface, volume,
procedural nodes, etc.). So PBR is derived FROM MaterialX, not a
sibling.

But 99% of consumers want PBR scalars + textures — that's the
common access path. Flattening PBR onto `.vis` directly keeps
the API simple. The MaterialX graph is provenance (where did this
come from), not the primary interface.

```
MaterialX source graph (in mat-vis git)
    │
    ▼ bake (CI runner)
PBR scalars + flat PNG textures (in Parquet)
    │
    ▼ fetch (vis client)
material.vis.roughness / .textures["normal"]
```

### Physics → rendering bridge

`ior` derived from `properties.optical.refractive_index`,
`transmission` from `properties.optical.transparency` — these
derivations move into `Vis` initialization.

## Breaking changes

- `material.properties.pbr.*` → `material.vis.*`
- `PBRProperties` class removed from `properties`
- `pbr.*_map` fields removed (textures are `vis.textures[...]`)
- TOML `[material.pbr]` → `[material.vis]`
- ocp_vscode `is_pymat` path reads from `.vis`

## Migration path

- 2.2.0: ship both namespaces, adapters read from both
- 2.3.0: `DeprecationWarning` on `properties.pbr` access
- 3.0.0: remove `properties.pbr`, `.vis` is the single source

## Related

- mat-vis `mtlx/` directory — MaterialX source files in git
- `export_mtlx()` adapter — becomes `vis.source.export()`
- mat-vis#36 — reference client + adapters migration
---

# [Comment #1]() by [gerchowl]()

_Posted on April 18, 2026 at 07:33 PM_

Shipped as **py-materials 3.0.0** on PyPI (2026-04-18, 18:40 UTC).

Pipeline: feature/40-vis-cutover → #52 → release-please #53 → tag v3.0.0 → release.yml → PyPI (38s end-to-end).

Migration story in [docs/migration/v2-to-v3.md](https://github.com/MorePET/mat/blob/main/docs/migration/v2-to-v3.md). CHANGELOG entry under [3.0.0].

