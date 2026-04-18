# ADR-0002: `Material.vis` owns identity + scalars; `mat-vis-client` is exposed, not wrapped

- **Status:** Accepted
- **Date:** 2026-04-18
- **Supersedes:** —
- **Related issues:** #37 (reference client), #40 (3.0 PBR→vis), #58 (this work)

## Context

After the 3.0 cutover (issue #40), `Material.vis` is the canonical home
for all visual state: identity (`source_id`, `tier`, `finishes`), PBR
scalars (`base_color`, `metallic`, `roughness`, `ior`, `transmission`,
`clearcoat`, `emissive`), and texture access via
`material.vis.textures`. Separately, `mat-vis-client` shipped as its
own PyPI package (issue #37) with a richer API than py-mat currently
exposes — `client.mtlx()` returning `MtlxSource` with `.xml` / `.export()`
/ `.original`, `client.tiers()`, `client.channels()`, `client.materialize()`,
`client.cache_prune()`, `client.check_updates()`, and more.

Every time a new consumer integrates (Three.js adapter, MaterialX
export, KTX2 transport, the ocp-vscode fork, build123d PR #1270), we
rediscover the same design question: does py-mat wrap this, or expose
the client? We keep arriving at the same answer in conversation but
never wrote it down, so we keep relitigating it — including, honestly,
inside this session multiple times.

This ADR exists to stop the drift.

## Decision

Three principles.

### 1. `Material.vis` owns material-side identity and scalars only

On `Vis`:

- **Identity:** `source`, `material_id`, `tier`, `finishes`, `finish`
  (the switcher)
- **PBR scalars:** `base_color`, `metallic`, `roughness`, `ior`,
  `transmission`, `clearcoat`, `emissive`
- **Domain logic:** `from_toml` loader, the PBR-defaults `get()`
  method, the tag-aware `discover()` method (py-mat's index-layer
  enrichment over the raw `mat-vis-client.search`).

Not on `Vis`: anything that duplicates a `mat-vis-client` method.

### 2. `mat-vis-client` is exposed, not wrapped

Reachable two ways:

- `material.vis.client` — per-material shortcut to the shared
  singleton. Most users hit this path.
- `pymat.vis.client()` — module-level entry point for operations
  that don't have a material in hand (tier enumeration, cache
  management, discovery before a material is picked).

Any method `mat-vis-client` adds upstream is immediately callable
without a py-mat release. We don't gate upstream capabilities on
our own release cadence.

### 3. Material-keyed operations get thin delegation sugar on `Vis`

Anywhere a `mat-vis-client` method takes `(source, material_id, tier)`
and those three come from a material's identity, `Vis` provides a
sugar property/method that pre-fills them. The sugar is a
**delegate**, not a translation layer — no new behavior, just less
boilerplate.

Inventory at ADR time:

- `material.vis.textures` → `client.fetch_all_textures(source, material_id, tier=self.tier)`
- `material.vis.channels` → `client.channels(source, material_id, self.tier)`
- `material.vis.mtlx` → `client.mtlx(source, material_id, tier=self.tier)` → `MtlxSource`
- `material.vis.materialize(out)` → `client.materialize(source, material_id, self.tier, out)`

The MtlxSource accessor is named `.mtlx` (not `.source`) because `source`
is already taken by the identity field (`Vis.source: str` = `"ambientcg"`).
`.mtlx` matches the upstream `client.mtlx()` name exactly.

This inventory grows when mat-vis-client adds a new material-keyed
method and we decide it's common enough to deserve sugar. The bar
for adding sugar is "does >1 consumer call this same
`(self.source, self.material_id, self.tier)` shape often enough to
be worth 3 lines on `Vis`?"

### Intentional exception: `Vis.discover()`

One method on `Vis` does not follow the thin-delegate rule: `discover()`.

`discover()` exists pre-3.0 as a tag-aware convenience wrapper over
`mat_vis_client.search`. It renames `metallic → metalness` (py-mat's
internal name for the scalar vs upstream's), widens roughness /
metalness into search-range tuples, and optionally mutates the Vis
(`auto_set=True`). All three of those are translation-layer behaviors
Principle 2 otherwise rejects.

We keep it because:

- **Ergonomics.** `steel.vis.discover(category="metal")` reads
  naturally; moving it to a module function `pymat.vis.discover_for
  (material, ...)` loses the dotted sugar without a clear win.
- **Domain logic.** Tag-aware search with py-mat's scalar renaming is
  genuinely py-mat-side — not a delegation to an identical
  mat-vis-client operation.
- **Scope.** It's the single exception. If a second method tempts us
  into wrapping rather than delegating, that's the signal to
  re-evaluate this ADR.

When adding new material-keyed operations, the default answer is
still "thin delegate." `discover()` is the carve-out, not the
precedent.

## Ownership test

When the question "should py-mat add sugar for X, or should
mat-vis-client expose X differently?" comes up, apply this test:

1. Does the operation take a `pymat.Material` (or `Vis`) as input?
   → **py-mat** wraps it: sugar property on `Vis`, or adapter
   function in `pymat.vis.adapters`.
2. Does the operation take `mat-vis` primitives `(source,
   material_id, tier, channel, …)` as input? → **mat-vis-client**
   owns it; py-mat exposes via `material.vis.client` without wrapping.

**Never** push py-mat abstractions (per-material default tier,
null-vis-case handling, TOML-level shapes) down into mat-vis-client.
That coupling invalidates the "mat-vis-client is ecosystem-level,
py-mat is one consumer of it" framing.

## Why the two-field identity (`source` + `material_id`) instead of one slashed string

This ADR doubles as the justification for the 3.0 → 3.1 field split.

`Vis` held `source_id: str` through 3.0 — a slashed string like
`"ambientcg/Metal012"` that every delegation site had to `.split("/", 1)`
before calling `mat-vis-client`. That form was a TOML curator-convenience
(a single string value per finish in `[vis.finishes]`), but nothing
in `mat-vis-client`'s model knows it exists. The client takes
`(source, material_id)` as two positional args everywhere.

Under the principles above:

- Sugar like `material.vis.mtlx` → `client.mtlx(...)` is supposed
  to be a **delegate, not a translation**. But with one slashed
  string and two positional args, every sugar site has to translate
  (parse the slash, inject tier) at runtime.
- The mismatch in identity shape is **py-mat abstraction leaking
  into the delegation boundary** — the exact thing principle 2
  rejects.

So `Vis` now stores `source: str | None` and `material_id: str | None`
separately. Variable names match mat-vis-client's positional-arg
names end-to-end. Delegates become:

```python
# Before (3.0)
src, mid = self.source_id.split("/", 1)
return self.client.mtlx(src, mid, tier=self.tier)

# After (3.1+)
return self.client.mtlx(self.source, self.material_id, tier=self.tier)
```

The TOML follows the same principle: `[<material>.vis.finishes]`
values are **inline tables**, not slashed strings:

```toml
# 3.0 (deprecated)
[stainless.vis.finishes]
brushed = "ambientcg/Metal012"

# 3.1
[stainless.vis.finishes]
brushed = { source = "ambientcg", id = "Metal012" }
```

Three other shapes were considered and rejected:

- **Two-tuple arrays** (`brushed = ["ambientcg", "Metal012"]`) —
  compact but positional; readers have to know the order, and a
  future field (e.g. per-finish tier override) can't extend
  without breaking compat. Footgun.
- **Default source at `[vis]` level, string ids in finishes**
  (`default_source = "ambientcg"` + `brushed = "Metal012"`) —
  optimizes for today's accident (100% ambientcg in the current
  corpus). Mixes `string` and `table` values inside one dict the
  moment the first polyhaven or gpuopen finish lands; the
  enrichment script already targets polyhaven.
- **Keep slashed strings** — cheap today, permanent drag at every
  mat-vis-client boundary; doesn't match `mat-vis-client`'s model
  anywhere; forces runtime parsing + runtime errors instead of
  TOML-load errors.

Inline tables win on the "py-mat types match mat-vis-client's
boundary" criterion, extend cleanly to per-finish overrides, and
produce clearer TOML-load errors for bad data.

## Consequences

- `pymat.vis` stays small. No parallel implementation of
  mat-vis-client.
- New mat-vis-client capabilities (e.g. new tier formats, cache
  operations, update checks) land for py-mat consumers automatically
  via `material.vis.client` — py-mat only ships a release when a
  capability becomes material-keyed enough to deserve sugar.
- Adapters (`to_threejs`, `to_gltf`, `export_mtlx`) stay pure
  functions over `(scalars, textures)`. They don't know about
  `Material`. py-mat ships Material-accepting wrappers in
  `pymat.vis.adapters`; `mat-vis-client` owns the format logic.
- Consumer code (build123d, ocp-vscode) imports only from `pymat`.
  The `mat-vis-client` package name is internal plumbing for
  anything consumers do via `material.vis.*`; direct import is
  an escape hatch, not the paved path.
- The two-field split is a 3.0 → 3.1 breaking change for TOML
  files and for any code that set `vis.source_id = "foo/bar"`
  directly. Break cleanly (no deprecation cycle), consistent with
  the 3.0 PBR→vis stance — our only known consumers are us.

## When to revisit

- If mat-vis-client's `(source, material_id, tier)` signature
  changes — e.g. if slashed refs become a broader ecosystem
  convention beyond py-mat and mat-vis-client grows overloads
  accepting them. If that happens, py-mat could drop the split
  and route single-string identifiers directly to the client.
- If a capability turns out to need py-mat-side translation (not
  just delegation) — the bar is high: we've hit KTX2 / MaterialX /
  tier enumeration without needing it.
- If material hierarchy starts inheriting `vis` from parent to
  child (today it doesn't — children get a fresh empty `Vis`; only
  `properties` inherits). That changes where `finishes` live and
  how delegation sugar null-checks work. Out of scope here; file a
  separate ADR if we go there.
