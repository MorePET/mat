"""Tests for pymat.vis.adapters — Material → format wrappers."""

from __future__ import annotations

import tempfile
from pathlib import Path

from pymat import Material
from pymat.vis.adapters import (
    _extract_scalars,
    _extract_textures,
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
        m.vis._textures = {
            "color": b"\x89PNG_color",
            "normal": b"\x89PNG_normal",
            "roughness": b"\x89PNG_roughness",
        }
        m.vis._fetched = True
        m.vis.source_id = "ambientcg/Metal032"
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
            # Check PNGs were written
            pngs = list(Path(tmp).glob("*.png"))
            assert len(pngs) == 3  # color, normal, roughness

    def test_export_no_textures(self):
        m = _make_material(with_vis=False)
        with tempfile.TemporaryDirectory() as tmp:
            mtlx_path = export_mtlx(m, Path(tmp))
            assert mtlx_path.exists()
            pngs = list(Path(tmp).glob("*.png"))
            assert len(pngs) == 0  # no textures
