---
type: issue
state: closed
created: 2026-04-22T09:22:37Z
updated: 2026-05-06T18:54:45Z
author: bernhard-42
author_url: https://github.com/bernhard-42
url: https://github.com/MorePET/mat/issues/98
comments: 1
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-05-07T05:24:05.514Z
---

# [Issue 98]: [[BUG] material.vis returns object of a class in a private model](https://github.com/MorePET/mat/issues/98)

### Description

`pymat.vis._model.Vis` which gets returned e.g. from `stainless.vis` looks like an internal implementation class

### Steps to Reproduce

```python
In [17]: from pymat import stainless

In [18]: stainless.vis
Out[18]: Vis(source='ambientcg', material_id='Metal012', tier='1k', finishes={'brushed': {'source': 'ambientcg', 'id': 'Metal012'}, 'polished': {'source': 'ambientcg', 'id': 'Metal049A'}, 'dirty': {'source': 'ambientcg', 'id': 'Metal049B'}}, roughness=0.3, metallic=1.0, base_color=(0.75, 0.75, 0.77, 1.0), ior=None, transmission=0.0, clearcoat=None, emissive=None)

In [19]: type(stainless.vis)
Out[19]: pymat.vis._model.Vis
```

In my code I now need to say 
```python
pbr: pymat.vis._model.Vis = stainless.vis
```

which looks like using an internal model not meant to be exposed.

Do I miss something?

### Expected Behavior

I would expect `Vis` to be a clearly public class (now private model in the module path)

### Actual Behavior

see above

### Environment

any

### Additional Context

_No response_

### Possible Solution

_No response_

### Changelog Category

Fixed
---

# [Comment #1]() by [gerchowl]()

_Posted on May 6, 2026 at 06:54 PM_

Shipped in [py-materials 3.10.0](https://pypi.org/project/py-materials/3.10.0/).

`Vis` / `VisDeltas` / `FinishEntry` are now formally public:
- `__module__` rewritten to `pymat.vis` so `type()`, `repr`, IDE auto-import, and Sphinx all surface the public path.
- `pymat.vis` module docstring documents the stability contract: field set follows semver; additive changes minor; renames need major.
- Pinned by `tests/test_vis.py::TestPublicApiContract`.

```python
from pymat.vis import Vis, VisDeltas, FinishEntry  # public
```

Underscore-prefixed paths (`pymat.vis._model`, `Vis._finish`, `Vis._textures`, `pymat.vis._client`) remain private.

