---
type: issue
state: closed
created: 2026-04-18T21:40:44Z
updated: 2026-04-19T01:00:17Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/58
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-04-19T04:44:05.278Z
---

# [Issue 58]: [3.1: split Vis.source_id into Vis.source + Vis.material_id + ADR-0002](https://github.com/MorePET/mat/issues/58)

## Context

Follow-up to #40 (PBR→vis cutover, shipped in 3.0). `Material.vis` now owns the visual identity + scalars, but `source_id` is still a single slashed string (`"ambientcg/Metal012"`) that every delegation site has to `.split("/")` before calling mat-vis-client.

mat-vis-client exposes `(source, material_id, tier)` as three positional args everywhere. The slashed form was a py-mat TOML convenience that forces a translation step at every boundary crossing.

## Scope

1. **ADR-0002** — codify "`Material.vis` owns identity + scalars; mat-vis-client is exposed, not wrapped" so we stop relitigating the design (see mat-vis-client 0.4.x already treating `client.mtlx(...)` / `MtlxSource` as canonical; this ADR just writes down py-mat's side of that story).

2. **`Vis.source_id: str` → `Vis.source: str, Vis.material_id: str`.** Variable names match mat-vis-client's positional arg names end-to-end; no more string surgery.

3. **TOML schema: inline-table finishes** (Option A from the design review):
   ```toml
   [stainless.vis.finishes]
   brushed  = { source = "ambientcg", id = "Metal012" }
   polished = { source = "ambientcg", id = "Metal049A" }
   ```
   Chosen over default-source-plus-string-ids because:
   - 0% of materials actually mix sources today, but enrichment is designed to pull from polyhaven too — the default-source shape optimizes for today's accident and breaks the moment the first polyhaven finish lands.
   - Inline tables are positional-swap-safe and extend cleanly to per-finish `tier` overrides if we want them later.
   - Integrity test improves (separate regex for source vs id, instead of one over-permissive regex for the joined form).

4. **Delegation sugar on `Vis` per ADR-0002:**
   - `material.vis.source` → `MtlxSource` (pre-fills src/mid/tier to `client.mtlx()`)
   - `material.vis.client` → shared `MatVisClient` (escape hatch)
   - `material.vis.channels` → channel names for this material+tier
   - `material.vis.materialize(out)` → PNG dump to disk

5. **Break cleanly, no deprecation cycle** — consistent with the 3.0 PBR→vis stance. Loader raises on bare string finish values with a pointer to the migration doc.

## Not in scope

- `vis` inheritance between parent and child materials. Design review confirmed children don't inherit `vis` today (only `properties`) — if we want to change that, it's a separate loader PR and a separate discussion.
- Per-finish `tier` overrides. The inline-table shape extends cleanly to this later if needed, but out of scope here.

## Plan

- `docs/decisions/0002-vis-owns-identity-client-exposed.md` — new ADR
- `src/pymat/vis/_model.py` — rename fields, add delegation properties, update `from_toml` + `finish` setter
- `scripts/migrate_toml_finishes.py` — one-shot migrator for `src/pymat/data/*.toml`
- Fix pre-existing bug in `scripts/enrich_vis.py` output format (writes `default = "..."` which collides with `[vis].default` semantics; design review flagged)
- Tighten regex in `tests/test_toml_integrity.py` — separate source vs id charsets
- Update `docs/migration/v2-to-v3.md` → extend with the 3.1 breakage
- CHANGELOG `[3.1.0]` section
- Version bump `__version__` + `pyproject.toml` → 3.1.0

Targets 3.1.0 (breaking change → major-style but we're still pre-external-adoption).
