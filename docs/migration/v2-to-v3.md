# Migrating to 3.x

- [3.1 → 3.2: mat-vis-client 0.5 adoption](#31--32-mat-vis-client-05-adoption) (planned)
- [3.0 → 3.1: Vis identity split](#30--31-vis-identity-split)
- [2.x → 3.0: PBR → .vis consolidation](#2x--30-pbr--vis-consolidation)

---

## 3.1 → 3.2: mat-vis-client 0.5 adoption

py-mat 3.2 bumps the `mat-vis-client` floor to `>=0.5.0`. The client
release is tracked at [mat-vis#85](https://github.com/MorePET/mat-vis/issues/85);
py-mat's migration is tracked at
[issue #73](https://github.com/MorePET/mat/issues/73).

### Rename cheat sheet (3.1 → 3.2)

| 3.1 (against mat-vis-client 0.4.x) | 3.2 (against mat-vis-client 0.5+) |
|---|---|
| `material.vis.mtlx.xml` (property, network IO on attribute access) | `material.vis.mtlx.xml()` (**method call**) |
| `from mat_vis_client import _get_client` | `from mat_vis_client import get_client` (public name) |
| `except urllib.error.HTTPError as e: ...` | `except HTTPFetchError as e: ...` (plus `NetworkError`, `NotFoundError`, `MaterialNotFoundError`, …) — all `MatVisError` subclasses |

The underlying behaviour is unchanged — `.xml()` still fetches lazily
and caches internally. The parens are the only user-visible break.

### Why `.xml` became a method

The 0.5 design reasoning (from mat-vis#85 item 7): property access
that silently triggers network IO is a footgun, and it doesn't port
cleanly to the JavaScript / Rust reference clients. Making it a
method forces the caller to acknowledge the network cost.

### Internal-only: `_get_client` → `get_client`

py-mat's `Vis.client` property and the module-level `pymat.vis.fetch`
/ `search` / `client()` helpers now import the public `get_client`,
with a fallback to the deprecated `_get_client` for `mat-vis-client
<0.5`. The floor in `pyproject.toml` stays at `>=0.4.0` for now so
downstream pinning doesn't flip overnight; it moves to `>=0.5.0`
when we cut 3.2.

### Typed HTTP errors

0.5 wraps `urllib.error.HTTPError` in a typed hierarchy rooted at
`MatVisError`:

- `HTTPFetchError(url, code, reason)` — generic 4xx/5xx.
- `NotFoundError` → `MaterialNotFoundError`, `SourceNotFoundError`,
  `TierNotFoundError`, `ChannelNotFoundError` — 404 with the specific
  thing that was missing.
- `NetworkError(url, reason)` — connection-level failure (no
  `.code`).
- `RateLimitError` — 429, with `retry_after` seconds.

Code that caught `urllib.error.HTTPError` still works against 0.4.x
— py-mat's test flake-guard `_skip_on_upstream_outage` catches both
shapes and picks based on which import succeeds. Once the floor
moves to `>=0.5.0`, the urllib catch becomes dead code.

---

---

## 3.0 → 3.1: Vis identity split

3.1 splits `Vis.source_id` into `Vis.source` + `Vis.material_id` so py-mat's
types match `mat-vis-client`'s `(source, material_id, tier)` positional-arg
shape end-to-end. No more string surgery at delegation sites. See
[ADR-0002](../decisions/0002-vis-owns-identity-client-exposed.md) for the
full rationale.

### Rename cheat sheet (3.0 → 3.1)

| 3.0 | 3.1 |
|---|---|
| `vis.source_id` | `vis.source` + `vis.material_id` (both as real fields). `source_id` remains as a **read-only convenience** returning `"{source}/{material_id}"` — handy for logs and CLI output. |
| `vis.source_id = "ambientcg/Metal012"` | `vis.source = "ambientcg"; vis.material_id = "Metal012"` |
| `if vis.source_id is not None:` | `if vis.has_mapping:` |
| `vis.source_id.split("/", 1)` | `vis.source`, `vis.material_id` — already split |
| `client.mtlx(*vis.source_id.split("/"), tier=vis.tier)` | `vis.mtlx` — dotted sugar |
| `client.channels(*vis.source_id.split("/"), vis.tier)` | `vis.channels` |
| `client.materialize(*vis.source_id.split("/"), vis.tier, out)` | `vis.materialize(out)` |

### TOML `[vis.finishes]` format change

Slashed-string form is removed in 3.1. Run the one-shot migrator:

```bash
python scripts/migrate_toml_finishes.py          # rewrites src/pymat/data/*.toml
python scripts/migrate_toml_finishes.py --check  # exits non-zero if stale
python scripts/migrate_toml_finishes.py --diff   # preview only
```

Before (3.0):

```toml
[stainless.vis.finishes]
brushed = "ambientcg/Metal012"
polished = "ambientcg/Metal049A"
```

After (3.1):

```toml
[stainless.vis.finishes]
brushed  = { source = "ambientcg", id = "Metal012" }
polished = { source = "ambientcg", id = "Metal049A" }
```

The loader raises `ValueError` on a bare-string finish value in 3.1 with
a pointer back to this doc. No deprecation cycle, consistent with the 3.0
PBR→vis stance.

### Catching 3.0 → 3.1 misuse

- **`AttributeError: Vis.source_id is read-only in 3.1+`** — someone assigned
  to `source_id`. Assign `source` + `material_id` separately, or via `finish = "..."`.
- **`ValueError: Finish 'X' uses the 3.0 slashed-string form`** — TOML still has
  the old value shape. Run `python scripts/migrate_toml_finishes.py`.

---

## 2.x → 3.0: PBR → .vis consolidation

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

## mat-vis-client upgrade

3.0 requires `mat-vis-client>=0.4.0` (was `>=0.2.0` in 2.x). The jump brings several behaviors worth knowing about:

- **Manifest `schema_version` now required.** `mat-vis-client` 0.3.0 dropped its legacy `version` fallback. If you had a warm cache from a 0.2.x install, the first `material.vis.*` call on 3.0 will error on the stale manifest format. One-time fix:

  ```bash
  mat-vis-client cache clear
  ```

  Fresh installs and CI environments are unaffected — only pre-existing caches need this.

- **Module-level `fetch()` and static `CATEGORIES` frozenset are gone** from `mat_vis_client`. py-mat doesn't use either, but if your own code imported `mat_vis_client.fetch` or `mat_vis_client.CATEGORIES` directly, migrate to `MatVisClient().fetch_all_textures(...)` and `client.categories()` respectively.

- **Friendlier errors + automatic 502/504 retries** (0.4.0) — no action needed, just better diagnostics when the CDN hiccups.

## Why no deprecation cycle?

A 2.3 release would have added `DeprecationWarning`s on every
affected symbol before deleting them in 3.0. The hedge wasn't worth
it here: our two primary consumers (the `build123d` and
`vscode-ocp-cad-viewer` forks) upgrade in lockstep with us, and the
PyPI audience is small enough that the `AttributeError` + this guide
is a cleaner migration signal than a warning-emitting 2.3 interlude
would have been. See [issue #40](https://github.com/MorePET/mat/issues/40)
for the conversation.
