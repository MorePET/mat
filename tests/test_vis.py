"""Tests for the pymat.vis module — model, wiring, adapters."""

from __future__ import annotations

import pytest

from pymat.vis._model import Vis

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
                    "brushed": {"source": "ambientcg", "id": "Metal032"},
                    "polished": {"source": "ambientcg", "id": "Metal012"},
                },
            }
        )
        assert v.source == "ambientcg"
        assert v.material_id == "Metal032"
        assert v.finish == "brushed"
        assert v.finishes == {
            "brushed": {"source": "ambientcg", "id": "Metal032"},
            "polished": {"source": "ambientcg", "id": "Metal012"},
        }

    def test_from_toml_no_default_uses_first(self):
        v = Vis.from_toml(
            {
                "finishes": {
                    "matte": {"source": "polyhaven", "id": "metal_matte"},
                    "satin": {"source": "polyhaven", "id": "metal_satin"},
                }
            }
        )
        assert v.finish == "matte"
        assert v.source == "polyhaven"
        assert v.material_id == "metal_matte"

    def test_from_toml_empty(self):
        v = Vis.from_toml({})
        assert v.source is None
        assert v.material_id is None
        assert v.finishes == {}

    def test_from_toml_rejects_slashed_string(self):
        import pytest

        with pytest.raises(ValueError, match="slashed-string form"):
            Vis.from_toml(
                {
                    "default": "brushed",
                    "finishes": {"brushed": "ambientcg/Metal032"},
                }
            )


# ── Finish switching ──────────────────────────────────────────


class TestFinishSwitching:
    def test_switch_finish(self):
        v = Vis.from_toml(
            {
                "default": "brushed",
                "finishes": {
                    "brushed": {"source": "ambientcg", "id": "Metal032"},
                    "polished": {"source": "ambientcg", "id": "Metal012"},
                },
            }
        )
        assert (v.source, v.material_id) == ("ambientcg", "Metal032")

        v.finish = "polished"
        assert (v.source, v.material_id) == ("ambientcg", "Metal012")
        assert v.finish == "polished"

    def test_switch_clears_cache(self):
        v = Vis.from_toml(
            {
                "default": "a",
                "finishes": {
                    "a": {"source": "src", "id": "a"},
                    "b": {"source": "src", "id": "b"},
                },
            }
        )
        v._textures = {"color": b"fake_png"}
        v._fetched = True

        v.finish = "b"
        assert v._textures == {}
        assert v._fetched is False

    def test_switch_unknown_finish_raises(self):
        v = Vis.from_toml(
            {
                "default": "brushed",
                "finishes": {"brushed": {"source": "ambientcg", "id": "Metal032"}},
            }
        )
        with pytest.raises(ValueError, match="Unknown finish 'mirror'"):
            v.finish = "mirror"


# ── Cache invalidation on identity mutation ──────────────────


class TestIdentityInvalidation:
    """When any identity field (source / material_id / tier) changes after
    a fetch has populated _textures, the cache MUST be cleared. Otherwise
    the next `.textures` access returns stale bytes that belong to the
    previous (source, material_id, tier) tuple."""

    def _prefetched(self) -> Vis:
        v = Vis(source="src1", material_id="id1", tier="1k")
        v._textures = {"color": b"cached_for_src1_id1_1k"}
        v._fetched = True
        return v

    def test_source_change_clears_cache(self):
        v = self._prefetched()
        v.source = "src2"
        assert v._textures == {}
        assert v._fetched is False

    def test_material_id_change_clears_cache(self):
        v = self._prefetched()
        v.material_id = "id2"
        assert v._textures == {}
        assert v._fetched is False

    def test_tier_change_clears_cache(self):
        v = self._prefetched()
        v.tier = "2k"
        assert v._textures == {}
        assert v._fetched is False

    def test_non_identity_field_does_not_clear_cache(self):
        """Changing PBR scalars or finishes does NOT invalidate the
        texture cache — those live on Vis but are not part of
        (source, material_id, tier) identity."""
        v = self._prefetched()
        v.roughness = 0.5
        v.metallic = 1.0
        v.base_color = (0.5, 0.5, 0.5, 1.0)
        assert v._textures == {"color": b"cached_for_src1_id1_1k"}
        assert v._fetched is True

    def test_init_does_not_trip_invalidation(self):
        """Constructing a Vis should NOT attempt to clear a cache that
        doesn't exist yet — __setattr__ guard must tolerate partial
        __init__ state."""
        # If the guard is wrong, the dataclass __init__ for `source=`
        # would try to clear `_textures`/`_fetched` before they exist
        # and crash with AttributeError.
        v = Vis(source="x", material_id="y", tier="3k")
        assert v.source == "x"
        assert v._textures == {}  # default factory
        assert v._fetched is False


# ── Equality hygiene (cache state must not affect ==) ────────


class TestVisEquality:
    """Two Vis objects with the same identity + scalars are the same Vis,
    regardless of whether one has been lazy-fetched and the other hasn't.
    The default @dataclass __eq__ includes all fields — we need
    field(compare=False) on the internal cache fields to get this right.
    """

    def test_equality_ignores_fetched_textures(self):
        a = Vis(source="ambientcg", material_id="Metal012", roughness=0.3)
        b = Vis(source="ambientcg", material_id="Metal012", roughness=0.3)
        # a is lazy-fetched, b isn't
        a._textures = {"color": b"\x89PNG..."}
        a._fetched = True
        assert a == b, "fetch state must not affect equality"

    def test_equality_ignores_finish_internal_state(self):
        """The _finish tracking is internal bookkeeping. If two Vis have
        the same identity and finishes, they should compare equal even
        if one has had a .finish = ... setter called (and the other
        reached the same identity via direct assignment)."""
        finishes = {
            "brushed": {"source": "ambientcg", "id": "Metal012"},
            "polished": {"source": "ambientcg", "id": "Metal049A"},
        }
        a = Vis(
            source="ambientcg",
            material_id="Metal049A",
            finishes=finishes,
        )
        b = Vis(
            source="ambientcg",
            material_id="Metal012",
            finishes=finishes,
        )
        b.finish = "polished"  # ends at (ambientcg, Metal049A) but sets _finish="polished"
        # Both now point at ambientcg/Metal049A; _finish differs
        assert a.source == b.source == "ambientcg"
        assert a.material_id == b.material_id == "Metal049A"
        assert a == b, "internal _finish tracking must not affect equality"


# ── Textures access ──────────────────────────────────────────


class TestTextures:
    def test_no_mapping_returns_empty(self):
        v = Vis()
        assert v.textures == {}

    def test_with_mapping_attempts_fetch(self, monkeypatch):
        """Verify that accessing textures delegates to the client."""
        called = {}

        class FakeClient:
            def fetch_all_textures(self, source, material_id, *, tier="1k"):
                called["source"] = source
                called["material_id"] = material_id
                called["tier"] = tier
                return {"color": b"\x89PNG_mock"}

        # Override the shared client singleton
        import mat_vis_client as _client
        monkeypatch.setattr(_client, "_client", FakeClient())

        v = Vis(source="ambientcg", material_id="Metal032")
        textures = v.textures
        assert called == {"source": "ambientcg", "material_id": "Metal032", "tier": "1k"}
        assert textures["color"] == b"\x89PNG_mock"


# ── ResolvedChannel ──────────────────────────────────────────


class TestResolvedChannel:
    def _prefetched(self, textures):
        v = Vis(source="test", material_id="id")
        v._textures = textures
        v._fetched = True
        return v

    def test_texture_available(self):
        v = self._prefetched({"roughness": b"\x89PNG_roughness"})
        rc = v.resolve("roughness", scalar=0.3)
        assert rc.has_texture is True
        assert rc.texture == b"\x89PNG_roughness"
        assert rc.scalar == 0.3

    def test_texture_missing_fallback_to_scalar(self):
        v = self._prefetched({})
        rc = v.resolve("metalness", scalar=1.0)
        assert rc.has_texture is False
        assert rc.texture is None
        assert rc.scalar == 1.0

    def test_no_texture_no_scalar(self):
        v = Vis()
        # no mapping → textures returns {}
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
        assert candidates[0]["source"] == "ambientcg"
        assert candidates[0]["id"] == "Metal032"
        assert v.source is None  # not set without auto_set

    def test_discover_auto_set(self, monkeypatch):
        import mat_vis_client as _client

        mock_results = [
            {"id": "Metal032", "source": "ambientcg", "category": "metal", "score": 0.1},
        ]
        monkeypatch.setattr(_client, "search", lambda **kw: mock_results)

        v = Vis()
        v.discover(category="metal", auto_set=True)
        assert v.source == "ambientcg"
        assert v.material_id == "Metal032"

    def test_discover_no_results(self, monkeypatch):
        import mat_vis_client as _client

        monkeypatch.setattr(_client, "search", lambda **kw: [])

        v = Vis()
        candidates = v.discover(category="exotic")
        assert candidates == []
        assert v.source is None


# ── Material.vis wiring ──────────────────────────────────────


class TestMaterialVisWiring:
    def test_custom_material_gets_empty_vis(self):
        from pymat import Material

        m = Material(name="test-alloy", density=5.0)
        assert m.vis is not None
        assert m.vis.source is None
        assert m.vis.material_id is None
        assert m.vis.textures == {}

    def test_vis_is_settable(self):
        from pymat import Material

        m = Material(name="test")
        m.vis.source = "ambientcg"
        m.vis.material_id = "Wood001"
        assert m.vis.source == "ambientcg"
        assert m.vis.material_id == "Wood001"

    def test_source_id_is_read_only(self):
        from pymat import Material

        m = Material(name="test")
        m.vis.source = "ambientcg"
        m.vis.material_id = "Wood001"
        assert m.vis.source_id == "ambientcg/Wood001"  # read-only convenience

        with pytest.raises(AttributeError, match="read-only"):
            m.vis.source_id = "other/thing"

    def test_vis_same_instance_on_repeat_access(self):
        from pymat import Material

        m = Material(name="test")
        v1 = m.vis
        v2 = m.vis
        assert v1 is v2

    def test_toml_material_gets_populated_vis(self):
        from pymat import stainless

        assert stainless.vis.source == "ambientcg"
        assert stainless.vis.material_id == "Metal012"
        assert stainless.vis.finish == "brushed"
        assert "polished" in stainless.vis.finishes

    def test_child_without_vis_gets_empty(self):
        from pymat import stainless

        s304 = stainless.s304
        assert s304.vis.source is None
        assert s304.vis.material_id is None


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
        import mat_vis_client as _client

        from pymat import vis

        mock_results = [
            {
                "id": "Metal001",
                "source": "ambientcg",
                "category": "metal",
                "roughness": 0.3,
                "metalness": 1.0,
            },
        ]

        class MockClient:
            def __init__(self, **kw):
                pass

            @property
            def manifest(self):
                return {"release_tag": "mock", "tiers": {}}

            def sources(self, tier="1k"):
                return ["ambientcg"]

            def index(self, source):
                return mock_results

            def search(self, **kw):
                return mock_results

        monkeypatch.setattr(_client, "_client", MockClient())

        results = vis.search(category="metal")
        assert len(results) >= 1
        assert results[0]["id"] == "Metal001"

    def test_rowmap_entry_missing_material_raises(self, monkeypatch):
        import mat_vis_client as _client

        from pymat import vis

        class MockClient:
            def __init__(self, **kw):
                pass

            @property
            def manifest(self):
                return {"release_tag": "mock", "tiers": {}}

            def rowmap_entry(self, source, mid, **kw):
                raise KeyError("NotExist")

        monkeypatch.setattr(_client, "_client", MockClient())

        with pytest.raises(KeyError, match="NotExist"):
            vis.rowmap_entry("ambientcg", "NotExist")

    def test_search_filters_and_scores(self, monkeypatch):
        """Exercises tag-subset, roughness-range, metalness-range, scoring."""
        import mat_vis_client as _client

        from pymat import vis

        rows = [
            # matches all filters (brushed + silver tags, rough 0.3, met 1.0)
            {
                "id": "A",
                "source": "ambientcg",
                "category": "metal",
                "tags": ["brushed", "silver", "steel"],
                "roughness": 0.3,
                "metalness": 1.0,
            },
            # wrong tags (missing brushed) → filtered out
            {
                "id": "B",
                "source": "ambientcg",
                "category": "metal",
                "tags": ["silver"],
                "roughness": 0.3,
                "metalness": 1.0,
            },
            # roughness out of range → filtered out
            {
                "id": "C",
                "source": "ambientcg",
                "category": "metal",
                "tags": ["brushed", "silver"],
                "roughness": 0.9,
                "metalness": 1.0,
            },
            # metalness out of range → filtered out
            {
                "id": "D",
                "source": "ambientcg",
                "category": "metal",
                "tags": ["brushed", "silver"],
                "roughness": 0.3,
                "metalness": 0.0,
            },
            # wrong category → filtered out
            {
                "id": "E",
                "source": "ambientcg",
                "category": "wood",
                "tags": ["brushed", "silver"],
                "roughness": 0.3,
                "metalness": 1.0,
            },
            # matches but scores higher (roughness distance > A's)
            {
                "id": "F",
                "source": "ambientcg",
                "category": "metal",
                "tags": ["brushed", "silver"],
                "roughness": 0.45,
                "metalness": 1.0,
            },
        ]

        class MockClient:
            def __init__(self, **kw):
                pass

            @property
            def manifest(self):
                return {"release_tag": "mock", "tiers": {}}

            def sources(self, tier="1k"):
                return ["ambientcg"]

            def index(self, source):
                return rows

        monkeypatch.setattr(_client, "_client", MockClient())

        results = vis.search(
            category="metal",
            tags=["brushed", "silver"],
            roughness=0.3,
            metalness=1.0,
        )
        ids = [r["id"] for r in results]
        assert ids[0] == "A"  # perfect-score entry sorts first
        assert "F" in ids  # matches filters, ranks lower
        assert "B" not in ids  # missing brushed tag
        assert "C" not in ids  # roughness out of ±0.2 range
        assert "D" not in ids  # metalness out of ±0.2 range
        assert "E" not in ids  # wrong category

    def test_search_source_iteration_swallows_index_errors(self, monkeypatch):
        """A broken source is skipped instead of failing the whole query."""
        import mat_vis_client as _client

        from pymat import vis

        class MockClient:
            def __init__(self, **kw):
                pass

            @property
            def manifest(self):
                return {"release_tag": "mock", "tiers": {}}

            def sources(self, tier="1k"):
                return ["ambientcg", "broken"]

            def index(self, source):
                if source == "broken":
                    raise RuntimeError("source index missing")
                return [{"id": "ok", "source": "ambientcg", "category": "metal"}]

        monkeypatch.setattr(_client, "_client", MockClient())

        results = vis.search(category="metal")
        assert [r["id"] for r in results] == ["ok"]

    def test_client_factory(self, monkeypatch):
        """vis.client() returns the lazy-initialized shared client."""
        import mat_vis_client as _client

        from pymat import vis

        sentinel = object()
        monkeypatch.setattr(_client, "_client", sentinel)
        assert vis.client() is sentinel
