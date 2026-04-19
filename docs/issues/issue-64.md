---
type: issue
state: open
created: 2026-04-18T23:00:43Z
updated: 2026-04-18T23:00:43Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/64
comments: 0
labels: none
assignees: none
milestone: 3.1.2 — post-audit follow-ups
projects: none
parent: none
children: none
synced: 2026-04-19T04:44:03.244Z
---

# [Issue 64]: [vis.source = vis.source no-op silently clears the texture cache](https://github.com/MorePET/mat/issues/64)

## Tier 2 — small design question

\`Vis.__setattr__\` clears \`_textures\` + \`_fetched\` whenever \`source\`,
\`material_id\`, or \`tier\` is assigned — regardless of whether the new
value differs from the old one. So:

```python
vis = Material("stainless").vis
_ = vis.textures  # populates cache
vis.source = vis.source  # no-op in value, but clears cache
_ = vis.textures  # re-fetches
```

Same hazard in disguise: \`vis.finish = vis.finish\` (the finish setter
re-assigns source + material_id, which trip \`__setattr__\` even when the
new values equal the old).

## Decision

Pick one:

**(a) Short-circuit on equality** — add a pre-assignment check:

```python
def __setattr__(self, name, value):
    if name in _IDENTITY_FIELDS and "_fetched" in self.__dict__:
        if getattr(self, name, None) == value:
            super().__setattr__(name, value)
            return  # no invalidation for a no-op
    ...
```

**(b) Document and leave** — add a docstring note: "any assignment to
an identity field invalidates the cache, even if the new value equals
the current one. Compare first if you want to avoid re-fetch."

## Recommendation

**(a)** — the short-circuit is three lines and makes the invariant
"the cache is valid for the current identity" stable under idempotent
assignment. The current behavior is correct (cache is never *wrong*
after clearing) but wasteful and surprising.

## Test

```python
def test_no_op_identity_assignment_preserves_cache(self):
    v = Vis(source="ambientcg", material_id="Metal012")
    v._textures = {"color": b"cached"}
    v._fetched = True

    v.source = "ambientcg"  # no-op value
    assert v._textures == {"color": b"cached"}
    assert v._fetched is True
```

Under the current implementation this fails (RED). Option (a) makes it
pass.
