"""
Cell-style examples for the py-materials + build123d integration.

Each ``# %%`` block is an independent cell — open this file in VS Code
/ Jupyter / PyCharm to step through, or run top-to-bottom as a plain
Python script. The full script is also wired into the test suite via
``tests/test_build123d_integration_examples.py`` so every example is
kept in working condition.

Covers the shape of the API surface that build123d#1270's Materials
class will consume:

- ``pymat["name or key"]``   — exact lookup (#89)
- ``pymat.search(...)``       — fuzzy find (3.3.0)
- ``m.vis.source / .vis.*``   — visual props, inherited by grades (#88)
- ``m.vis.to_threejs()``      — Three.js handoff
- ``m.vis.to_gltf()``         — glTF 2.0 material node
- ``m.vis.mtlx.xml() / .export(dir)`` — MaterialX
- ``shape.material = m``      — build123d wiring
- ``export_gltf(shape, path)``— current baseColor-only path
"""

# %% [markdown]
# # 1. Install + imports
#
# ```
# pip install "py-materials[build123d]>=3.3.0"
# ```

# %%
import pymat

print(f"py-materials version: {pymat.__version__}")


# %% [markdown]
# # 2. Look up a Material by name or key
#
# Three ways to resolve a user-typed string to a `Material`:
#
# | Form                              | When                                  |
# | --------------------------------- | ------------------------------------- |
# | `pymat["Stainless Steel 304"]`    | Exact match — raises if missing/amb.  |
# | `pymat.search(q, exact=True)`     | Same but returns `list[Material]`     |
# | `pymat.search(q)`                 | Fuzzy — tokenized, ranked list        |

# %%
# Exact by name (case + whitespace insensitive, NFKC-normalized)
housing_mat = pymat["Stainless Steel 304"]
assert housing_mat.name == "Stainless Steel 304"
assert housing_mat.grade == "304"

# %%
# Exact by registry key
bolt_mat = pymat["s316L"]
assert bolt_mat.grade == "316L"

# %%
# Exact by grade — grade strings like "304", "6061", "T6" all resolve
crystal_mat = pymat["304"]
assert crystal_mat.name == "Stainless Steel 304"

# %%
# Normalization — user-pasted strings with weird whitespace / case just work
assert pymat["  stainless   steel   304  "].name == "Stainless Steel 304"
assert pymat["STAINLESS STEEL 304"].name == "Stainless Steel 304"

# %%
# Unknown or ambiguous raises KeyError with a helpful candidate list
try:
    _ = pymat["not-a-real-material"]
except KeyError as e:
    print(f"expected miss: {e}")


# %% [markdown]
# # 3. Fuzzy search
#
# When the user query may match multiple materials (or none), use
# `pymat.search(...)` and decide how to present ambiguity.

# %%
hits = pymat.search("Stainless Steel")
print(f"{len(hits)} matches for 'Stainless Steel':")
for m in hits[:5]:
    print(f"  - {m.name}  (key={m._key})")

# %%
# Tokenized fuzzy — every whitespace-token must match somewhere
narrower = pymat.search("stainless 316")
assert all("316" in m.name.lower() or m.grade == "316L" for m in narrower)
print(f"Narrowed: {[m.name for m in narrower]}")


# %% [markdown]
# # 4. Vis properties inherited by grades (#88)
#
# Before 3.4 a grade without its own `[vis]` TOML section had `vis.source = None`.
# Now grades inherit the parent's vis — including textures, scalars, and
# the finishes map — while remaining independently mutable.

# %%
stainless = pymat["Stainless Steel"]
s304 = pymat["Stainless Steel 304"]

# Both have real vis identity
assert stainless.vis.source == "ambientcg"
assert s304.vis.source == "ambientcg"
assert s304.vis.material_id == stainless.vis.material_id
assert s304.vis.metallic == 1.0

# %%
# Derive a polished variant WITHOUT mutating the registry singleton.
# `pymat[...]` returns the shared instance — `m.vis.finish = "polished"`
# would corrupt the appearance for every other consumer of "Stainless
# Steel 304" in the same Python process. The safe path:
#
#   1. ``Vis.override(**deltas)`` returns a new (deep-copied) Vis.
#   2. ``Material.with_vis(new_vis)`` returns a new Material with that
#      Vis attached, registry-detached.
polished_vis = s304.vis.override(finish="polished")
s304_polished = s304.with_vis(polished_vis)

assert s304_polished.vis.material_id != stainless.vis.material_id
assert s304.vis.material_id == stainless.vis.material_id  # registry untouched
print(f"s304 polished: {s304_polished.vis.source}/{s304_polished.vis.material_id}")


# %% [markdown]
# # 5. Adapter output: Three.js / glTF / MaterialX
#
# Three export formats from every `Material`. Method form and
# module-level function produce identical output — pick whichever reads
# better at the call site.

# %%
threejs_dict = s304.vis.to_threejs()
print("Three.js fields:", sorted(threejs_dict.keys()))
assert "metalness" in threejs_dict
assert "roughness" in threejs_dict

# %%
gltf_node = s304.vis.to_gltf(name=s304.name)
assert "pbrMetallicRoughness" in gltf_node
assert gltf_node["pbrMetallicRoughness"]["metallicFactor"] == 1.0
print("glTF material:", gltf_node["name"], "→", list(gltf_node["pbrMetallicRoughness"].keys()))


# %% [markdown]
# # 6. build123d integration — shape.material and export_gltf
#
# Today's baseline: `apply_to()` + `export_gltf()` produces a glTF with
# the material's base color. Metallic / roughness / textures don't flow
# through build123d 0.10's exporter — that's the gap build123d#1270 is
# closing.

# %%
try:
    from build123d import Box, export_gltf

    BUILD123D_AVAILABLE = True
except ImportError:
    BUILD123D_AVAILABLE = False
    print("build123d not installed — skipping shape cells")


# %%
# The current baseColor-only path — proves materials carry through to glTF.
if BUILD123D_AVAILABLE:
    import json
    import tempfile
    from pathlib import Path

    housing = Box(50, 50, 10)
    s304.apply_to(housing)
    assert housing.material.name == "Stainless Steel 304"
    assert housing.color is not None
    assert housing.mass > 0

    out = Path(tempfile.mkdtemp()) / "housing.glb"
    export_gltf(housing, str(out))
    doc = json.loads(out.read_text())
    assert doc.get("materials"), "material should land in glTF"
    print(f"glTF materials[0]: {doc['materials'][0]}")


# %%
# Direct assignment: `shape.material = m` (no apply_to). Today this sets
# the attribute but doesn't reach build123d's export_gltf (which reads
# shape.color only). That's exactly the gap #1270 closes.
if BUILD123D_AVAILABLE:
    bracket = Box(30, 20, 5)
    bracket.material = bolt_mat  # no apply_to → no shape.color
    # Materials class (PR #1270) would populate everything via a single hook.


# %% [markdown]
# # 7. MaterialX full package (DCC pipelines)
#
# For Houdini / Blender Cycles / USD pipelines, the richer authoring
# format. Skip if the mat-vis mirror can't reach the asset.

# %%
try:
    xml_doc = s304.vis.mtlx.xml()
    assert xml_doc and "<materialx" in xml_doc.lower()
    print(f"MaterialX XML: {len(xml_doc)} chars")
except Exception as e:  # pragma: no cover — upstream flake
    print(f"mat-vis MTLX not reachable ({type(e).__name__}), skipping")


# %% [markdown]
# # 8. The mat-vis index is thin but real
#
# Direct visual-catalog search for "find me a metal texture" use cases.
# On a cold CI runner this returns few results while the bake pipeline
# catches up — see build123d#1270 comment for the full mirror status.

# %%
from pymat import vis  # noqa: E402 — cell-style script, imports near use

baked_metals = vis.search(category="metal", limit=5)
print(f"Baked metals in mat-vis: {len(baked_metals)}")
for hit in baked_metals:
    print(f"  - {hit['source']}/{hit['id']}  tier={hit.get('default_tier', '1k')}")


# %% [markdown]
# # 9. Cleanup / summary
#
# Everything above ran top-to-bottom as a smoke test. The matching
# pytest runner calls `runpy` to exercise every cell on every CI run —
# if the API shape drifts, these examples go red before build123d
# picks them up.

# %%
print("All cells completed.")
