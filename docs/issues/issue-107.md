---
type: issue
state: closed
created: 2026-05-04T12:33:46Z
updated: 2026-05-04T12:37:14Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/107
comments: 1
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-05-05T04:54:34.118Z
---

# [Issue 107]: [DX: rename Vis.override → Vis.replace (mirrors dataclasses.replace)](https://github.com/MorePET/mat/issues/107)

DX review feedback: \`override\` fights Python convention and collides with terminology used elsewhere in the codebase.

### Convention pull

The Python ecosystem has settled on **\`replace\`** (\`dataclasses.replace\`, \`NamedTuple._replace\`, \`datetime.replace\`) and **\`evolve\`** (\`attrs.evolve\`) as the verb for \"return a derived copy with deltas applied\". \`override\` reads as a *mutation* verb (\"override this value\"), not derivation. The \`-> Vis\` return type is the only hint otherwise.

### Internal collision

\`override\` already means something else in this codebase: TOML inheritance overlays. See \`core.py: _add_child(**overrides)\` and the README's \"Override inherited property\" section. We now have two different meanings of \"override\" in one library.

### Proposal

1. Add \`Vis.replace\` as the canonical name. Same body.
2. Keep \`Vis.override\` as a thin alias for one minor cycle (3.7.x), emitting \`DeprecationWarning\`.
3. Drop \`override\` in 4.0.

### Get feedback before merging

Want a sanity check on whether the rename is worth the churn vs. shipping more docs that explain \`override\` is derive-not-mutate. Open question — leave open for one cycle to collect input before acting.
---

# [Comment #1]() by [gerchowl]()

_Posted on May 4, 2026 at 12:37 PM_

Three-reviewer split decision; keeping \`override\`.

**Resolution from independent feedback:**
- Ecosystem reviewer: rename (stdlib precedent strong)
- Domain reviewer: keep (codebase already teaches \"override\" for inheritance — runtime \`Vis.override\` is the runtime mirror of TOML grade override; collision is the feature)
- Cost reviewer: zero external callers detected; either choice is cheap

The domain-fit argument wins on internal grounds. The codebase's existing vocabulary (\`_add_child(**overrides)\`, \`merge_from_toml\`, README \"Override inherited property\") makes \`override\` the conceptually right verb here. A user who's read the README will reach for \`.override()\` first.

**Mitigation in 3.7.0:** add one-line docstring note distinguishing \`Vis.override\` from \`dataclasses.replace\` (derive vs. flat field substitution) and from the TOML-time \"override\" (runtime mirror, same concept).

