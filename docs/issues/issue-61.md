---
type: issue
state: open
created: 2026-04-18T23:00:04Z
updated: 2026-04-18T23:00:04Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/61
comments: 0
labels: none
assignees: none
milestone: 3.1.2 — post-audit follow-ups
projects: none
parent: none
children: none
synced: 2026-04-19T04:44:04.257Z
---

# [Issue 61]: [test_init_does_not_trip_invalidation passes even without the guard](https://github.com/MorePET/mat/issues/61)

## Tier 1 — weak test, flagged by the adversarial review

\`tests/test_vis.py::TestIdentityInvalidation::test_init_does_not_trip_invalidation\`
claims to verify the \`"_fetched" in self.__dict__\` guard in \`Vis.__setattr__\`.
The adversarial review notes: delete the guard entirely and the test still
passes. \`super().__setattr__("_textures", {})\` on a partially-initialized
object just sets the attribute — no AttributeError fires.

So the test pins a failure mode that doesn't exist, not the one the commit
message implies.

## What the test should actually pin

The real risk the guard protects against is: if the dataclass-generated
\`__init__\` order ever changes such that \`_textures\` / \`_fetched\` would
be assigned BEFORE \`source\` / \`material_id\` / \`tier\`, the later-assigned
identity fields would wipe the just-initialized cache. The field-declaration
order in \`_model.py\` makes this impossible today, but that's a fragile
contract (reorder the @dataclass fields and the guard is what saves you).

## Stronger test

```python
def test_init_guard_protects_against_reorder():
    """Validate the __setattr__ guard's actual purpose: preventing
    dataclass __init__ from wiping a freshly-set cache if field
    assignment order ever flips to put _textures before source."""
    from pymat.vis._model import Vis

    # Simulate the future-refactor ordering by manually constructing
    # an empty Vis, then poking state in the "wrong" order.
    v = Vis.__new__(Vis)
    # Set cache first (no guard protection if we didn't have the guard)
    object.__setattr__(v, "_textures", {"color": b"pre-existing"})
    object.__setattr__(v, "_fetched", True)
    # Now assigning source via the hook must NOT wipe the cache
    # — but it DOES, because post-init guard fires. Is that correct?
    v.source = "ambientcg"
    assert v._textures == {} and v._fetched is False  # current behavior

    # Actually, the GUARD ALLOWS THIS: identity was assigned AFTER
    # _fetched exists in __dict__. The guard is doing its job —
    # but it's protecting against the *opposite* case from what the
    # current test claims.
```

The honest fix is probably to delete the existing
\`test_init_does_not_trip_invalidation\` (theater) and replace it with a
comment in the guard explaining why it's there.

## Labels

No matching label on the repo — leaving unlabeled. Consider adding
\`test-quality\` to the label set.
