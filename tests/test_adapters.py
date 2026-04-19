"""Tests for pymat.vis.adapters — Material → format wrappers."""

from __future__ import annotations

import tempfile
from pathlib import Path

from pymat import Material
from pymat.vis.adapters import (
    _extract_scalars,
    _extract_textures,
    _rgba_to_hex,
    export_mtlx,
    to_gltf,
    to_threejs,
)


def _make_material(with_vis=False):
    """Create a test material with vis scalars."""
    m = Material(name="Test Steel")
    m.vis.metallic = 1.0
    m.vis.roughness = 0.3
    m.vis.base_color = (0.8, 0.8, 0.8, 1.0)
    m.vis.ior = 2.5
    m.vis.transmission = 0.0
    m.vis.clearcoat = 0.0
    m.vis.emissive = (0, 0, 0)
    if with_vis:
        # Identity must be set BEFORE the cache — assigning source /
        # material_id invalidates _textures + _fetched via Vis.__setattr__
        # (3.1.1 cache-invalidation behavior).
        m.vis.source = "ambientcg"
        m.vis.material_id = "Metal032"
        m.vis._textures = {
            "color": b"\x89PNG_color",
            "normal": b"\x89PNG_normal",
            "roughness": b"\x89PNG_roughness",
        }
        m.vis._fetched = True
    return m


class TestExtractScalars:
    def test_from_pbr(self):
        m = _make_material()
        s = _extract_scalars(m)
        assert s["metalness"] == 1.0
        assert s["roughness"] == 0.3
        assert s["ior"] == 2.5

    def test_vis_wins_over_pbr(self):
        m = _make_material()
        m.vis.roughness = 0.5  # vis override
        s = _extract_scalars(m)
        assert s["roughness"] == 0.5  # vis wins
        assert s["metalness"] == 1.0  # falls back to pbr

    def test_metallic_mapped_to_metalness(self):
        m = _make_material()
        s = _extract_scalars(m)
        assert "metalness" in s
        assert "metallic" not in s

    def test_base_color_emitted_as_color_hex(self):
        """mat-vis-client only formats color from color_hex — the extractor
        must convert our RGBA list to '#RRGGBB' or the final Three.js dict
        has no color at all (every material renders as default grey)."""
        m = _make_material()
        m.vis.base_color = (1.0, 0.0, 0.0, 1.0)
        s = _extract_scalars(m)
        assert s["color_hex"] == "#ff0000"
        assert "base_color" not in s  # RGBA form must not leak through


class TestRgbaToHex:
    def test_pure_red(self):
        assert _rgba_to_hex([1.0, 0.0, 0.0, 1.0]) == "#ff0000"

    def test_pure_green(self):
        assert _rgba_to_hex([0.0, 1.0, 0.0]) == "#00ff00"  # alpha optional

    def test_mid_grey(self):
        assert _rgba_to_hex([0.5, 0.5, 0.5]) == "#808080"

    def test_none_passthrough(self):
        assert _rgba_to_hex(None) is None

    def test_clamps_out_of_range(self):
        # PBR values can over/undershoot; don't raise, just clamp
        assert _rgba_to_hex([-0.1, 1.5, 0.5]) == "#00ff80"

    def test_alpha_ignored(self):
        assert _rgba_to_hex([1.0, 1.0, 1.0, 0.3]) == "#ffffff"  # alpha stripped


class TestExtractTextures:
    def test_no_vis_returns_empty(self):
        m = _make_material(with_vis=False)
        assert _extract_textures(m) == {}

    def test_with_vis_returns_textures(self):
        m = _make_material(with_vis=True)
        tex = _extract_textures(m)
        assert "color" in tex
        assert tex["color"] == b"\x89PNG_color"


class TestToThreejs:
    def test_scalar_only(self):
        m = _make_material(with_vis=False)
        d = to_threejs(m)
        assert d["metalness"] == 1.0
        assert d["roughness"] == 0.3
        assert "map" not in d  # no textures

    def test_with_textures(self):
        m = _make_material(with_vis=True)
        d = to_threejs(m)
        assert "map" in d  # base64 data URI
        assert d["map"].startswith("data:image/png;base64,")
        assert "normalMap" in d
        assert "roughnessMap" in d


class TestToGltf:
    def test_scalar_only(self):
        m = _make_material(with_vis=False)
        d = to_gltf(m)
        assert d["name"] == "Test Steel"
        assert "pbrMetallicRoughness" in d
        pbr = d["pbrMetallicRoughness"]
        assert pbr["metallicFactor"] == 1.0
        assert pbr["roughnessFactor"] == 0.3

    def test_with_textures(self):
        m = _make_material(with_vis=True)
        d = to_gltf(m)
        assert d["name"] == "Test Steel"


class TestExportMtlx:
    def test_export_creates_files(self):
        m = _make_material(with_vis=True)
        with tempfile.TemporaryDirectory() as tmp:
            mtlx_path = export_mtlx(m, Path(tmp))
            assert mtlx_path.exists()
            assert mtlx_path.suffix == ".mtlx"
            # Check textures were written as PNG files
            pngs = list(Path(tmp).glob("*.png"))
            assert len(pngs) == 3  # color, normal, roughness

    def test_export_no_textures(self):
        m = _make_material(with_vis=False)
        with tempfile.TemporaryDirectory() as tmp:
            mtlx_path = export_mtlx(m, Path(tmp))
            assert mtlx_path.exists()
            pngs = list(Path(tmp).glob("*.png"))
            assert len(pngs) == 0  # no textures


class TestAdapterPolymorphism:
    """Adapters accept either a Material or a Vis — same output.

    This is the property that lets ``Vis.to_gltf()`` method sugar
    delegate to the module-level adapter without a back-reference
    from Vis to its owning Material.
    """

    def test_to_threejs_material_and_vis_agree(self):
        m = _make_material()
        assert to_threejs(m) == to_threejs(m.vis)

    def test_to_gltf_material_and_vis_agree_on_pbr(self):
        m = _make_material()
        from_material = to_gltf(m)
        from_vis = to_gltf(m.vis, name=m.name)
        assert from_material == from_vis

    def test_to_gltf_vis_without_name_leaves_empty_string(self):
        m = _make_material()
        d = to_gltf(m.vis)  # no name= kwarg
        assert d["name"] == ""

    def test_export_mtlx_vis_accepts_name_kwarg(self):
        m = _make_material(with_vis=True)
        with tempfile.TemporaryDirectory() as tmp:
            # Via Vis + explicit name — filename stem must match.
            mtlx_path = export_mtlx(m.vis, Path(tmp), name="Stem")
            assert mtlx_path.exists()
            assert mtlx_path.stem == "Stem", f"expected stem 'Stem', got {mtlx_path.stem!r}"

    def test_export_mtlx_vis_without_name_falls_back(self):
        """A standalone Vis with no name= kwarg must not crash; the
        default stem is whatever the adapter picks (currently 'material')."""
        from pymat.vis._model import Vis

        # Construct a Vis fully detached from any Material — this is
        # the path a downstream like mat-vis-client might hit if they
        # adopted the same sugar independently.
        vis = Vis(source=None, material_id=None)  # no mapping → no textures
        with tempfile.TemporaryDirectory() as tmp:
            mtlx_path = export_mtlx(vis, Path(tmp))
            assert mtlx_path.exists()
            assert mtlx_path.stem != "", "empty stem would break filesystem writes"

    def test_resolve_vis_duck_typing_invariant(self):
        """``_resolve_vis_and_name`` distinguishes Material-vs-Vis via
        ``hasattr(obj, "vis")``. If Vis ever grows a ``.vis`` attribute
        (self-reference, alias, anything), the helper would recurse and
        misclassify. Pin that invariant here."""
        from pymat.vis._model import Vis

        vis = Vis(source="ambientcg", material_id="Metal032")
        assert not hasattr(vis, "vis"), (
            "Vis must not have a .vis attribute — would break the "
            "Material-vs-Vis duck-typing in adapter._resolve_vis_and_name. "
            "If this test starts failing, the helper needs an "
            "isinstance check instead of hasattr."
        )

    def test_adapter_name_is_keyword_only(self):
        """``to_gltf(obj, name=...)`` must be keyword-only. Positional
        call should be a TypeError — prevents a downstream relying on
        positional ordering that could silently shift on a future
        signature change."""
        import pytest

        from pymat.vis._model import Vis

        vis = Vis()
        with pytest.raises(TypeError):
            to_gltf(vis, "positional_name")  # type: ignore[misc]


class TestAdapterOnDetachedVis:
    """Full-path tests that construct a Vis without any Material,
    verifying every adapter still works on the raw payload object.
    This is the contract downstreams (including a hypothetical
    mat-vis-client VisAsset) can rely on."""

    def _detached_vis_with_scalars(self):
        from pymat.vis._model import Vis

        v = Vis()
        v.metallic = 1.0
        v.roughness = 0.25
        v.base_color = (0.9, 0.9, 0.9, 1.0)
        v.ior = 1.5
        v.transmission = 0.0
        return v

    def test_to_threejs_on_detached_vis(self):
        v = self._detached_vis_with_scalars()
        d = to_threejs(v)
        assert d["metalness"] == 1.0
        assert d["roughness"] == 0.25
        assert "ior" in d  # ior scalar routed through

    def test_to_gltf_on_detached_vis_empty_name(self):
        v = self._detached_vis_with_scalars()
        d = to_gltf(v)
        assert d["pbrMetallicRoughness"]["metallicFactor"] == 1.0
        assert d["name"] == ""  # no owning Material, no name kwarg

    def test_to_gltf_on_detached_vis_with_name(self):
        v = self._detached_vis_with_scalars()
        d = to_gltf(v, name="Hand-rolled")
        assert d["name"] == "Hand-rolled"

    def test_vis_method_on_detached_vis(self):
        """The method form must also work on a detached Vis — covers
        the common case of ``Vis().to_gltf(name='...')`` in downstream
        code that constructs Vis without a py-mat Material."""
        v = self._detached_vis_with_scalars()
        assert v.to_gltf(name="X") == to_gltf(v, name="X")
        assert v.to_threejs() == to_threejs(v)

    def test_method_call_surface_present(self):
        """``m.vis.<TAB>`` must surface the three adapter methods —
        that's the whole point of this sugar."""
        v = self._detached_vis_with_scalars()
        for name in ("to_threejs", "to_gltf", "export_mtlx"):
            attr = getattr(v, name, None)
            assert attr is not None, f"Vis.{name} missing"
            assert callable(attr), f"Vis.{name} not callable"


class TestVisAdapterMethods:
    """Method-form sugar on Vis — discoverability via tab completion.

    Must be a drop-in shorthand: ``m.vis.to_gltf()`` and
    ``pymat.vis.to_gltf(m)`` must produce the same dict. Same for
    ``to_threejs`` and ``export_mtlx``.
    """

    def test_vis_to_threejs_matches_module_level(self):
        m = _make_material()
        assert m.vis.to_threejs() == to_threejs(m)

    def test_vis_to_gltf_matches_module_level_with_name(self):
        m = _make_material()
        assert m.vis.to_gltf(name=m.name) == to_gltf(m)

    def test_vis_to_gltf_no_name_leaves_empty(self):
        """Vis.to_gltf() without name= produces an empty name field —
        the method can't reach the owning Material without a back-ref,
        so users on a standalone Vis path opt in by passing name="X"."""
        m = _make_material()
        d = m.vis.to_gltf()
        assert d["name"] == ""

    def test_vis_export_mtlx_delegates(self):
        m = _make_material(with_vis=True)
        with tempfile.TemporaryDirectory() as tmp:
            mtlx_path = m.vis.export_mtlx(Path(tmp), name="ViaMethod")
            assert mtlx_path.exists()
            assert mtlx_path.suffix == ".mtlx"
