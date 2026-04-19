---
type: issue
state: open
created: 2026-04-18T23:02:15Z
updated: 2026-04-18T23:02:15Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/71
comments: 0
labels: documentation
assignees: none
milestone: 3.1.2 — post-audit follow-ups
projects: none
parent: none
children: none
synced: 2026-04-19T04:44:00.850Z
---

# [Issue 71]: [pymat.vis.client() (module function) vs .client (Vis property) — same concept, two spellings](https://github.com/MorePET/mat/issues/71)

## Tier 3 — documentation clarity

Two callables, one concept ("get the shared \`MatVisClient\` singleton"):

```python
from pymat import vis
c = vis.client()             # module-level function in pymat.vis.__init__

c = material.vis.client      # property on Vis — no parens
```

A brain-typo apart. The current docstrings don't cross-reference, so a
user who learns one won't immediately discover the other.

## Fix

Add a side-by-side callout in both docstrings:

**In \`pymat/vis/__init__.py\` \`client()\`:**

```
Note: if you already have a Material, `material.vis.client` is the
same singleton without the parens.
```

**In \`pymat/vis/_model.py\` \`Vis.client\` property:**

```
Note: if you don't have a Material yet (tier enumeration, cache
management), `pymat.vis.client()` is the module-level entry point.
```

## No code change

Naming stays the same — both spellings earn their keep:
- Module function is called before a material is picked.
- Instance property is called in material-keyed contexts.

The duplication is the feature; the docs should acknowledge it
explicitly.
