---
type: issue
state: open
created: 2026-05-04T12:34:13Z
updated: 2026-05-04T12:34:13Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/109
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-05-05T04:54:33.345Z
---

# [Issue 109]: [Material.copy / with_vis to close the parent-singleton hazard](https://github.com/MorePET/mat/issues/109)

DX review of 3.6.0: \`Vis.override\` is a half-solution.

### The remaining hazard

\`\`\`python
m = pymat[\"Stainless Steel 304\"]   # registry singleton
m.vis = m.vis.override(roughness=0.6)   # avoids Vis-mutation hazard
# ...but m IS still the registry singleton; m.vis = ... mutated it for everyone.
\`\`\`

User did the right thing for Vis and stepped straight into the same trap one level up. \`pymat.vis.to_threejs\` / \`to_gltf\` etc. take a \`Material\`, not a \`Vis\`, so the user is forced through this Material-mutation path.

### Proposal

Add either:

- \`Material.copy() -> Material\` — full copy, then \`m2.vis = m.vis.override(...)\` is safe.
- \`Material.with_vis(vis: Vis) -> Material\` — return a new Material sharing identity + properties but with a new Vis. More explicit and avoids accidentally diverging properties.

\`with_vis\` reads better and pairs with \`Vis.override\` to give a clean derive chain:

\`\`\`python
shiny = m.with_vis(m.vis.override(roughness=0.05, finish=\"polished\"))
pymat.vis.to_threejs(shiny)
\`\`\`

### Tests
- New Material is independent of the registry instance for both \`vis\` and \`properties\`.
- Identity (name, key, grade) preserved.
- Adapter round-trip via the new Material.

### Scope
3.7.0 — bundle with #103 / #104 / #105 / #106 fixes.
