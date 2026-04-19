---
type: issue
state: open
created: 2026-04-18T23:00:13Z
updated: 2026-04-18T23:00:13Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/62
comments: 0
labels: none
assignees: none
milestone: 3.1.2 — post-audit follow-ups
projects: none
parent: none
children: none
synced: 2026-04-19T04:44:03.913Z
---

# [Issue 62]: [Equality tests don't independently pin compare=False on _fetched](https://github.com/MorePET/mat/issues/62)

## Tier 1 — weak test coverage

The adversarial review flags that \`tests/test_vis.py::TestVisEquality\` has
a gap: removing \`compare=False\` from \`_fetched\` individually (while keeping
it on \`_textures\`) leaves all current tests passing, because
\`test_equality_ignores_finish_internal_state\` ends with both sides having
the same empty cache (the \`finish\` setter clears \`_fetched=False\` on both).

So the test suite doesn't independently pin that \`_fetched\` is excluded
from equality.

## Add

```python
def test_equality_ignores_fetched_flag(self):
    """Two Vis with identical identity + scalars + textures must compare
    equal even if one has _fetched=True and the other has _fetched=False.
    Guards against someone removing field(compare=False) from _fetched
    but leaving it on _textures."""
    a = Vis(source="ambientcg", material_id="Metal012", roughness=0.3)
    b = Vis(source="ambientcg", material_id="Metal012", roughness=0.3)
    # Both have _textures={} by default; only the flag differs
    object.__setattr__(a, "_fetched", True)
    assert a == b, "_fetched must not affect equality"
```

(Using \`object.__setattr__\` to bypass the cache-invalidation hook so we
isolate the flag from the dict.)
