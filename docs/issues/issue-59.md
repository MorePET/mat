---
type: issue
state: closed
created: 2026-04-18T22:59:37Z
updated: 2026-04-19T01:00:18Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/59
comments: 0
labels: bug
assignees: none
milestone: 3.1.2 — post-audit follow-ups
projects: none
parent: none
children: none
synced: 2026-04-19T04:44:04.936Z
---

# [Issue 59]: [pymat.vis.adapters has a dual namespace (local wrapper vs mat-vis-client module)](https://github.com/MorePET/mat/issues/59)

## Tier 1 — time bomb flagged by the adversarial review

\`src/pymat/vis/__init__.py\` imports two different \`adapters\`:

```python
from mat_vis_client import (
    MatVisClient,
    adapters,  # noqa: F401    ← binds name `adapters` to mat_vis_client.adapters
    ...
)
...
from pymat.vis.adapters import export_mtlx, to_gltf, to_threejs
                  ↑
                  this is the local submodule src/pymat/vis/adapters.py
                  (different signature: takes Material, not (scalars, textures))
```

Depending on Python's submodule-import precedence vs explicit-import precedence,
\`pymat.vis.adapters\` can resolve to either the mat-vis-client module (primitive
signatures: \`(scalars_dict, textures_dict)\`) or the local wrapper module
(Material signature).

**Failure mode:** \`from pymat.vis import adapters; adapters.to_threejs(mat)\`
— if \`adapters\` resolves to mat-vis-client's version, the user gets a
\`TypeError\` about argument shape that's extremely unclear.

## Fix

Drop the \`from mat_vis_client import adapters\` line. The three concrete
adapter names are already re-exported (\`to_threejs\`, \`to_gltf\`,
\`export_mtlx\`) via \`from pymat.vis.adapters import ...\`, so removing the
module-level re-export loses nothing. Consumers who want the primitive-signature
versions can \`from mat_vis_client import adapters\` themselves.

## Test

Add a regression test in \`tests/test_vis.py\`:

```python
def test_pymat_vis_adapters_is_local_module():
    from pymat.vis import adapters
    # Must be the local wrapper, not mat_vis_client.adapters
    assert adapters.__name__ == "pymat.vis.adapters"

    # And the Material-accepting signature must hold
    import inspect
    sig = inspect.signature(adapters.to_threejs)
    params = list(sig.parameters.values())
    assert len(params) == 1 and params[0].name == "material"
```

## Labels

\`bug\` because the shadow is latent — not currently user-observed, but a
single \`from pymat.vis import adapters\` in a downstream tool surfaces it.
