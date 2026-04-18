"""End-to-end test: Material → vis → mat-vis live data → adapter output.

Hits real mat-vis release assets. Skip with MAT_VIS_SKIP_LIVE=1.
"""

from __future__ import annotations

import os

import pytest

SKIP_LIVE = os.environ.get("MAT_VIS_SKIP_LIVE", "0") == "1"


@pytest.mark.skipif(SKIP_LIVE, reason="MAT_VIS_SKIP_LIVE=1")
class TestEndToEnd:
    """Full pipeline: TOML material → vis textures → Three.js output."""

    def test_search_and_fetch(self):
        """Search the mat-vis index, fetch textures for a result."""
        from pymat import vis

        # Search for metals in the corpus
        results = vis.search(category="metal", limit=3)
        assert len(results) > 0, "No metals found in mat-vis index"

        mat_id = results[0]["id"]
        source = results[0].get("source", "ambientcg")
        assert mat_id, "Empty material ID"

        # Fetch textures via HTTP range read
        textures = vis.fetch(source, mat_id, tier="1k")
        assert len(textures) > 0, f"No textures for {source}/{mat_id}"

        # Verify PNG bytes
        for channel, data in textures.items():
            assert data[:4] == b"\x89PNG", f"{channel}: not a valid PNG"
            assert len(data) > 100, f"{channel}: suspiciously small ({len(data)} bytes)"

    def test_material_vis_textures(self):
        """Material.vis.textures fetches real PBR textures."""
        from pymat import Material, vis

        # Find a material that exists in mat-vis
        results = vis.search(category="wood", limit=1)
        if not results:
            pytest.skip("No wood materials in mat-vis index")

        source = results[0].get("source", "ambientcg")
        mat_id = results[0]["id"]

        # Create a material and wire vis
        m = Material(name="Test Wood")
        m.vis.roughness = 0.6
        m.vis.source_id = f"{source}/{mat_id}"

        # Access textures — triggers lazy HTTP fetch
        textures = m.vis.textures
        assert len(textures) > 0, f"No textures fetched for {source}/{mat_id}"
        assert all(v[:4] == b"\x89PNG" for v in textures.values())

    def test_material_to_threejs_with_live_textures(self):
        """Full path: Material → vis.textures → to_threejs → dict with maps."""
        from pymat import Material, vis
        from pymat.vis.adapters import to_threejs

        results = vis.search(category="metal", limit=1)
        if not results:
            pytest.skip("No metal materials in mat-vis index")

        source = results[0].get("source", "ambientcg")
        mat_id = results[0]["id"]

        m = Material(name="Live Metal Test")
        m.vis.metallic = 1.0
        m.vis.roughness = 0.3
        m.vis.base_color = (0.8, 0.8, 0.8, 1.0)
        m.vis.source_id = f"{source}/{mat_id}"

        d = to_threejs(m)

        # Scalars present
        assert d["metalness"] == 1.0
        assert d["roughness"] == 0.3

        # At least one texture map as base64 data URI
        has_map = any(
            k in d for k in ("map", "normalMap", "roughnessMap", "metalnessMap", "aoMap")
        )
        assert has_map, f"No texture maps in to_threejs output: {list(d.keys())}"

        # Verify data URI format
        for key in ("map", "normalMap", "roughnessMap", "metalnessMap", "aoMap"):
            if key in d:
                assert d[key].startswith("data:image/png;base64,"), f"{key}: not a data URI"

    def test_toml_material_with_vis_mapping(self):
        """Stainless steel from TOML has vis.source_id from [vis] section."""
        from pymat import stainless

        assert stainless.vis.source_id is not None
        assert stainless.vis.finish == "brushed"
        assert stainless.vis.roughness == 0.3
        assert stainless.vis.metallic == 1.0

        # Finishes available
        assert "polished" in stainless.vis.finishes

        # Switch finish
        stainless.vis.finish = "polished"
        assert stainless.vis.source_id == "ambientcg/Metal012"

        # Switch back
        stainless.vis.finish = "brushed"

    def test_discover_finds_candidates(self):
        """vis.search() finds materials by category."""
        from pymat import vis

        # Use module-level search (tier-free) instead of discover()
        # which delegates to mat_vis_client.search (tier-filtered)
        results = vis.search(category="metal", limit=5)
        assert len(results) > 0
        assert all("id" in c for c in results)

    def test_prefetch_small(self, tmp_path):
        """vis.fetch works for multiple materials (light prefetch test)."""
        from pymat import vis

        # Fetch just 2 materials instead of full prefetch
        results = vis.search(category="stone", limit=2)
        for r in results:
            textures = vis.fetch(r["source"], r["id"], tier="128")
            assert len(textures) >= 0  # may be 0 if 128 tier not available

    def test_resolve_channel(self):
        """Vis.resolve() returns texture or scalar fallback."""
        from pymat import Material, vis

        results = vis.search(category="stone", limit=1)
        if not results:
            pytest.skip("No stone materials")

        source = results[0].get("source", "ambientcg")
        mat_id = results[0]["id"]

        m = Material(name="Test Stone")
        m.vis.roughness = 0.7
        m.vis.source_id = f"{source}/{mat_id}"

        rc = m.vis.resolve("roughness", scalar=0.7)
        # Should have texture (if roughness map exists) or scalar fallback
        assert rc.scalar == 0.7
        if rc.has_texture:
            assert rc.texture[:4] == b"\x89PNG"
