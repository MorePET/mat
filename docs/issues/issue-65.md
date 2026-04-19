---
type: issue
state: open
created: 2026-04-18T23:00:54Z
updated: 2026-04-18T23:00:54Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/65
comments: 0
labels: enhancement
assignees: none
milestone: 3.1.2 — post-audit follow-ups
projects: none
parent: none
children: none
synced: 2026-04-19T04:44:02.912Z
---

# [Issue 65]: [Extract Vis._identity_args() helper to unify delegate call signatures](https://github.com/MorePET/mat/issues/65)

## Tier 2 — small refactor

Three delegation sugar properties use three different call shapes for
the same identity triple, flagged by the adversarial review
(\`src/pymat/vis/_model.py\`):

```python
# .mtlx — kwarg-style
return self.client.mtlx(self.source, self.material_id, tier=self.tier)

# .channels — positional
return self.client.channels(self.source, self.material_id, self.tier)

# .materialize — positional
return self.client.materialize(self.source, self.material_id, self.tier, output_dir)
```

If mat-vis-client ever makes \`tier\` keyword-only (\`*, tier: str = "1k"\`),
\`.channels\` + \`.materialize\` break while \`.mtlx\` keeps working — and the
breakage is silent-ish (\`TypeError: got positional arg for keyword-only\`).

## Fix

```python
def _identity_args(self) -> tuple[str, str, str]:
    """Return (source, material_id, tier) — the positional arg triple
    that mat-vis-client methods expect. Call guarded by has_mapping."""
    return (self.source, self.material_id, self.tier)

@property
def mtlx(self) -> MtlxSource | None:
    if not self.has_mapping:
        return None
    src, mid, tier = self._identity_args()
    return self.client.mtlx(src, mid, tier=tier)

# Same shape for .channels and .materialize.
```

## Test

```python
def test_identity_args_tuple(self):
    v = Vis(source="a", material_id="b", tier="2k")
    assert v._identity_args() == ("a", "b", "2k")
```

Plus: grep for every remaining \`self.client.X(self.source, self.material_id, ...)\`
and route through the helper. This is a consistency refactor — not
behavioral.

## Why a helper instead of explicit calls everywhere

The helper makes it one place to update when mat-vis-client changes
signatures. Also provides a seam for testing (monkeypatch
\`_identity_args\` to return a fixture triple).
