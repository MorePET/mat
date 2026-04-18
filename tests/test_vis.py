"""Tests for the pymat.vis module — model, wiring, adapters."""

from __future__ import annotations

import pytest

from pymat.vis._model import ResolvedChannel, Vis


# ── Vis construction ──────────────────────────────────────────


class TestVisConstruction:
    def test_empty_vis(self):
        v = Vis()
        assert v.source_id is None
        assert v.finish is None
        assert v.finishes == {}
        assert v.textures == {}
        assert v.tier == "1k"

    def test_from_toml_with_default(self):
        v = Vis.from_toml(
            {
                "default": "brushed",
                "finishes": {
                    "brushed": "ambientcg/Metal032",
                    "polished": "ambientcg/Metal012",
                },
            }
        )
        assert v.source_id == "ambientcg/Metal032"
        assert v.finish == "brushed"
        assert v.finishes == {
            "brushed": "ambientcg/Metal032",
            "polished": "ambientcg/Metal012",
        }

    def test_from_toml_no_default_uses_first(self):
        v = Vis.from_toml(
            {
                "finishes": {
                    "matte": "polyhaven/metal_matte",
                    "satin": "polyhaven/metal_satin",
                }
            }
        )
        assert v.finish == "matte"
        assert v.source_id == "polyhaven/metal_matte"

    def test_from_toml_empty(self):
        v = Vis.from_toml({})
        assert v.source_id is None
        assert v.finishes == {}


# ── Finish switching ──────────────────────────────────────────


class TestFinishSwitching:
    def test_switch_finish(self):
        v = Vis.from_toml(
            {
                "default": "brushed",
                "finishes": {
                    "brushed": "ambientcg/Metal032",
                    "polished": "ambientcg/Metal012",
                },
            }
        )
        assert v.source_id == "ambientcg/Metal032"

        v.finish = "polished"
        assert v.source_id == "ambientcg/Metal012"
        assert v.finish == "polished"

    def test_switch_clears_cache(self):
        v = Vis.from_toml(
            {
                "default": "a",
                "finishes": {"a": "src/a", "b": "src/b"},
            }
        )
        # Simulate cached textures
        v._textures = {"color": b"fake_png"}
        v._fetched = True

        v.finish = "b"
        assert v._textures == {}
        assert v._fetched is False

    def test_switch_unknown_finish_raises(self):
        v = Vis.from_toml(
            {
                "default": "brushed",
                "finishes": {"brushed": "ambientcg/Metal032"},
            }
        )
        with pytest.raises(ValueError, match="Unknown finish 'mirror'"):
            v.finish = "mirror"


# ── Textures access ──────────────────────────────────────────


class TestTextures:
    def test_no_source_id_returns_empty(self):
        v = Vis()
        assert v.textures == {}

    def test_with_source_id_attempts_fetch(self, monkeypatch):
        """Verify that accessing textures triggers the fetch layer."""
        called = {}

        def mock_fetch(source, material_id, *, tier="1k", **kw):
            called["source"] = source
            called["material_id"] = material_id
            return {"color": b"\x89PNG_mock"}

        monkeypatch.setattr("mat_vis_client.fetch", mock_fetch)

        v = Vis(source_id="ambientcg/Metal032")
        textures = v.textures
        assert called["source"] == "ambientcg"
        assert called["material_id"] == "Metal032"
        assert textures["color"] == b"\x89PNG_mock"


# ── ResolvedChannel ──────────────────────────────────────────


class TestResolvedChannel:
    def test_texture_available(self):
        v = Vis()
        v._textures = {"roughness": b"\x89PNG_roughness"}
        v._fetched = True
        v.source_id = "test/id"  # set to avoid re-fetch

        rc = v.resolve("roughness", scalar=0.3)
        assert rc.has_texture is True
        assert rc.texture == b"\x89PNG_roughness"
        assert rc.scalar == 0.3

    def test_texture_missing_fallback_to_scalar(self):
        v = Vis()
        v._textures = {}
        v._fetched = True
        v.source_id = "test/id"

        rc = v.resolve("metalness", scalar=1.0)
        assert rc.has_texture is False
        assert rc.texture is None
        assert rc.scalar == 1.0

    def test_no_texture_no_scalar(self):
        v = Vis()
        # source_id is None → textures returns {}
        rc = v.resolve("color")
        assert rc.has_texture is False
        assert rc.texture is None
        assert rc.scalar is None


# ── Discover ─────────────────────────────────────────────────


class TestDiscover:
    def test_discover_returns_candidates(self, monkeypatch):
        import mat_vis_client as _client

        mock_results = [
            {"id": "Metal032", "source": "ambientcg", "category": "metal", "score": 0.1},
            {"id": "Metal012", "source": "ambientcg", "category": "metal", "score": 0.3},
        ]
        monkeypatch.setattr(_client, "search", lambda **kw: mock_results)

        v = Vis()
        candidates = v.discover(category="metal")
        assert len(candidates) == 2
        assert candidates[0]["id"] == "ambientcg/Metal032"
        assert v.source_id is None  # not set without auto_set

    def test_discover_auto_set(self, monkeypatch):
        import mat_vis_client as _client

        mock_results = [
            {"id": "Metal032", "source": "ambientcg", "category": "metal", "score": 0.1},
        ]
        monkeypatch.setattr(_client, "search", lambda **kw: mock_results)

        v = Vis()
        v.discover(category="metal", auto_set=True)
        assert v.source_id == "ambientcg/Metal032"

    def test_discover_no_results(self, monkeypatch):
        import mat_vis_client as _client

        monkeypatch.setattr(_client, "search", lambda **kw: [])

        v = Vis()
        candidates = v.discover(category="exotic")
        assert candidates == []
        assert v.source_id is None


# ── Material.vis wiring ──────────────────────────────────────


class TestMaterialVisWiring:
    def test_custom_material_gets_empty_vis(self):
        from pymat import Material

        m = Material(name="test-alloy", density=5.0)
        assert m.vis is not None
        assert m.vis.source_id is None
        assert m.vis.textures == {}

    def test_vis_is_settable(self):
        from pymat import Material

        m = Material(name="test")
        m.vis.source_id = "ambientcg/Wood001"
        assert m.vis.source_id == "ambientcg/Wood001"

    def test_vis_same_instance_on_repeat_access(self):
        from pymat import Material

        m = Material(name="test")
        v1 = m.vis
        v2 = m.vis
        assert v1 is v2

    def test_toml_material_gets_populated_vis(self):
        from pymat import stainless

        assert stainless.vis.source_id is not None
        assert stainless.vis.finish == "brushed"
        assert "polished" in stainless.vis.finishes

    def test_child_without_vis_gets_empty(self):
        from pymat import stainless

        # s304 has no [vis] section — gets empty Vis
        s304 = stainless.s304
        assert s304.vis.source_id is None


# ── Module-level API ─────────────────────────────────────────


class TestVisModuleApi:
    def test_import_vis(self):
        from pymat import vis

        assert hasattr(vis, "search")
        assert hasattr(vis, "fetch")
        assert hasattr(vis, "rowmap_entry")
        assert hasattr(vis, "get_manifest")

    def test_get_manifest_returns_dict(self):
        from pymat import vis

        manifest = vis.get_manifest()
        assert "release_tag" in manifest
        assert "tiers" in manifest

    def test_search_with_mock(self, monkeypatch):
        """Search against a mock client (no network)."""
        from pymat import vis
        import mat_vis_client as _client

        mock_results = [
            {"id": "Metal001", "source": "ambientcg", "category": "metal", "roughness": 0.3, "metalness": 1.0},
        ]

        class MockClient:
            def __init__(self, **kw): pass
            @property
            def manifest(self): return {"release_tag": "mock", "tiers": {}}
            def sources(self, tier="1k"): return ["ambientcg"]
            def index(self, source): return mock_results
            def search(self, **kw): return mock_results

        monkeypatch.setattr(_client, "_client", MockClient())

        results = vis.search(category="metal")
        assert len(results) >= 1
        assert results[0]["id"] == "Metal001"

    def test_rowmap_entry_missing_material_raises(self, monkeypatch):
        from pymat import vis
        import mat_vis_client as _client

        class MockClient:
            def __init__(self, **kw): pass
            @property
            def manifest(self): return {"release_tag": "mock", "tiers": {}}
            def rowmap_entry(self, source, mid, **kw):
                raise KeyError(f"NotExist")

        monkeypatch.setattr(_client, "_client", MockClient())

        with pytest.raises(KeyError, match="NotExist"):
            vis.rowmap_entry("ambientcg", "NotExist")
