---
type: issue
state: open
created: 2026-04-18T23:01:56Z
updated: 2026-04-18T23:01:56Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/69
comments: 0
labels: enhancement
assignees: none
milestone: 3.1.2 — post-audit follow-ups
projects: none
parent: none
children: none
synced: 2026-04-19T04:44:01.558Z
---

# [Issue 69]: [Material(vis={...}) loops setattr, causing redundant cache invalidation per identity field](https://github.com/MorePET/mat/issues/69)

## Tier 3 — cosmetic perf

\`src/pymat/core.py:71-75\` (and the mirror at \`:591-593\`) applies the
\`vis={...}\` constructor kwarg by looping:

```python
if vis:
    for key, value in vis.items():
        setattr(mat.vis, key, value)
```

If the user passes \`vis={"source": "ambientcg", "material_id": "Metal012"}\`,
each \`setattr\` trips \`Vis.__setattr__\` — invalidating a cache that's
already empty (so no user-visible bug), but performing redundant work.

Worse: if the dict iteration order happens to set \`source\` first and
\`material_id\` second, there's a brief intermediate state where
\`has_mapping\` returns False (\`material_id is None\`). Only observable
under threading or reentrant code, but it's a representable
inconsistency.

## Fix

Batch the identity updates. Either:

**(a) Apply non-identity scalars first, then identity atomically:**

```python
if vis:
    # Split identity keys from scalars
    identity = {k: vis[k] for k in ("source", "material_id", "tier") if k in vis}
    scalars = {k: v for k, v in vis.items() if k not in ("source", "material_id", "tier")}

    for key, value in scalars.items():
        setattr(mat.vis, key, value)

    # Then set identity via a dedicated method that invalidates once
    if identity:
        mat.vis._set_identity(**identity)  # new method — see below
```

**(b) Add \`Vis._set_identity(source=None, material_id=None, tier=None)\`:**

```python
def _set_identity(self, *, source=None, material_id=None, tier=None):
    """Atomic identity update — all three fields in one invalidation."""
    if source is not None: super().__setattr__("source", source)
    if material_id is not None: super().__setattr__("material_id", material_id)
    if tier is not None: super().__setattr__("tier", tier)
    # Single invalidation regardless of how many fields changed
    super().__setattr__("_textures", {})
    super().__setattr__("_fetched", False)
```

## Test

```python
def test_atomic_identity_update_via_material_kwarg(self):
    m = Material(name="test", vis={"source": "a", "material_id": "b"})
    # has_mapping must be True after construction — never False
    # in an intermediate state
    assert m.vis.source == "a"
    assert m.vis.material_id == "b"
    assert m.vis.has_mapping

    # Verify single invalidation: prefill cache, then re-apply kwarg
    m.vis._textures = {"color": b"x"}
    m.vis._fetched = True
    m.vis._set_identity(source="c", material_id="d")
    assert m.vis._textures == {}
    # Confirm atomic: no race-window where only one was updated
```

Low priority. Ship if (b) gets picked up; skip if short-circuit from #64
lands first (that alone makes the redundant clears free).
