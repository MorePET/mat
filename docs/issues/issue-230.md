---
type: issue
state: closed
created: 2026-05-08T08:26:25Z
updated: 2026-05-08T09:29:17Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/230
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-05-09T05:14:48.385Z
---

# [Issue 230]: [Vis.candidates: auto-query from self, Match-aware browse API (Phase 2 of dispatch refactor)](https://github.com/MorePET/mat/issues/230)

## Context

Phase 1 of the dispatch refactor (spike branch ``spike/vis-asset-dispatch``, closing mat#220 / mat-vis #285 / mat-vis #298) made ``Vis`` a thin delegate to mat-vis's ``client.asset(...)``. Phase 2 is the symmetric step on the *browse* side: surface mat-vis's ``search()`` / Match unification (mat-vis #359) on ``Vis`` so users can answer "what catalog appearances match this material?" without manually building queries.

## Today

``Vis.discover(*, category=None, roughness=None, metallic=None, limit=5, auto_set=False)`` exists but:

- The caller has to pass scalar/category filters explicitly — even when the calling Vis ALREADY has them set (``vis.roughness``, ``vis.metallic``, owning Material's category).
- ``auto_set=True`` mutates the Vis in place; no immutable variant.
- Returns ``list[dict]`` today; on mat-vis dev (#359) ``search()`` returns ``list[Match]`` — Phase 2 should pin the Match contract.
- No fuzzy name matching (``search(query=...)``) — but probably out of scope until upstream adds it.

## Proposed shape

\`\`\`python
class Vis:
    def candidates(
        self,
        *,
        # All optional — defaults derive from this Vis's own state
        category: str | None = None,        # else from owning Material's category (if set)
        roughness: float | None = None,     # else self.roughness
        metalness: float | None = None,     # else self.metallic
        roughness_range: tuple[float, float] | None = None,
        metalness_range: tuple[float, float] | None = None,
        source: str | None = None,
        tier: str = \"1k\",
        limit: int = 10,
    ) -> list[\"Match\"]:
        \"\"\"Find catalog appearances matching this material's properties.

        Auto-populates the search query from this Vis's own PBR scalars
        when filters aren't supplied. Returns Match handles ready to
        feed to ``client.asset(m)`` or assign back via ``vis.with_match(m)``.
        \"\"\"
        from mat_vis_client import search
        return search(
            category=category,  # caller-passed wins; else add owning-Material category lookup
            roughness=roughness if roughness is not None else self.roughness,
            metalness=metalness if metalness is not None else self.metallic,
            roughness_range=roughness_range,
            metalness_range=metalness_range,
            source=source,
            tier=tier,
            limit=limit,
        )

    def with_match(self, match: \"Match\") -> Vis:
        \"\"\"Return a new Vis with this Match's identity (source, id, tier).
        Immutable companion to ``set_identity`` / ``override``.\"\"\"
        return self.override(
            source=match.source,
            material_id=match.id,
            tier=match.tiers[0] if match.tiers else self.tier,
        )
\`\`\`

## Migration of existing ``discover()``

Two paths:

**A. Add ``candidates`` alongside; deprecate ``discover``.** ``discover`` was added before mat-vis #359; it pre-dates Match. ``candidates`` is the cleaner name (returns the candidate set; doesn't imply mutation). Mark ``discover`` deprecated in 3.x, remove in 4.x.

**B. Evolve ``discover`` in place.** Accept new auto-query semantics; keep the name. Less churn for existing callers; loses the chance to introduce ``with_match`` symmetry.

Recommendation: **A**. The semantics shift (auto-query, Match return, no mutation) is observable enough to warrant the new name.

## Acceptance

- [ ] ``vis.candidates()`` with no args returns matches scored against this Vis's own scalars (no manual roughness=, metalness=)
- [ ] Returns ``list[Match]`` post mat-vis #359; falls back gracefully on older client versions
- [ ] ``vis.with_match(match)`` returns a new Vis with the match's identity; original Vis unchanged
- [ ] ``vis.candidates()`` does NOT trigger texture HTTP fetches (search is index-only)
- [ ] Optional integration: when called on ``Material.vis``, look up Material's category for the search filter (today's ``discover`` doesn't auto-derive category either)
- [ ] **Forward verify**: round-trip the canonical Bernhard flow:
  \`\`\`python
  steel = pymat[\"Stainless Steel 304\"]
  for m in steel.vis.candidates():
      print(m)  # uses Match.__str__ — name + scalars + tiers
  picked = steel.with_vis(steel.vis.with_match(steel.vis.candidates()[0]))
  picked.vis.to_threejs()  # works end-to-end
  \`\`\`

## Out of scope

- **Name-fuzzy search** (``search(query=\"steel\")``) — needs upstream support; file separately if/when needed
- **Cross-tier discovery** (rank by which tier is staged) — a search ergonomics issue
- **Rendering candidates as thumbnails** — covered by mat-vis #362 (VisAsset.thumb)

## Related

- spike PR ``spike/vis-asset-dispatch`` (Phase 1 — render dispatch refactor)
- mat-vis #359 (Match unification — the substrate Phase 2 builds on)
- mat-vis #367 (``_scalars_for`` name resolution — orthogonal asymmetry, not blocking Phase 2)
- ADR-0002 Principle 3 (thin delegation sugar)
