---
type: issue
state: open
created: 2026-04-17T08:07:49Z
updated: 2026-04-17T08:19:25Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/37
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-04-18T04:24:32.793Z
---

# [Issue 37]: [Replace hardcoded vis client with mat-vis reference client](https://github.com/MorePET/mat/issues/37)

## Context

`pymat/vis/` currently contains ~400 lines of mat-vis client logic
that we wrote as a temporary bridge because mat-vis's reference
client didn't exist yet. Now that mat-vis is shipping data (v0.1.0)
and will ship reference clients (mat-vis#3), this code should
migrate.

## What moves to mat-vis

| Current location | What | New home |
|---|---|---|
| `_client.py` (250 lines) | fetch, search, prefetch, rowmap_entry, get_manifest, range-read, cache | `clients/python.py` |
| `adapters.py` (170 lines) | to_threejs, to_gltf, export_mtlx, field name mapping | `clients/python.py` or `clients/adapters.py` |

## What stays in mat

| File | What | Why |
|---|---|---|
| `_model.py` | Vis, ResolvedChannel, from_toml, finish switching, discover | Material domain model |
| `__init__.py` | Re-exports from mat-vis client | Thin forwarding layer |
| `adapters.py` | Thin wrappers: `Material` → generic dicts → mat-vis adapter | Maps mat's types to mat-vis's interface |

## After migration

```python
# pymat/vis/__init__.py
from mat_vis_client import fetch, search, prefetch, rowmap_entry, get_manifest

# pymat/vis/adapters.py
def to_threejs(material):
    from mat_vis_client.adapters import to_threejs as _impl
    pbr = material.properties.pbr
    return _impl(
        scalars={"metallic": pbr.metallic, "roughness": pbr.roughness, ...},
        textures=material.vis.textures,
    )
```

mat-vis's adapters take generic `(scalars: dict, textures: dict)` —
no dependency on mat's types. Same interface works for JS/Rust
clients.

## Blocked by

- [MorePET/mat-vis#3](https://github.com/MorePET/mat-vis/issues/3)
  — reference clients shipped
- [MorePET/mat-vis#22](https://github.com/MorePET/mat-vis/issues/22)
  — release-manifest.json published

## Acceptance

- [ ] No hardcoded source list or URL pattern in mat
- [ ] `_client.py` replaced by import from mat-vis client
- [ ] `adapters.py` replaced by thin wrappers calling mat-vis adapters
- [ ] `_model.py` unchanged
- [ ] All existing tests pass
- [ ] mat-vis client importable without pymat dependency (no circular)
