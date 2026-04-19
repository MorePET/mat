---
type: issue
state: open
created: 2026-04-18T23:01:23Z
updated: 2026-04-18T23:01:23Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/67
comments: 0
labels: enhancement
assignees: none
milestone: 3.1.2 — post-audit follow-ups
projects: none
parent: none
children: none
synced: 2026-04-19T04:44:02.253Z
---

# [Issue 67]: [has_mapping should include tier or tier should never be None](https://github.com/MorePET/mat/issues/67)

## Tier 3 — narrow edge, minor

\`Vis.has_mapping\` checks only \`source\` and \`material_id\`:

```python
@property
def has_mapping(self) -> bool:
    return self.source is not None and self.material_id is not None
```

But \`tier\` is also part of the identity triple. If someone sets
\`vis.tier = None\` explicitly (bypassing the default \`"1k"\`),
\`has_mapping\` still returns True but \`client.fetch_all_textures(src, id,
tier=None)\` will blow up downstream with an unhelpful error.

## Options

**(a) Gate in \`has_mapping\`:** add \`and self.tier is not None\`. Narrows
the bad-state surface.

**(b) Make tier required:** change the dataclass field to \`tier: str\`
(no \`None\`) with a non-None default. A \`vis.tier = None\` assignment
then fails at assignment time via a \`__setattr__\` guard.

**(c) Leave as-is:** the surface is very narrow (explicit \`None\` only;
default \`"1k"\`), and we have \`Tier 2/#63\` round-trip coverage that
would flush it.

## Recommendation

**(a)** is lowest-cost and most correct. (b) over-constrains for
the rare future where \`tier=None\` might mean "client default."

## Test

```python
def test_has_mapping_requires_tier(self):
    v = Vis(source="a", material_id="b")
    assert v.has_mapping  # default tier="1k"
    v.tier = None
    assert not v.has_mapping  # explicitly None → no mapping
```
