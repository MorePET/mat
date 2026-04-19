---
type: issue
state: open
created: 2026-04-18T23:00:32Z
updated: 2026-04-18T23:00:32Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/63
comments: 0
labels: none
assignees: none
milestone: 3.1.2 — post-audit follow-ups
projects: none
parent: none
children: none
synced: 2026-04-19T04:44:03.570Z
---

# [Issue 63]: [No round-trip coverage: copy.deepcopy / pickle / dataclasses.replace on Vis](https://github.com/MorePET/mat/issues/63)

## Tier 2 — coverage for things we're correct-by-construction about

The adversarial review noted: \`Vis\` is currently safe to \`copy.deepcopy\`,
\`pickle.dumps/loads\`, and pass through \`dataclasses.replace(vis, ...)\` —
but none of these paths have test coverage, so a future refactor of
\`__setattr__\` / \`__getstate__\` / field order could silently break any of
them.

## Scenarios to pin

1. **\`copy.deepcopy(vis)\`** — the copy should own its own cache; mutating
   the copy's \`source\` should not wipe the original's cache.
2. **\`pickle.dumps / loads(vis)\`** — round-tripping through pickle should
   preserve identity + finishes + scalars + cache state. (Pickle currently
   uses \`__dict__.update\`, so \`__setattr__\` isn't invoked per-field —
   but that's one \`__reduce__\` override away from being per-field.)
3. **\`dataclasses.replace(vis, source="new")\`** — currently goes through
   a fresh \`__init__\`, so the replaced Vis starts with \`_textures={}\` /
   \`_fetched=False\`. Pin this; it's the safe behavior but a refactor
   could regress.

## Test sketch

```python
class TestRoundTrips:
    def _populated(self):
        v = Vis(source="ambientcg", material_id="Metal012", tier="1k",
                finishes={"brushed": {"source": "ambientcg", "id": "Metal012"}},
                roughness=0.3, metallic=1.0)
        v._textures = {"color": b"cached"}
        v._fetched = True
        return v

    def test_deepcopy_independent_cache(self):
        import copy
        v = self._populated()
        v2 = copy.deepcopy(v)
        v2.source = "polyhaven"  # triggers cache clear on v2 only
        assert v._textures == {"color": b"cached"}
        assert v2._textures == {}

    def test_pickle_roundtrip_preserves_state(self):
        import pickle
        v = self._populated()
        v2 = pickle.loads(pickle.dumps(v))
        assert v == v2  # equality ignores cache per compare=False
        assert v2._fetched == v._fetched  # but round-trip preserves flag

    def test_dataclasses_replace_starts_unfetched(self):
        import dataclasses
        v = self._populated()
        v2 = dataclasses.replace(v, source="polyhaven")
        assert v2.source == "polyhaven"
        assert v2.material_id == "Metal012"  # preserved
        assert v2._fetched is False
        assert v2._textures == {}
```
