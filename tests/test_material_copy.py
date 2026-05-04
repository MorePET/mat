"""Tests for ``Material.copy()`` and ``Material.with_vis(...)`` (#109).

The motivating bug: ``pymat["..."]`` returns the registry singleton.
Even after `Vis.override` insulated the visual side, users still had
to do ``m.vis = m.vis.override(...)`` — mutating the *Material*
singleton (the new pitfall one level up). ``copy`` and ``with_vis``
close that hazard:

    shiny = m.with_vis(m.vis.override(roughness=0.05, finish="polished"))

Pinned semantics:

- ``copy()`` returns a Material whose vis / properties / property-group
  dicts are deep-copied; identity metadata (name, grade, etc.) preserved.
- The copy is registry-detached: ``_key`` is None, ``_children`` is {},
  ``parent`` retained for inheritance chain only.
- ``with_vis(vis)`` returns ``copy()`` with the new ``_vis`` attached.
- Adapters operating on the copy reflect the new state, not the registry.
"""

from __future__ import annotations

import pytest

from pymat import Material
from pymat.vis._model import Vis


class TestCopyReturnsIndependentInstance:
    def test_returns_new_instance(self):
        m = Material(name="probe", density=7.8)
        c = m.copy()
        assert c is not m

    def test_identity_metadata_preserved(self):
        m = Material(name="Stainless 304", grade="304", formula="FeCr18Ni8")
        c = m.copy()
        assert c.name == "Stainless 304"
        assert c.grade == "304"
        assert c.formula == "FeCr18Ni8"

    def test_properties_independent(self):
        m = Material(name="probe", density=7.8)
        c = m.copy()
        c.properties.mechanical.density = 12.0
        assert m.properties.mechanical.density == 7.8
        assert c.properties.mechanical.density == 12.0

    def test_vis_independent(self):
        m = Material(name="probe")
        m.vis.roughness = 0.3
        m.vis.metallic = 1.0
        c = m.copy()
        c.vis.roughness = 0.9
        assert m.vis.roughness == 0.3
        assert c.vis.roughness == 0.9

    def test_vis_finishes_independent(self):
        """Deep-copy reaches into nested vis state."""
        m = Material(name="probe")
        m.vis.finishes = {"a": {"source": "x", "id": "y"}}
        c = m.copy()
        c.vis.finishes["b"] = {"source": "z", "id": "w"}
        assert "b" not in m.vis.finishes
        assert "b" in c.vis.finishes


class TestCopyRegistryDetachment:
    def test_key_cleared_on_copy(self):
        import pymat

        steel = pymat["Stainless Steel 304"]
        c = steel.copy()
        assert c._key is None
        # Original still has its registry key
        assert steel._key is not None

    def test_children_emptied_on_copy(self):
        import pymat

        # stainless has child grades (s304, s316L, ...)
        stainless = pymat.stainless
        c = stainless.copy()
        assert c._children == {}
        # Original retains its children
        assert len(stainless._children) > 0

    def test_parent_preserved_for_inheritance_chain(self):
        """Copy stays parent-aware so property fallbacks still work."""
        import pymat

        s304 = pymat.stainless.s304
        c = s304.copy()
        assert c.parent is s304.parent  # same parent reference


class TestRegistryHazardClosed:
    def test_copy_isolates_vis_mutations_from_registry(self):
        import pymat

        steel = pymat["Stainless Steel 304"]
        original_roughness = steel.vis.roughness

        c = steel.copy()
        c.vis = c.vis.override(roughness=0.99)

        # Registry singleton untouched
        assert steel.vis.roughness == original_roughness

    def test_with_vis_isolates_vis_swap_from_registry(self):
        import pymat

        steel = pymat["Stainless Steel 304"]
        original_vis = steel.vis  # capture identity reference

        new_vis = steel.vis.override(roughness=0.05, finish="polished")
        shiny = steel.with_vis(new_vis)

        assert shiny is not steel
        # ``with_vis`` deep-copies the supplied vis (defends against
        # callers passing the registry's own .vis back in). Equality,
        # not identity, is the contract.
        assert shiny.vis == new_vis
        assert shiny.vis is not new_vis
        assert steel.vis is original_vis  # registry untouched


class TestWithVis:
    def test_returns_new_material(self):
        m = Material(name="probe")
        c = m.with_vis(Vis(source="ambientcg", material_id="Metal012"))
        assert c is not m

    def test_attaches_provided_vis(self):
        m = Material(name="probe")
        new_vis = Vis(source="ambientcg", material_id="Metal032", tier="2k")
        c = m.with_vis(new_vis)
        # Deep-copied — equal but not the same instance (defends against
        # the registry-singleton aliasing case).
        assert c.vis == new_vis
        assert c.vis is not new_vis
        assert c.vis.source == "ambientcg"
        assert c.vis.material_id == "Metal032"

    def test_original_vis_unchanged(self):
        m = Material(name="probe")
        m.vis.source = "ambientcg"
        m.vis.material_id = "Metal012"
        c = m.with_vis(Vis(source="polyhaven", material_id="metal_01"))
        assert m.vis.source == "ambientcg"
        assert c.vis.source == "polyhaven"

    def test_rejects_non_vis(self):
        m = Material(name="probe")
        with pytest.raises(TypeError, match="Vis instance"):
            m.with_vis({"source": "ambientcg", "material_id": "Metal012"})  # dict, not Vis

    def test_preserves_other_material_state(self):
        m = Material(name="probe", density=7.8, grade="304")
        c = m.with_vis(Vis(source="ambientcg", material_id="Metal012"))
        assert c.name == "probe"
        assert c.grade == "304"
        assert c.properties.mechanical.density == 7.8


class TestAdapterRoundTripViaWithVis:
    """The headline user story: derive a tweaked variant, hand to an
    adapter, get the new values out."""

    def test_to_threejs_reflects_new_vis(self):
        from pymat.vis.adapters import to_threejs

        m = Material(name="probe")
        m.vis.roughness = 0.3
        m.vis.metallic = 1.0

        new_vis = m.vis.override(roughness=0.7, metallic=0.0)
        c = m.with_vis(new_vis)

        d = to_threejs(c)
        assert d["roughness"] == 0.7
        assert d["metalness"] == 0.0

    def test_original_material_adapter_unchanged(self):
        from pymat.vis.adapters import to_threejs

        m = Material(name="probe")
        m.vis.roughness = 0.3
        m.vis.metallic = 1.0

        c = m.with_vis(m.vis.override(roughness=0.7, metallic=0.0))
        _ = to_threejs(c)  # noqa: F841 — exercising the adapter

        d_orig = to_threejs(m)
        assert d_orig["roughness"] == 0.3
        assert d_orig["metalness"] == 1.0


class TestRegistryParentChainStillResolves:
    """Detached copies keep their parent so property inheritance
    fallbacks still work — important for CAD users who derive a
    grade-level variant but expect ``c.density`` to still resolve."""

    def test_density_via_parent_chain(self):
        import pymat

        s304 = pymat.stainless.s304
        c = s304.copy()
        # The grade may not own density itself; parent chain provides it
        assert c.properties.mechanical.density == s304.properties.mechanical.density


class TestVisCacheZeroedOnCopy:
    """``copy()`` deep-copies ``_vis``. ``deepcopy`` does NOT call
    ``Vis.__post_init__`` (it goes through ``__reduce_ex__``), so the
    texture cache + ``_fetched`` flag would carry over without an
    explicit zeroing — wasteful and contradicts the docstring."""

    def test_copy_zeroes_texture_cache(self):
        m = Material(name="cached probe")
        m.vis.source = "ambientcg"
        m.vis.material_id = "Metal012"
        m.vis._textures = {"color": b"\x89PNG_fake_bytes"}
        m.vis._fetched = True

        c = m.copy()
        assert c.vis._textures == {}
        assert c.vis._fetched is False
        # Original cache untouched
        assert m.vis._textures == {"color": b"\x89PNG_fake_bytes"}
        assert m.vis._fetched is True

    def test_with_vis_target_starts_fresh(self):
        """``with_vis`` builds on top of ``copy``, so the texture cache
        on the resulting Material's vis is whatever the supplied vis
        has — but the copy's pre-existing cache is wiped, so there's
        no leftover bytes from the parent."""
        m = Material(name="probe")
        m.vis.source = "ambientcg"
        m.vis.material_id = "Metal012"
        m.vis._textures = {"color": b"\x89PNG_old"}
        m.vis._fetched = True

        new_vis = m.vis.override(material_id="Metal032")
        c = m.with_vis(new_vis)
        # New vis starts unfetched (override invalidated identity)
        assert c.vis._textures == {}
        assert c.vis._fetched is False


class TestWithVisDeepCopiesSuppliedVis:
    """Bug B2: ``with_vis(vis)`` must deep-copy ``vis`` so callers
    passing the registry's own ``m.vis`` don't get a Material whose
    ``_vis`` is re-aliased to the singleton's instance."""

    def test_supplied_vis_is_deep_copied(self):
        import pymat

        steel = pymat["Stainless Steel 304"]
        # Caller passes the registry's own vis directly
        c = steel.with_vis(steel.vis)
        assert c.vis is not steel.vis  # independent instance
        # Mutating the copy must not leak to the registry
        c.vis.roughness = 0.99
        assert steel.vis.roughness != 0.99

    def test_supplied_vis_finishes_dict_independent(self):
        m = Material(name="probe")
        m.vis.source = "ambientcg"
        m.vis.material_id = "Metal012"
        m.vis.finishes = {"a": {"source": "ambientcg", "id": "Metal012"}}

        c = m.with_vis(m.vis)
        c.vis.finishes["b"] = {"source": "x", "id": "y"}
        assert "b" not in m.vis.finishes


class TestParentMutationWarning:
    """``copy()`` preserves ``parent`` by reference for the inheritance
    fallback chain. This means mutating ``c.parent.<anything>`` still
    corrupts the registry — documented as a footgun. Pin the behavior
    so a future "deep-copy parent too" change can't slip through
    silently."""

    def test_parent_is_same_object_after_copy(self):
        import pymat

        s304 = pymat.stainless.s304
        c = s304.copy()
        # By design — the copy joins the existing inheritance chain
        assert c.parent is s304.parent
        assert c.parent is pymat.stainless


class TestCopyOnNonRegistryMaterial:
    """``copy()`` of a user-constructed Material is also valid; nothing
    in the implementation requires the source be a registry entry."""

    def test_custom_material_copy(self):
        m = Material(name="custom probe", density=4.2)
        m.vis.roughness = 0.5
        c = m.copy()
        assert c is not m
        assert c.name == "custom probe"
        assert c.parent is None  # custom Material has no parent
        assert c._key is None
        # Independent state
        c.properties.mechanical.density = 9.9
        c.vis.roughness = 0.1
        assert m.properties.mechanical.density == 4.2
        assert m.vis.roughness == 0.5


class TestCopyOnParentLevelEmptiesChildren:
    """``stainless.copy()`` empties ``_children`` — documented behavior.
    A user reaching for ``stainless.copy().s304`` should get a clean
    failure, not a stale registry reference."""

    def test_parent_copy_has_no_children(self):
        import pymat

        c = pymat.stainless.copy()
        assert c._children == {}
        with pytest.raises(AttributeError):
            _ = c.s304
