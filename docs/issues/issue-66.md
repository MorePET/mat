---
type: issue
state: open
created: 2026-04-18T23:01:15Z
updated: 2026-04-18T23:01:15Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/66
comments: 0
labels: question
assignees: none
milestone: 3.1.2 — post-audit follow-ups
projects: none
parent: none
children: none
synced: 2026-04-19T04:44:02.588Z
---

# [Issue 66]: [Vis.discover() is a wrapper, not a thin delegate — ADR-0002 Principle 2 drift](https://github.com/MorePET/mat/issues/66)

## Tier 3 — design question flagged by adversarial review

\`Vis.discover()\` in \`src/pymat/vis/_model.py\` claims to be part of the
"thin delegate" set per [ADR-0002](https://github.com/MorePET/mat/blob/main/docs/decisions/0002-vis-owns-identity-client-exposed.md),
but it actually does translation:

```python
def discover(self, *, category=None, roughness=None, metallic=None,
             limit=5, auto_set=False):
    from mat_vis_client import search
    results = search(
        category=category,
        roughness=roughness,
        metalness=metallic,   # ← rename: metallic → metalness
        limit=limit,
    )
    if auto_set and results:
        top = results[0]
        self.source = top["source"]
        self.material_id = top["id"]
    return results
```

Three ways this violates Principle 2 ("client is exposed, not wrapped"):

1. Arg renaming: \`metallic\` → \`metalness\` (py-mat's internal name vs
   mat-vis-client's name).
2. \`auto_set=True\` side-effects the Vis — that's a mutation disguised
   as a search.
3. The underlying \`mat_vis_client.search\` already takes roughness +
   metalness as ranges (widened in \`pymat.vis.search\`). \`Vis.discover\`
   passes scalars through; they hit a different code path.

## Decision

**Option A — relocate:** move \`discover\` to a module function
\`pymat.vis.discover_for(material, ...)\` that takes a material
explicitly, and delete the method. Leaves \`Vis\` as pure
identity + scalars + delegate sugar.

**Option B — footnote the ADR:** acknowledge \`discover\` as the one
exception where py-mat does translation, because it's a search layered
over the client and the tag-aware semantics are genuinely py-mat-side.

## Recommendation

**(B)**. \`discover\` has been in \`Vis\` since pre-3.0 and the
\`auto_set=True\` convenience is genuinely useful on a Material.
Moving it to a module function loses the dotted sugar
(\`steel.vis.discover(...)\`) without a clear win. Footnote in
ADR-0002 Principle 2 describing \`.discover\` as the "tag-aware
convenience wrapper" exception.

## Labels

\`question\` — behavior stays the same either way; this is about
the documentation contract.
