---
type: issue
state: open
created: 2026-04-18T23:02:08Z
updated: 2026-04-18T23:02:08Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/70
comments: 0
labels: enhancement
assignees: none
milestone: 3.1.2 — post-audit follow-ups
projects: none
parent: none
children: none
synced: 2026-04-19T04:44:01.206Z
---

# [Issue 70]: [Vis.channels has no cache but .textures does — asymmetric](https://github.com/MorePET/mat/issues/70)

## Tier 3 — consistency

The adversarial review flagged:

- \`Vis.textures\` is a property that fetches once and caches in
  \`_textures\` + \`_fetched\`.
- \`Vis.channels\` is a property that hits the client **on every access**
  with no cache:

```python
@property
def channels(self) -> list[str]:
    if not self.has_mapping:
        return []
    return self.client.channels(self.source, self.material_id, self.tier)
```

\`client.channels\` is cheap — it reads the rowmap, which is in-memory on
the client after the first fetch — but still asymmetric with
\`.textures\`. Two rationales to pick from:

## Options

**(a) Cache channels too.** Add \`_channels: list[str] | None = field(...)\`
and invalidate alongside \`_textures\` + \`_fetched\` in \`__setattr__\`.
Consistency.

**(b) Document the asymmetry.** Channels are cheap (rowmap lookup),
textures are expensive (HTTP range reads + PNG bytes). No need to
cache cheap.

## Recommendation

**(b)** — cache-everything is a trap. The adversarial review's
observation is fair but the cost model is real: channels lookup is
O(1) against an already-cached rowmap on the client. Adding a second
cache field doubles the invalidation surface for almost no gain.

## Minor action

Add one line to \`channels\` docstring noting "result comes from the
client's in-memory rowmap cache — cheap per-access, not cached on
this Vis."
