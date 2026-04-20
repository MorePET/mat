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

    def test_init_guard_handles_partial_state(self):
        """The `"_fetched" in self.__dict__` guard in __setattr__ is
        load-bearing if dataclass field declaration order ever flips to
        put _textures / _fetched before source / material_id / tier.
        Today the order is identity-first, so the guard is theoretically
        redundant — but cheap insurance. Simulate the hostile case by
        constructing a Vis without going through @dataclass __init__."""
        # Bypass @dataclass __init__ to construct a half-initialized
        # object. The __setattr__ hook must tolerate `_fetched` missing.
        v = Vis.__new__(Vis)
        # Simulate the "identity set before cache fields" path that
        # would trip the hook on any future field-reorder refactor.
        # If the guard is deleted, this assignment still succeeds
        # (super().__setattr__ doesn't care whether _textures exists),
        # but the hook would attempt to clear two attrs that don't
        # exist yet — which on current Python is a silent no-op.
        v.source = "x"
        v.material_id = "y"
        v.tier = "3k"
        # Now attach the rest manually to round out the instance
        v.finishes = {}
        v.roughness = None
        v.metallic = None
        v.base_color = None
        v.ior = None
        v.transmission = None
        v.clearcoat = None
        v.emissive = None
        v._finish = None
        v._textures = {}
        v._fetched = False

        # All identity fields survived the hostile construction order
        assert (v.source, v.material_id, v.tier) == ("x", "y", "3k")

    def test_no_op_identity_assignment_preserves_cache(self):
        """Re-assigning source/material_id/tier to the same value must
        NOT clear the cache — otherwise `vis.source = vis.source` is a
        silent cache-buster. Closes #64."""
        v = Vis(source="ambientcg", material_id="Metal012", tier="1k")
        v._textures = {"color": b"cached"}
        v._fetched = True

        # No-op assignments
        v.source = "ambientcg"
        assert v._textures == {"color": b"cached"}
        assert v._fetched is True

        v.material_id = "Metal012"
        assert v._textures == {"color": b"cached"}
        assert v._fetched is True

        v.tier = "1k"
        assert v._textures == {"color": b"cached"}
        assert v._fetched is True

        # Real change still invalidates
        v.tier = "2k"
        assert v._textures == {}
        assert v._fetched is False

    def test_set_identity_batches_invalidation(self):
        """Vis.set_identity(source=..., material_id=...) updates multiple
        identity fields with a single cache invalidation. Closes #69."""
        v = Vis(source="src1", material_id="id1", tier="1k")
        v._textures = {"color": b"cached"}
        v._fetched = True

        v.set_identity(source="src2", material_id="id2")
        assert v.source == "src2"
        assert v.material_id == "id2"
        assert v.tier == "1k"  # unchanged
        assert v._textures == {}
        assert v._fetched is False

    def test_set_identity_no_change_no_invalidation(self):
        """If every passed value equals the current, set_identity is
        a no-op — cache stays populated."""
        v = Vis(source="src", material_id="id", tier="1k")
        v._textures = {"color": b"cached"}
        v._fetched = True

        v.set_identity(source="src", material_id="id", tier="1k")
        assert v._textures == {"color": b"cached"}
        assert v._fetched is True

    def test_material_vis_kwarg_avoids_half_assigned_state(self):
        """Material(name=..., vis={"source": ..., "material_id": ...})
        must route identity through set_identity — otherwise the
        individual setattrs leave the vis briefly in a
        half-assigned state (source set, material_id still None)."""
        from pymat import Material

        m = Material(
            name="test",
            vis={"source": "ambientcg", "material_id": "Metal012"},
        )
        assert m.vis.source == "ambientcg"
        assert m.vis.material_id == "Metal012"
        assert m.vis.has_mapping

    def test_finish_reassignment_to_same_preserves_cache(self):
        """`vis.finish = vis.finish` is a compound no-op: the setter
        re-writes source + material_id to the same values. Those
        must not clear the cache."""
        v = Vis.from_toml(
            {
                "default": "brushed",
                "finishes": {
                    "brushed": {"source": "ambientcg", "id": "Metal032"},
                    "polished": {"source": "ambientcg", "id": "Metal012"},
                },
            }
        )
        v._textures = {"color": b"cached"}
        v._fetched = True

        # Re-assign the same finish — source+material_id unchanged
        v.finish = "brushed"
        assert v._textures == {"color": b"cached"}
        assert v._fetched is True

        # Different finish → clear
        v.finish = "polished"
        assert v._textures == {}

    def test_init_via_dataclass_does_not_clear_default_cache(self):
        """Normal @dataclass construction. The guard prevents the
        __setattr__ hook from trying to wipe _textures / _fetched
        *after* they've been initialized by the default_factory, in
        the hypothetical future where @dataclass reorders assignments.
        Today it's pure future-proofing; pin the current behavior
        so a refactor that breaks it is caught in CI."""
        v = Vis(source="x", material_id="y", tier="3k")
        assert v._textures == {}
        assert v._fetched is False
        # Critically: the default_factory for _textures ran and
        # wasn't wiped. Mutating it afterwards and then re-setting
        # identity must still trigger the hook (the guard is only
        # for partial-state; post-init the hook fires normally).
        v._textures["probe"] = b"sentinel"
        v._fetched = True
        v.source = "x2"
        assert v._textures == {}
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

    def test_equality_ignores_fetched_flag_independently(self):
        """Pin field(compare=False) on _fetched separately from
        _textures. If a future refactor keeps compare=False on
        _textures but removes it on _fetched, test_equality_ignores
        _fetched_textures wouldn't catch the regression (it sets
        both simultaneously). This test only flips _fetched."""
        a = Vis(source="ambientcg", material_id="Metal012")
        b = Vis(source="ambientcg", material_id="Metal012")
        # Both start with _textures={}. Only the flag differs.
        # Use object.__setattr__ to bypass the cache-invalidation hook,
        # which would otherwise reset the flag back to False.
        object.__setattr__(a, "_fetched", True)
        assert a._fetched is True
        assert b._fetched is False
        assert a._textures == b._textures == {}
        assert a == b, "_fetched must not affect equality independently of _textures"

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


# ── Module shape regressions (#59, #60) ──────────────────────


class TestModuleShape:
    """Regressions pinned to catch shape drift flagged by the post-3.1
    adversarial audit (milestone 3.1.2)."""

    def test_pymat_vis_adapters_is_local_module(self):
        """`pymat.vis.adapters` must resolve to the LOCAL submodule
        (Material-accepting signatures), not mat-vis-client's adapters
        module (primitive-accepting signatures). Closes #59."""
        from pymat.vis import adapters

        assert adapters.__name__ == "pymat.vis.adapters", (
            f"expected local submodule, got {adapters.__name__}"
        )

        # And the Material-accepting signature must hold
        import inspect

        # First positional parameter must be the Material/Vis object.
        # 3.2+ renamed the param to ``obj`` for the polymorphic
        # Material|Vis signature; historically it was ``material``.
        params = list(inspect.signature(adapters.to_threejs).parameters)
        assert params and params[0] in {"material", "obj"}, (
            f"local to_threejs must accept a Material/Vis as first param, got params {params}"
        )

    def test_top_level_adapter_reexports(self):
        """`from pymat.vis import to_threejs` must work — otherwise
        consumers land on `pymat.vis` via tab-completion and find no
        breadcrumb to the cross-tool handoff."""
        from pymat import vis

        for name in ("to_threejs", "to_gltf", "export_mtlx"):
            assert hasattr(vis, name), f"pymat.vis missing re-export: {name}"
            assert callable(getattr(vis, name)), f"pymat.vis.{name} not callable"

    def test_has_mapping_requires_tier(self):
        """has_mapping must include tier — explicit None un-maps.
        Closes #67."""
        v = Vis(source="ambientcg", material_id="Metal012")
        assert v.has_mapping  # default tier="1k"
        v.tier = None
        assert not v.has_mapping, (
            "tier=None must un-map so delegates fail at the gate, not downstream in the client"
        )

    def test_identity_args_tuple(self):
        """Vis._identity_args() returns the positional-arg triple
        every mat-vis-client method expects. Closes #65."""
        v = Vis(source="ambientcg", material_id="Metal012", tier="2k")
        assert v._identity_args() == ("ambientcg", "Metal012", "2k")

    def test_deepcopy_isolates_cache(self):
        """copy.deepcopy produces an independent Vis; mutating the
        copy's identity must not affect the original's cache.
        Pins correct-by-construction behavior (closes #63)."""
        import copy

        v = Vis(source="ambientcg", material_id="Metal012", tier="1k")
        v._textures = {"color": b"cached_for_original"}
        v._fetched = True

        v2 = copy.deepcopy(v)
        # Sanity — deep copy preserves state
        assert v2.source == "ambientcg"
        assert v2._textures == {"color": b"cached_for_original"}
        assert v2._fetched is True

        # Mutate v2's identity — v stays untouched
        v2.source = "polyhaven"
        assert v2._textures == {}
        assert v._textures == {"color": b"cached_for_original"}  # untouched

    def test_pickle_roundtrip_preserves_state(self):
        """pickle.dumps → pickle.loads must preserve identity, finishes,
        scalars, and cache state. Default dataclass pickling goes
        through __dict__.update, which bypasses __setattr__ — pin
        this so a future __reduce__ override doesn't silently wipe
        the unpickled cache."""
        import pickle

        v = Vis(
            source="ambientcg",
            material_id="Metal012",
            tier="1k",
            finishes={"brushed": {"source": "ambientcg", "id": "Metal012"}},
            roughness=0.3,
            metallic=1.0,
        )
        v._textures = {"color": b"cached"}
        v._fetched = True
        v._finish = "brushed"

        v2 = pickle.loads(pickle.dumps(v))

        # Equality (ignores _textures/_fetched/_finish per compare=False)
        assert v == v2

        # But cache state is round-tripped — internal representation preserved
        assert v2._textures == {"color": b"cached"}
        assert v2._fetched is True
        assert v2._finish == "brushed"

    def test_dataclasses_replace_starts_unfetched(self):
        """dataclasses.replace constructs a fresh Vis via __init__,
        so the replaced instance starts with an empty cache — the
        new identity hasn't been fetched yet. Pin this so a future
        refactor can't silently copy the old cache through replace."""
        import dataclasses

        v = Vis(source="ambientcg", material_id="Metal012", tier="1k")
        v._textures = {"color": b"cached"}
        v._fetched = True

        v2 = dataclasses.replace(v, source="polyhaven")
        assert v2.source == "polyhaven"
        assert v2.material_id == "Metal012"
        assert v2.tier == "1k"
        # Cache starts empty for the new identity
        assert v2._textures == {}
        assert v2._fetched is False
        # Original untouched
        assert v._textures == {"color": b"cached"}

    def test_concurrent_textures_access_can_double_fetch(self, monkeypatch):
        """Documented behavior: ``Vis`` is not thread-safe per-instance.
        Two threads calling ``.textures`` simultaneously may each
        trigger a fetch because the ``_fetched`` flag is checked and
        set without synchronization.

        Pins the docstring claim in ``Vis`` (Thread safety section) so
        a future "this looks unnecessary" cleanup that removes the
        warning has a test that demonstrates the race is real.
        Closes #72."""
        import threading

        call_count = 0
        enter_event = threading.Event()
        proceed_event = threading.Event()

        class CountingClient:
            def fetch_all_textures(self, source, material_id, *, tier="1k"):
                nonlocal call_count
                call_count += 1
                enter_event.set()
                # Hold the window open long enough for the other thread
                # to also observe _fetched=False and enter this method.
                proceed_event.wait(timeout=2.0)
                return {"color": b"x"}

        import mat_vis_client as _client

        monkeypatch.setattr(_client, "_client", CountingClient())

        v = Vis(source="a", material_id="b")

        results = []

        def read():
            results.append(v.textures)

        t1 = threading.Thread(target=read)
        t2 = threading.Thread(target=read)
        t1.start()
        # Wait until t1 has entered the fetch (is waiting on proceed_event)
        assert enter_event.wait(timeout=1.0), "t1 never entered fetch — test setup broken"
        t2.start()
        # Both threads now in the fetch method (or t2 is about to enter).
        # Release both.
        proceed_event.set()
        t1.join()
        t2.join()

        # Document the race: at least one fetch happened; either one or
        # two, depending on whether t2 raced past the _fetched=False
        # check before t1 wrote _fetched=True. Both outcomes are
        # allowed by current Vis semantics; this test pins "not
        # thread-safe" by exercising the race path.
        assert call_count >= 1
        assert all(r == {"color": b"x"} for r in results)

    def test_vis_get_param_is_name_not_field(self):
        """`Vis.get(name=..., default=...)` — parameter must not be
        named `field` because that shadows `dataclasses.field` imported
        at module top. Closes #60."""
        import inspect

        sig = inspect.signature(Vis.get)
        assert "name" in sig.parameters
        assert "field" not in sig.parameters, "don't shadow dataclasses.field"


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

    def test_child_without_vis_inherits_from_parent(self):
        """3.4: grades without their own [vis] TOML section inherit
        the parent's vis via deep-copy at load time (#88). The prior
        contract returned a fresh empty Vis, which surprised consumers
        like build123d#1270 who expected s304 to render the same as
        stainless."""
        from pymat import stainless

        s304 = stainless.s304
        # Inherited identity + scalars from parent
        assert s304.vis.source == "ambientcg"
        assert s304.vis.material_id == "Metal012"
        assert s304.vis.metallic == 1.0
        # Cache is fresh (not shared with parent)
        assert s304.vis._textures == {}
        assert s304.vis._fetched is False


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
