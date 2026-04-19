"""
Tests for `pymat.pbr` — PbrSource Protocol + native backend serializer.

Covers the lite in-tree path (PBRProperties.to_dict) and the
Material.to_three_js_material_dict dispatch. The rich threejs-materials
backend is exercised via a duck-typed stub to avoid pulling the extra
into the base test dependency set. See ADR-0002.
"""

from __future__ import annotations

import pytest

from pymat import Material
from pymat.pbr import PbrSource
from pymat.properties import PBRProperties


class TestPbrSourceProtocol:
    """Native `PBRProperties` should satisfy the `PbrSource` Protocol."""

    def test_native_pbr_properties_is_pbr_source(self):
        pbr = PBRProperties()
        assert isinstance(pbr, PbrSource)

    def test_native_minimal_serialization(self):
        """Default PBRProperties emits only `color` (all other fields
        are at Three.js defaults and get omitted)."""
        pbr = PBRProperties()
        out = pbr.to_dict()
        assert out == {"color": [0.8, 0.8, 0.8]}

    def test_native_full_serialization(self):
        pbr = PBRProperties(
            base_color=(0.7, 0.2, 0.2, 0.8),
            metallic=1.0,
            roughness=0.25,
            transmission=0.3,
            clearcoat=0.5,
            normal_map="/path/to/normal.png",
        )
        out = pbr.to_dict()
        assert out["color"] == [0.7, 0.2, 0.2]
        assert out["metalness"] == 1.0
        assert out["roughness"] == 0.25
        assert out["transmission"] == 0.3
        assert out["clearcoat"] == 0.5
        assert out["opacity"] == pytest.approx(0.8)
        assert out["transparent"] is True
        assert out["normalMap"] == "/path/to/normal.png"


class TestMaterialToThreeJs:
    """`Material.to_three_js_material_dict()` picks the right backend."""

    def test_falls_back_to_native_pbr(self):
        steel = Material(
            name="Steel",
            density=7.85,
            pbr={"base_color": (0.6, 0.6, 0.65, 1.0), "metallic": 1.0},
        )
        out = steel.to_three_js_material_dict()
        assert out["color"] == [0.6, 0.6, 0.65]
        assert out["metalness"] == 1.0

    def test_pbr_source_takes_precedence(self):
        """When `pbr_source` is set, the native `properties.pbr` is ignored."""

        class FakeRichBackend:
            """Stub conforming to PbrSource Protocol."""

            def to_dict(self) -> dict:
                return {
                    "color": [0.91, 0.91, 0.88],
                    "metalness": 1.0,
                    "roughness": 0.05,
                    "normalMap": "textures/brushed_steel_normal.png",
                }

        steel = Material(
            name="Brushed Steel",
            density=7.85,
            pbr={"base_color": (0.3, 0.3, 0.3, 1.0)},  # would lose if used
            pbr_source=FakeRichBackend(),
        )
        out = steel.to_three_js_material_dict()
        # Rich backend's output, not the lite pbr dict.
        assert out["color"] == [0.91, 0.91, 0.88]
        assert out["normalMap"] == "textures/brushed_steel_normal.png"

    def test_pbr_source_stub_is_pbr_source(self):
        """Any class with `to_dict()` satisfies the Protocol."""

        class Stub:
            def to_dict(self):
                return {}

        assert isinstance(Stub(), PbrSource)

    def test_non_conforming_object_is_not_pbr_source(self):
        class NotPbr:
            pass

        assert not isinstance(NotPbr(), PbrSource)


class TestPbrBackfill:
    """
    When `pbr_source` is set, the rich backend's `to_dict()`
    output is projected onto the lite `properties.pbr` dataclass. This
    lets existing ocp_vscode / downstream renderers that only read
    `material.properties.pbr.<field>` pick up the rich data without
    needing adapter changes on their side. See ADR-0002 + the session
    discussion on MorePET/mat#3.
    """

    def _make_rich_backend(self):
        """Flat Three.js-shaped dict (matches the native lite backend's
        output shape)."""

        class RichBackend:
            def to_dict(self) -> dict:
                return {
                    "color": [0.91, 0.91, 0.88],
                    "metalness": 1.0,
                    "roughness": 0.08,
                    "ior": 2.5,
                    "transmission": 0.0,
                    "clearcoat": 0.2,
                    "emissive": [0.01, 0.01, 0.01],
                    "map": "cache/albedo.png",
                    "normalMap": "cache/normal.png",
                    "roughnessMap": "cache/roughness.png",
                    "metalnessMap": "cache/metalness.png",
                    "aoMap": "cache/ao.png",
                }

        return RichBackend()

    def _make_nested_rich_backend(self):
        """Nested `{values, textures}` dict shape — what
        `threejs_materials.PbrProperties.to_dict()` actually emits
        (verified against the real library at v1.0.4)."""

        class NestedBackend:
            def to_dict(self) -> dict:
                return {
                    "id": "ivory_walnut",
                    "name": "Ivory Walnut Solid Wood",
                    "source": "gpuopen",
                    "url": "https://matlib.gpuopen.com/...",
                    "license": "MIT Public Domain",
                    "values": {
                        "color": [0.8, 0.8, 0.8],  # neutral tint, map carries visual
                        "metalness": 0.0,
                        "roughness": 1.0,
                        "ior": 1.5,
                    },
                    "textures": {
                        "color": "data:image/png;base64,AAAA",  # albedo
                        "normal": "data:image/png;base64,BBBB",
                        "roughness": "data:image/png;base64,CCCC",
                    },
                }

        return NestedBackend()

    def test_backfill_populates_lite_scalars(self):
        steel = Material(
            name="Brushed Steel",
            density=7.85,
            pbr_source=self._make_rich_backend(),
        )
        lite = steel.properties.pbr
        assert lite.base_color[:3] == (0.91, 0.91, 0.88)
        assert lite.metallic == 1.0
        assert lite.roughness == 0.08
        assert lite.ior == 2.5
        assert lite.clearcoat == 0.2
        assert lite.emissive == (0.01, 0.01, 0.01)

    def test_backfill_populates_texture_maps(self):
        steel = Material(
            name="Brushed Steel",
            density=7.85,
            pbr_source=self._make_rich_backend(),
        )
        lite = steel.properties.pbr
        assert lite.base_color_map == "cache/albedo.png"
        assert lite.normal_map == "cache/normal.png"
        assert lite.roughness_map == "cache/roughness.png"
        assert lite.metallic_map == "cache/metalness.png"
        assert lite.ambient_occlusion_map == "cache/ao.png"

    def test_backfill_handles_nested_threejs_shape(self):
        """
        `threejs_materials.PbrProperties.to_dict()` emits a nested
        `{id, name, source, url, license, values: {...}, textures: {...}}`
        dict, NOT a flat Three.js MeshPhysicalMaterial dict. The
        backfill must read scalars from `values` and texture paths
        from `textures`. See ADR-0002 + the live verification on
        the build123d fork (gerchowl:feature/pymat-material-integration).
        """
        wood = Material(
            name="Walnut",
            density=0.65,
            pbr_source=self._make_nested_rich_backend(),
        )
        lite = wood.properties.pbr
        # Scalars from `values`.
        assert lite.base_color[:3] == (0.8, 0.8, 0.8)
        assert lite.metallic == 0.0
        assert lite.roughness == 1.0
        assert lite.ior == 1.5
        # Texture maps from `textures` (short names: color, normal, ...).
        assert lite.base_color_map == "data:image/png;base64,AAAA"
        assert lite.normal_map == "data:image/png;base64,BBBB"
        assert lite.roughness_map == "data:image/png;base64,CCCC"

    def test_backfill_existing_adapter_compat(self):
        """
        Simulate Bernhard's `_extract_materials_from_node` adapter:
        read from `material.properties.pbr.<field>` as he does today,
        verify the rich-backend data makes it through.
        """
        steel = Material(
            name="Brushed Steel",
            density=7.85,
            pbr_source=self._make_rich_backend(),
        )
        pbr = steel.properties.pbr
        simulated_extraction = {
            "color": pbr.base_color,
            "metalness": pbr.metallic,
            "roughness": pbr.roughness,
            "normal_map": pbr.normal_map,
            "roughness_map": pbr.roughness_map,
            "metalness_map": pbr.metallic_map,
            "ao_map": pbr.ambient_occlusion_map,
        }
        # Every field the adapter reads should carry the rich backend value.
        assert simulated_extraction["color"][:3] == (0.91, 0.91, 0.88)
        assert simulated_extraction["metalness"] == 1.0
        assert simulated_extraction["roughness"] == 0.08
        assert simulated_extraction["normal_map"] == "cache/normal.png"
        assert simulated_extraction["metalness_map"] == "cache/metalness.png"

    def test_backfill_noop_when_no_source(self):
        """With no pbr_source, lite dataclass keeps its authored values."""
        steel = Material(
            name="Steel",
            density=7.85,
            pbr={"base_color": (0.5, 0.5, 0.5, 1.0), "metallic": 0.3},
        )
        assert steel.properties.pbr.base_color == (0.5, 0.5, 0.5, 1.0)
        assert steel.properties.pbr.metallic == 0.3
        # Roughness stays at its dataclass default, not overridden.
        assert steel.properties.pbr.roughness == 0.5

    def test_rich_still_takes_precedence_in_dispatch(self):
        """
        Even with backfill, `Material.to_three_js_material_dict()` still
        prefers the rich `pbr_source` (full fidelity for callers that
        can handle extra fields).
        """
        rich = self._make_rich_backend()
        steel = Material(
            name="Brushed Steel",
            density=7.85,
            pbr_source=rich,
        )
        out = steel.to_three_js_material_dict()
        # Same object as rich's output, not re-serialized from lite.
        assert out == rich.to_dict()
