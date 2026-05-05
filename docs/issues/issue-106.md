---
type: issue
state: open
created: 2026-05-04T12:33:30Z
updated: 2026-05-04T12:33:30Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/106
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-05-05T04:54:34.522Z
---

# [Issue 106]: [examples + Vis docstring teach the unsafe mutation pattern](https://github.com/MorePET/mat/issues/106)

DX review of 3.6.0 found the canonical example file teaches the registry-mutation hazard \`Vis.override\` was created to fix.

### Where

- \`examples/build123d_integration.py\` — does \`s304.vis.finish = \"brushed\"\` and even comments \"restore so downstream cells see consistent state\" — i.e. demonstrates the hazard *and the workaround*.
- \`src/pymat/vis/_model.py\` — \`Vis\` class docstring shows \`steel.vis.finish = \"polished\"\` as the canonical idiom. New users read this, copy the pattern, silently corrupt the registry singleton.

### Why this matters

Users learn idioms from the class docstring and the example file, not the CHANGELOG. As long as both teach mutation, \`override\` is invisible no matter how good the implementation is.

### Fix

- Update the \`Vis\` class docstring quickstart to show \`override\` as the canonical derive path.
- Update \`examples/build123d_integration.py\` to use \`m.vis = m.vis.override(finish=\"brushed\")\` (or, once #109 lands, \`m = m.with_vis(vis.override(...))\`). Keep one cell showing the in-place mutation only with an explicit "OK because we just constructed this Material" caveat.
- Add to \`pymat/vis/__init__.py\` module docstring: one sentence on registry-singleton semantics + override.

Closes the gap. Block on #109 (Material.copy / with_vis) before finalizing the example, since today \`m.vis = ...\` still mutates the Material singleton.
