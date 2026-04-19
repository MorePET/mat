---
type: issue
state: open
created: 2026-04-18T22:59:49Z
updated: 2026-04-18T22:59:49Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/60
comments: 0
labels: bug
assignees: none
milestone: 3.1.2 — post-audit follow-ups
projects: none
parent: none
children: none
synced: 2026-04-19T04:44:04.597Z
---

# [Issue 60]: [Vis.get(field=..., default=...) parameter shadows dataclasses.field](https://github.com/MorePET/mat/issues/60)

## Tier 1 — latent footgun

\`src/pymat/vis/_model.py:371-380\`:

```python
def get(self, field: str, default: Any = None) -> Any:
    """..."""
    val = getattr(self, field, None)
    ...
```

The parameter name \`field\` shadows \`dataclasses.field\` (imported at module
top for the dataclass decorator — see line 40). Inside this method body,
any refactor that reaches for \`field(default_factory=...)\` or similar
silently grabs a string instead of the dataclass helper.

## Fix

Rename the parameter:

```python
def get(self, name: str, default: Any = None) -> Any:
```

All existing call sites use positional arg, so no breakage.

## Test

Not strictly necessary (lint would catch some refactor regressions), but
pinning the public signature prevents a future change from re-adding the
collision:

```python
def test_vis_get_param_is_name_not_field():
    import inspect
    from pymat.vis._model import Vis
    sig = inspect.signature(Vis.get)
    assert "name" in sig.parameters
    assert "field" not in sig.parameters  # don't shadow dataclasses.field
```
