# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [4.0.0](https://github.com/MorePET/mat/compare/v3.4.0...v4.0.0) (2026-04-20)


### ⚠ BREAKING CHANGES

* 3.1 — Vis identity split + inline-table finishes + ADR-0002
* 3.0 vis cutover — `properties.pbr` removed, `.vis` canonical, mat-vis-client 0.4.x ([#52](https://github.com/MorePET/mat/issues/52))

### Added

* [#88](https://github.com/MorePET/mat/issues/88) vis inheritance + [#89](https://github.com/MorePET/mat/issues/89) pymat[...] lookup + runnable examples (3.4.0) ([048416f](https://github.com/MorePET/mat/commit/048416fc28fdd9ef656756b54cf03f91b48366e9))
* [#88](https://github.com/MorePET/mat/issues/88) vis inheritance + [#89](https://github.com/MorePET/mat/issues/89) pymat[...] lookup + runnable examples (3.4.0) ([3ad2916](https://github.com/MorePET/mat/commit/3ad2916590e75bc8d16ebf7a6c23c3c7dd2a2050))
* 3.0 vis cutover — `properties.pbr` removed, `.vis` canonical, mat-vis-client 0.4.x ([#52](https://github.com/MorePET/mat/issues/52)) ([49b5dff](https://github.com/MorePET/mat/commit/49b5dff0f5ca139e8e7f1dec82587d4ddf146c45))
* 3.1 — Vis identity split + inline-table finishes + ADR-0002 ([24d060e](https://github.com/MorePET/mat/commit/24d060e8e258b4eb3b24f6ff894df0da4622d954))
* 3.1.1 — audit corrections, cache invalidation on identity change, adapter re-exports ([aa3f956](https://github.com/MorePET/mat/commit/aa3f95681afca7592b0c453327d73fc3328d76f0))
* 3.1.2 — milestone 1 audit follow-ups (13 issues closed) ([6a70509](https://github.com/MorePET/mat/commit/6a70509fc0e18739e560a3f32c44255f7f9f20f3))
* 3.2 prep — mat-vis-client 0.5 API adoption (blocked on PyPI publish) ([52bde58](https://github.com/MorePET/mat/commit/52bde5856add4705440b0c6dd4a20e415a40b8e4))
* add mat-rs Rust crate for material database + formula parsing ([82630d4](https://github.com/MorePET/mat/commit/82630d4dea1c9f26a80f37a1d64d0f4c962e1e8f))
* embed TOML data files in crate via include_str!() ([0e82f07](https://github.com/MorePET/mat/commit/0e82f0713bf04133c5ff982dafc76cd689bf249c)), closes [#5](https://github.com/MorePET/mat/issues/5)
* pixel-diff baselines for visual regression (closes [#41](https://github.com/MorePET/mat/issues/41)'s last two checkboxes) ([b6f6cce](https://github.com/MorePET/mat/commit/b6f6cce1904e580b95f7afa99012e3d0535d12c9))
* pymat.search(query) — fuzzy domain-library search ([bf9629a](https://github.com/MorePET/mat/commit/bf9629a8593dc16057b31a5374b2e80ca79adda9))
* pymat.search(query) — fuzzy domain-library search ([45c7fdc](https://github.com/MorePET/mat/commit/45c7fdcddf3b93838f78de1b19dfd25da237edb8))
* Vis.to_gltf() / .to_threejs() / .export_mtlx() method sugar ([e3afd96](https://github.com/MorePET/mat/commit/e3afd96cbd9fdedaafb209c783ca91bec6fe2f53))
* Vis.to_gltf() / .to_threejs() / .export_mtlx() method sugar ([#78](https://github.com/MorePET/mat/issues/78)) ([1fc3194](https://github.com/MorePET/mat/commit/1fc3194e71ffb95b1b30bfb66b168ae550c8f453))


### Fixed

* add --allow-dirty to cargo publish in CI ([2e80119](https://github.com/MorePET/mat/commit/2e801191047602148a3dfb4ed21a3e092dc6c6d8))
* **ci:** correct release-please extra-file type and manifest baseline ([#46](https://github.com/MorePET/mat/issues/46)) ([30208d0](https://github.com/MorePET/mat/commit/30208d0477a1c36410565a25ff50a3aab581203c)), closes [#43](https://github.com/MorePET/mat/issues/43)
* **ci:** downgrade Python pin to 3.12 ([5c9eebe](https://github.com/MorePET/mat/commit/5c9eebe572478b9992374c5c59a96e23bdb23c3f))
* **ci:** pin Python to 3.13 via .python-version ([ee2d5dc](https://github.com/MorePET/mat/commit/ee2d5dc5cb93159be77d0de3718a301f16b7e64c))
* enricher molar_mass + pymarkdown MD031 + ADR infrastructure ([e212891](https://github.com/MorePET/mat/commit/e21289111739ff170efafbd62a974b9575b8f090))
* **enricher:** Material.molar_mass computed property + correct enricher docs ([506456b](https://github.com/MorePET/mat/commit/506456b64139a8eccf789300eabf565c8c6819ac))
* **lint:** resolve ruff errors and remove scaffold stub ([3a73739](https://github.com/MorePET/mat/commit/3a7373926a9b22b2f25c79c1dda01488d5d65e98))
* **pymarkdown:** rewrite RELEASE_PROCESS + TEMPERATURE_UNITS to satisfy MD031 ([7b67af3](https://github.com/MorePET/mat/commit/7b67af3fcb69f136f308fa1b24ca3be409f681cd))
* regenerate uv.lock for py-materials rename, apply rustfmt ([d1ace0b](https://github.com/MorePET/mat/commit/d1ace0be9c2c0344f6767ce0820e555bb9e89457))
* **sync:** use git merge-tree for false-positive-free conflict detection ([373809e](https://github.com/MorePET/mat/commit/373809ed93ef41e2bd0de095d6908d331f7dbf4e))
* **sync:** use git merge-tree for false-positive-free conflict detection ([4138abc](https://github.com/MorePET/mat/commit/4138abc7bc99aca6d56b39c2c4cf408417c0de22))
* **test:** stale Vis.source_id usage in visual regression test ([2e41c7b](https://github.com/MorePET/mat/commit/2e41c7b7bab221ebb13c1727664cc12ddbb98196))
* **tests:** xfail broken periodictable enrichment tests + add ruff dep ([78a5fda](https://github.com/MorePET/mat/commit/78a5fda68d23cac8ec6e6085714330e9a335e141))


### Changed

* rename Rust crate mat-rs → rs-materials ([c2d8ec1](https://github.com/MorePET/mat/commit/c2d8ec13a7378f8ec5fc4f94a92db7a703994337))


### Documentation

* **adr:** add ADR infrastructure + ADR-0001 on derived chemistry ([8b1d594](https://github.com/MorePET/mat/commit/8b1d59463808a24c29001c9888b4281c6e12910a))
* sync README with 3.1 visual-properties shape ([d917e6a](https://github.com/MorePET/mat/commit/d917e6a61a450803e70a38f140e54743995f91fe))
* update README and RELEASE_PROCESS for repo rename to mat ([b7bf7f3](https://github.com/MorePET/mat/commit/b7bf7f3a00f2584499663e38b5644196a68282ef))

## [3.4.0] - 2026-04-20

Unblocks the build123d#1270 Materials-class adapt pass — fixes two bugs
Bernhard reported against 3.3.0 ([#88](https://github.com/MorePET/mat/issues/88), [#89](https://github.com/MorePET/mat/issues/89)) and
adds a runnable, in-CI example file that mirrors his cell-style pattern.

### Added

* **`pymat["Stainless Steel 304"]`** — module-level subscript for exact
  lookup. Matches registry key OR `Material.name` OR `grade`
  (case-insensitive, NFKC + whitespace-collapse normalization). Raises
  `KeyError` with close-match suggestions on miss, raises on ambiguity
  with candidate list. `in` operator also supported. Closes [#89](https://github.com/MorePET/mat/issues/89).
* **`pymat.search(q, *, exact=True)`** — list-returning exact variant,
  symmetric with the fuzzy form. `exact=True` now matches `grade` too
  (previously only key + name — caught by the falsify review).
* **Input normalization on all lookup paths** — `search()` and `pymat[...]`
  both apply NFKC + case-fold + whitespace-collapse, so pasted strings
  with curly quotes, non-breaking spaces, or tabs resolve cleanly.
* **`examples/build123d_integration.py`** — cell-style (`# %%`) runnable
  script showing the full build123d + py-mat integration surface.
  Wired into pytest via `tests/test_build123d_integration_examples.py`
  so every cell is exercised on every CI run. Prevents API drift from
  breaking the downstream copy-paste.

### Fixed

* **Grades inherit parent `Vis` at load time** ([#88](https://github.com/MorePET/mat/issues/88)). Before 3.4, a grade
  without its own `[vis]` TOML section landed with `source=None`, which
  made `pymat.s304.vis.source` useless for every grade and forced
  downstream consumers (build123d#1270) to walk the parent chain
  manually. The loader now deep-copies the parent's `_vis` when a grade
  has no `[vis]`, and merges TOML overrides on top when it does. Matches
  the existing `_add_child` property-inheritance pattern. Runtime mutation
  semantics: changes on a child don't propagate to parent (or vice versa)
  — documented, intentional.

### Internal

* **`Vis.merge_from_toml(base, vis_data)`** — new classmethod for the
  loader's partial-override path. Handles the "grade specifies only
  `roughness=0.7`, inherit everything else" case that
  `Vis.from_toml` (pure constructor) couldn't express.
* **`search.py`**: new `_normalize()` helper, new `exact=True` path,
  grade added to exact-match targets. 25 new tests across
  `tests/test_lookup.py` + fuzzy regression coverage.
* **`tests/test_vis_inheritance.py`** — 21 tests pinning inheritance,
  isolation (child mutations don't touch parent), `merge_from_toml`
  unit coverage, cache-invalidation-on-identity-change, and end-to-end
  "Bernhard's workaround no longer needed".
* Falsify review documented at [py-mat#88](https://github.com/MorePET/mat/issues/88)
  — original deep-copy-at-access design was refuted by three orthogonal
  reviewers; final load-time deep-copy-with-merge design was chosen to
  match existing `_add_child` convention.

## [3.3.0] - 2026-04-19

Adds `pymat.search()` — fuzzy find over the domain library.

### Added

* **`pymat.search(query: str, *, limit: int = 10) -> list[Material]`** —
  tokenized, weighted-target fuzzy search over the full registered
  library. Complements `pymat.vis.search(...)` (visual catalog) with a
  symmetric domain-side verb.
  * Matches registry key (weight 10) > `Material.name` / `grade`
    (weight 5) > hierarchy parent names (weight 3).
  * All query tokens must match somewhere — conjunctive, so
    `pymat.search("stainless 316")` returns only grades matching both.
  * Triggers `load_all()` for exhaustive results; case-insensitive.
  * Ties broken by shorter registry key → parents rank above
    descendants when both score the same.
* **30 tests** (`tests/test_search.py`) pinning tokenization, scoring
  weights, conjunctive matching, tie-breaks, `limit=` semantics,
  across-category loading, deterministic ordering, and specific
  realistic queries (`"stainless 316"`, `"lyso ce saint"`, etc.).

## [3.2.1] - 2026-04-19

Discoverability sugar for the output adapters — motivated by the
[build123d#1270](https://github.com/gumyr/build123d/pull/1270) Materials-class
integration. Zero breaking change; existing `pymat.vis.to_gltf(material)` call
sites keep working identically.

### Added

* **`Vis.to_threejs()` / `Vis.to_gltf(*, name=None)` / `Vis.export_mtlx(out, *, name=None)`** —
  method-form sugar on `Vis`. `m.vis.<TAB>` now surfaces the three handoff
  formats. Thin delegates to the module-level adapters; same output byte-for-byte.
  ([#78](https://github.com/MorePET/mat/issues/78))
* **Adapters accept `Material` or `Vis`** — `to_gltf(obj)`, `to_threejs(obj)`,
  `export_mtlx(obj, out)` duck-type on `.vis`, so a detached `Vis()` can be
  serialized without an owning `Material`. `name=` kwarg populates the glTF /
  MTLX name field when `obj` is a plain Vis.
* **Test pins** (15 new):
  * `TestAdapterPolymorphism` — `to_*(m) == to_*(m.vis)`.
  * `TestVisAdapterMethods` — `m.vis.to_*() == to_*(m)`.
  * `TestAdapterOnDetachedVis` — full adapter path on `Vis()` with no Material.
  * Duck-typing invariant (`Vis` has no `.vis` attribute), keyword-only `name=`
    signature, and method-surface presence each dedicated-tested.
* **build123d glTF behaviour pinned** — `TestGltfMaterialPassthrough` documents
  the real state today: `apply_to()` preserves only `baseColorFactor`; direct
  `shape.material = m` reaches no glTF field at all. The tests fail the moment
  build123d#1270 lands and changes either behavior — the signal to update docs.
* **e2e test for `m.vis.mtlx.xml()`** — pins the 0.5 method shape against the
  live mat-vis CDN (skips on outage).

### Changed

* `pymat.vis.adapters` docstring and the `test_vis.py` module-shape test both
  reflect the polymorphic first-arg rename (`material` → `obj`, still
  positional-compatible).

### Architectural note

The adapter asymmetry is intentional: module-level functions for `Material → format` transforms (open/closed, easy to add new formats without touching Material/Vis), method form for operations *on* a concrete object (`MtlxSource.xml()` etc.). The new `Vis.to_*` sugar is discoverability-only — see
[mat-vis#93](https://github.com/MorePET/mat-vis/issues/93) for the architecturally-cleaner
endgame where the payload object moves into `mat-vis-client`.

## [3.2.0] - 2026-04-19

Adopts `mat-vis-client` 0.5.0 (closes [#73](https://github.com/MorePET/mat/issues/73); upstream: [mat-vis#85](https://github.com/MorePET/mat-vis/issues/85)). Also folds in the visual-regression pixel-diff framework ([#41](https://github.com/MorePET/mat/issues/41)) and infrastructure hygiene.

### Breaking

* **`mat-vis-client` floor raised to `>=0.5.0`.** 0.4.x is no longer supported. See [docs/migration/v2-to-v3.md](docs/migration/v2-to-v3.md#31--32-mat-vis-client-05-adoption) for the cheat sheet. The single user-visible surface change is `material.vis.mtlx.xml` → `material.vis.mtlx.xml()` (property → method, to match the JS/Rust reference clients and make the network cost explicit).

### Changed

* **Migrated internal `_get_client` → `get_client`** ([mat-vis#84](https://github.com/MorePET/mat-vis/issues/84)). The public accessor lands in 0.5.0; py-mat no longer reaches past the underscore. A try/except fallback keeps 0.4.x importable during the floor transition, now moot with the pin bump.
* **Test flake-guard `_skip_on_upstream_outage` catches typed `MatVisError` subclasses** (`HTTPFetchError`, `NetworkError`) alongside raw `urllib.error.HTTPError`. Two new tests pin the typed paths.
* **Docstrings refreshed** for `.mtlx.xml()` in `core.py` + `_model.py` (class + property docs). py-mat code never called `.xml` directly — the change only bites downstream consumers who copied the old form.

### Added

* **`tests/_visual_compare.py`** — PIL-based RMS pixel-diff comparator with a `MAT_VIS_UPDATE_BASELINES=1` regeneration mode. Closes the last two checkboxes on [#41](https://github.com/MorePET/mat/issues/41) (baselines + tolerance threshold). Absent baseline → soft-skip with a clear regen instruction; framework is usable without a pre-generation ritual.
* **`tests/test_visual_compare.py`** — 12 unit tests for the comparator (within/beyond tolerance, size mismatch, missing-baseline skip, update-mode write, per-test tolerance override). Runs without Playwright.
* **`.github/workflows/visual-regression.yml`** — adds `update_baselines` `workflow_dispatch` input that flips the env so the run produces fresh baselines in the artifact instead of comparing.
* **`tests/baselines/README.md`** — documents regeneration workflow (local + CI-artifact path) and tolerance rationale.

### Fixed

* **e2e tests soft-skip when the mat-vis index returns empty**. `test_search_and_fetch` + `test_discover_finds_candidates` used to hard-assert `len(results) > 0`, which fires when a fresh CI runner has no seeded indexes. They now `pytest.skip` with a clear reason; the follow-on fetch/PNG assertions stay hard.

### Internal

* `.gitignore` excludes `.claude/` (Claude Code session state) and `examples/output/` (ad-hoc script output).

### Migration

See [docs/migration/v2-to-v3.md § 3.1 → 3.2](docs/migration/v2-to-v3.md#31--32-mat-vis-client-05-adoption).

## [3.1.2] - 2026-04-19

Post-3.1 audit follow-ups ([milestone 1](https://github.com/MorePET/mat/milestone/1)).
Three parallel agents reviewed the 3.1 + 3.1.1 surface from different angles
(DX, API good-practice checklist, adversarial); this release addresses the
13 issues they filed.

### Fixed

* **Dropped the misleading `from mat_vis_client import adapters` re-export** (#59). `pymat.vis.adapters` now unambiguously resolves to the local submodule (Material-accepting signatures). A regression test pins `adapters.__name__ == "pymat.vis.adapters"` and the one-param signature.
* **Renamed `Vis.get(field, default)` → `Vis.get(name, default)`** (#60) to stop shadowing `dataclasses.field` imported at module scope. Signature test pins the rename.
* **`vis.source = vis.source` no longer clears the texture cache** (#64). `__setattr__` now short-circuits when the incoming value equals the current one — `vis.finish = vis.finish` is also a cache-safe no-op now.
* **`dataclasses.replace(vis, source="new")` no longer inherits stale cache** (#63). Added `__post_init__` that zeros `_textures` + `_fetched`; pickle round-trip still preserves cache because pickle goes through `__dict__.update`, not `__init__`.
* **`Vis.has_mapping` now requires `tier is not None`** (#67). An explicit `vis.tier = None` un-maps the Vis so delegates fail at the gate rather than downstream in the client.

### Added

* **`Vis._identity_args()` helper** (#65) returning `(source, material_id, tier)`. `.mtlx`, `.channels`, `.materialize`, and `_fetch` all route through it — consistent call-site shape so adding new delegates doesn't drift.
* **`Vis.set_identity(*, source=, material_id=, tier=)`** (#69) — atomic multi-field identity update with a single cache invalidation. `Material(vis={"source": ..., "material_id": ...})` constructor path routes identity through this so the material is never observed in a half-assigned state.
* **Round-trip tests** (#63): `copy.deepcopy`, `pickle.dumps/loads`, `dataclasses.replace(vis, ...)`. Pins the current correct-by-construction behavior so a future refactor can't silently regress any of them.
* **Thread-safety race reproducer test** (#72). Deterministically exhibits the documented two-thread double-fetch race by gating the mock client with `threading.Event`s. Pins the docstring claim — any future "look, we fixed it" removal of the warning needs to make this test go RED first.
* **`_fetched` equality test pinned independently of `_textures`** (#62), using `object.__setattr__` to bypass the invalidation hook. Guards against a future `field(compare=False)` regression on one field without the other.
* **`Vis.__post_init__`** zeros the lazy texture cache after every `@dataclass` construction. See #63 above for rationale.

### Changed

* **`Vis.discover()` is now an intentional ADR-0002 exception**, called out in a new section of the ADR. It's a tag-aware convenience wrapper (renames `metallic → metalness`, widens scalars to ranges, optionally mutates via `auto_set`) — translation layer behavior Principle 2 otherwise rejects, kept for ergonomics. Any *second* wrapper on `Vis` re-triggers the ADR conversation.
* **`Vis.source_id` is no longer described as "deprecated"** (#68). It's a read-only convenience property (joined `"source/material_id"`) useful for logs + CLI output. The setter raising `AttributeError` remains the breaking signal for write attempts.
* **`.channels` docstring clarifies the cache asymmetry with `.textures`** (#70). `.channels` reads from the client's in-memory rowmap (cheap, shared across instances); `.textures` caches per-instance because the payload is large PNG bytes.
* **Cross-referenced docstrings** (#71) so readers landing on either `pymat.vis.client()` (module function) or `material.vis.client` (property) find the other. Same singleton, two entry points.
* **Strengthened two weak tests** from the 3.1.1 red/green pass. `test_init_does_not_trip_invalidation` (#61) replaced with two tests that actually exercise the guard's invariant. Previous form passed even when the guard was deleted.

### Internal

* Filed [mat-vis#84](https://github.com/MorePET/mat-vis/issues/84) asking for `mat_vis_client._get_client` → `get_client` rename. Until that lands, py-mat reaches into the underscore symbol from six property bodies.

## [3.1.1] - 2026-04-19

### Fixed

* **Identity mutation now invalidates the lazy texture cache.** Assigning `vis.source`, `vis.material_id`, or `vis.tier` after a fetch populated `_textures` silently left the old bytes in place — only `.finish = ...` cleared the cache. Now any identity-field assignment triggers cache invalidation via `Vis.__setattr__`. Guarded against the dataclass `__init__` so construction doesn't trip the clear.
* **`Vis` equality no longer depends on cache state or `_finish` label.** Two `Vis` objects with the same identity + scalars now compare equal regardless of whether one has been lazy-fetched. Fixed by adding `field(compare=False, repr=False)` to `_textures`, `_fetched`, and `_finish`.
* `pymat.vis.adapters._extract_textures` — use `.has_mapping` instead of `source_id is None` (the string-concatenating convenience property; `has_mapping` is the clearer intent).
* Stale docstrings: `Vis` class docstring no longer claims `.source` is a MtlxSource (it's `.mtlx`); `_MaterialInternal.vis` docstring updated for the 3.1 two-field identity; `CONTRIBUTING.md` TOML template no longer shows the 3.0 `[pbr]` section or slashed-string finishes (new contributors copying it would produce TOMLs that raise on load).

### Added

* **`pymat.vis.to_threejs` / `to_gltf` / `export_mtlx` re-exported at top level.** Consumer `from pymat.vis import to_threejs` now works — previously they had to reach for `pymat.vis.adapters.to_threejs`, which was a dead-end in tab completion. `Vis.__doc__` now points at `pymat.vis.to_threejs(material)` as the main cross-tool handoff.
* **`FinishEntry` TypedDict** — types `Vis.finishes` as `dict[str, FinishEntry]` for `mypy`-friendly consumer code.
* `ResolvedChannel.has_texture` is now a derived `@property` (from `texture is not None`), removing the chance of representing the nonsense state `has_texture=True, texture=None`.
* Docstrings on `.textures`, `.channels`, `.mtlx` call out that first access performs network IO (blocking). Class-level note on thread-safety: `Vis` is not thread-safe per-instance; the shared `MatVisClient` is read-safe.
* New test classes `TestIdentityInvalidation` (5 cases) and `TestVisEquality` (2 cases) pin the bug-fix invariants with red/green coverage.

### Changed

* `Vis.base_color` typed as `tuple[float, float, float, float] | None` (was bare `tuple`); `Vis.emissive` typed as `tuple[float, float, float] | None`. No runtime change — just honest type hints for consumers.
* `Vis` class docstring expanded with a Thread safety section and a pointer to `pymat.vis.to_threejs`.

### Upstream

* Filed [mat-vis#84](https://github.com/MorePET/mat-vis/issues/84) asking for `mat_vis_client._get_client` → `get_client` rename. py-mat reaches into the underscore symbol from six property bodies; a public rename tightens the ADR-0002 "client exposed, not wrapped" contract.

## [3.1.0] - 2026-04-18

### Breaking

* **`Vis.source_id: str` split into `Vis.source: str` + `Vis.material_id: str`.** Matches `mat-vis-client`'s `(source, material_id, tier)` positional-arg shape end-to-end — no more `.split("/")` at every delegation site. `source_id` remains as a **read-only** convenience property returning `f"{source}/{material_id}"`; **assignment raises `AttributeError`**. Codified in [ADR-0002](docs/decisions/0002-vis-owns-identity-client-exposed.md).
* **TOML `[<material>.vis.finishes]` values are now inline tables.** The 3.0 slashed-string form (`brushed = "ambientcg/Metal012"`) raises `ValueError` on load. The 3.1 form:

  ```toml
    [stainless.vis.finishes]
    brushed = { source = "ambientcg", id = "Metal012" }
    polished = { source = "ambientcg", id = "Metal049A" }
    ```

  One-shot migrator ships at `scripts/migrate_toml_finishes.py`. Bundled TOMLs have been migrated. No deprecation cycle — consistent with the 3.0 PBR→vis stance.
* `Vis.finishes` value type changed from `dict[str, str]` (slashed) to `dict[str, dict[str, str]]` (`{"source": ..., "id": ...}`).

### Added

* **ADR-0002** — *`Material.vis` owns identity + scalars; `mat-vis-client` is exposed, not wrapped.* Codifies three principles (identity/scalars on `Vis`; client exposed not wrapped; material-keyed delegation sugar only), the ownership test for future API questions, and the rationale for the two-field split above.
* **Delegation sugar properties on `Vis`** — thin delegates that pre-fill `(source, material_id, tier)` from the material's identity:
  * `material.vis.mtlx` → `MtlxSource` (lazy MaterialX accessor; `.xml`, `.export(path)`, `.original`)
  * `material.vis.client` → the shared `MatVisClient` singleton (escape hatch for tier enumeration, cache management, discovery)
  * `material.vis.channels` → texture channel names for this material at this tier
  * `material.vis.materialize(out)` → PNG dump to disk
* `Vis.has_mapping` property — replaces `if vis.source_id is not None:` sniffs.
* `scripts/migrate_toml_finishes.py` — idempotent line-oriented rewriter for `[vis.finishes]` blocks. Supports `--check` and `--diff`.

### Changed

* `scripts/enrich_vis.py` — now emits 3.1 inline-table finish syntax. Also fixes a pre-existing bug where it wrote `default = "..."` inside `[vis.finishes]` (which collides with `[vis].default` semantics, per the design-review that informed ADR-0002).
* `tests/test_toml_integrity.py::test_vis_finishes_use_valid_source_ids` → `test_vis_finishes_have_valid_shape`. The single over-permissive slashed-string regex is replaced with two per-field regexes (`_SOURCE_RE` lowercase-dashed, `_MATERIAL_ID_RE` allows uppercase + dots) — catches malformed fields that the old combined regex couldn't distinguish.

## [3.0.0](https://github.com/MorePET/mat/compare/v2.1.1...v3.0.0) - 2026-04-18

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
