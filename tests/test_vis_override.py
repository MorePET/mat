"""Tests for ``Vis.override(**deltas)`` — immutable derive helper.

The motivating bug: ``pymat["Stainless Steel 304"]`` returns the
*registry singleton*, so ``m.vis.roughness = 0.6`` in one caller is
visible to every other caller of the same key. ``override`` returns a
deep-copied variant so consumers can derive tweaked Vis instances
without corrupting the shared registry entry.

Pinned semantics:

- Returns a new instance; original unchanged in every field.
- ``finishes`` dict deep-copied (no shared-reference hazard).
- Identity deltas route through ``set_identity`` (atomic invalidation).
- ``finish=`` is special-cased (it's a property, not a field) and
  applied LAST against the deep-copied finishes map.
- Identity change without ``finish=`` clears stale ``_finish`` label.
- Unknown kwargs raise ``TypeError`` (typo protection).
- Cache state preserved when identity unchanged; cleared otherwise.
"""

from __future__ import annotations

import pytest

from pymat.vis._model import Vis


def _base() -> Vis:
    return Vis(
        source="ambientcg",
        material_id="Metal012",
        tier="1k",
        finishes={
            "brushed": {"source": "ambientcg", "id": "Metal012"},
            "polished": {"source": "ambientcg", "id": "Metal049A"},
        },
        roughness=0.3,
        metallic=1.0,
        base_color=(0.75, 0.75, 0.77, 1.0),
    )


class TestOverrideReturnsNewInstance:
    def test_returns_new_object(self):
        v = _base()
        v2 = v.override(roughness=0.6)
        assert v2 is not v

    def test_original_scalars_unchanged(self):
        v = _base()
        v.override(roughness=0.6, metallic=0.0)
        assert v.roughness == 0.3
        assert v.metallic == 1.0

    def test_original_identity_unchanged(self):
        v = _base()
        v.override(source="polyhaven", material_id="custom_01")
        assert v.source == "ambientcg"
        assert v.material_id == "Metal012"

    def test_no_deltas_returns_independent_copy(self):
        """``override()`` with no kwargs is still a deep-copy."""
        v = _base()
        v2 = v.override()
        assert v2 is not v
        assert v2 == v
        assert v2.finishes is not v.finishes


class TestFinishesDeepCopy:
    """The headline correctness fix — finishes must not share a dict."""

    def test_finishes_is_independent(self):
        v = _base()
        v2 = v.override(roughness=0.6)
        assert v.finishes is not v2.finishes

    def test_child_mutates_finishes_parent_unaffected(self):
        v = _base()
        v2 = v.override()
        v2.finishes["matte"] = {"source": "ambientcg", "id": "Metal099"}
        assert "matte" in v2.finishes
        assert "matte" not in v.finishes

    def test_child_mutates_finish_entry_parent_unaffected(self):
        """Even nested dict values are deep-copied."""
        v = _base()
        v2 = v.override()
        v2.finishes["brushed"]["source"] = "polyhaven"
        assert v.finishes["brushed"]["source"] == "ambientcg"


class TestScalarOverride:
    def test_single_scalar(self):
        v = _base()
        v2 = v.override(roughness=0.6)
        assert v2.roughness == 0.6

    def test_multiple_scalars(self):
        v = _base()
        v2 = v.override(roughness=0.6, metallic=0.5, ior=1.4)
        assert (v2.roughness, v2.metallic, v2.ior) == (0.6, 0.5, 1.4)

    def test_identity_preserved_on_scalar_override(self):
        v = _base()
        v2 = v.override(roughness=0.6)
        assert v2.source == "ambientcg"
        assert v2.material_id == "Metal012"
        assert v2.tier == "1k"

    def test_finish_label_preserved_on_scalar_override(self):
        """Pure scalar tweak should not clear the inherited finish."""
        v = _base()
        v.finish = "polished"
        v2 = v.override(roughness=0.6)
        assert v2._finish == "polished"


class TestIdentityOverride:
    def test_source_change(self):
        v = _base()
        v2 = v.override(source="polyhaven")
        assert v2.source == "polyhaven"
        assert v2.material_id == "Metal012"  # unchanged

    def test_full_identity_swap(self):
        v = _base()
        v2 = v.override(source="polyhaven", material_id="metal_01", tier="2k")
        assert (v2.source, v2.material_id, v2.tier) == ("polyhaven", "metal_01", "2k")

    def test_identity_change_clears_stale_finish(self):
        """If user moves identity without specifying a finish, the
        inherited ``_finish`` label is now meaningless — clear it."""
        v = _base()
        v.finish = "polished"
        assert v._finish == "polished"
        v2 = v.override(source="polyhaven", material_id="custom_01")
        assert v2._finish is None

    def test_identity_no_op_preserves_finish(self):
        """If identity 'change' is actually a no-op, don't clear finish."""
        v = _base()
        v.finish = "polished"
        v2 = v.override(source="ambientcg")  # same value
        assert v2._finish == "polished"

    def test_identity_change_invalidates_cache(self):
        """Cache must be empty/unfetched after identity change."""
        v = _base()
        v._textures = {"color": b"\x89PNG_fake"}
        v._fetched = True
        v2 = v.override(source="polyhaven")
        assert v2._textures == {}
        assert v2._fetched is False

    def test_no_identity_change_preserves_cache(self):
        """Pure scalar override → cache is still valid for the same
        identity, so deep-copy preserves it (deepcopy doesn't trip
        ``__post_init__``)."""
        v = _base()
        v._textures = {"color": b"\x89PNG_fake"}
        v._fetched = True
        v2 = v.override(roughness=0.6)
        assert v2._textures == {"color": b"\x89PNG_fake"}
        assert v2._fetched is True


class TestFinishDelta:
    def test_finish_applied(self):
        v = _base()
        v2 = v.override(finish="polished")
        assert v2._finish == "polished"
        assert v2.material_id == "Metal049A"
        assert v2.source == "ambientcg"

    def test_finish_against_deep_copied_map(self):
        """Mutating child finishes after override doesn't affect parent's
        finish lookup."""
        v = _base()
        v2 = v.override(finish="polished")
        v2.finishes["polished"]["id"] = "TamperedID"
        # Parent's polished entry still untouched
        assert v.finishes["polished"]["id"] == "Metal049A"

    def test_unknown_finish_raises(self):
        v = _base()
        with pytest.raises(ValueError, match="Unknown finish"):
            v.override(finish="mirror")

    def test_finish_combined_with_scalars(self):
        v = _base()
        v2 = v.override(finish="polished", roughness=0.1)
        assert v2._finish == "polished"
        assert v2.roughness == 0.1
        assert v2.material_id == "Metal049A"

    def test_finish_wins_over_explicit_identity(self):
        """If user passes both ``source=`` and ``finish=``, finish runs
        last and wins. Documented behavior — same as merge_from_toml."""
        v = _base()
        v2 = v.override(source="polyhaven", finish="polished")
        # finish=polished is from finishes map (ambientcg/Metal049A)
        assert v2.source == "ambientcg"
        assert v2.material_id == "Metal049A"
        assert v2._finish == "polished"


class TestUnknownKwargs:
    def test_typo_raises_typeerror(self):
        v = _base()
        with pytest.raises(TypeError, match="roughnes"):
            v.override(roughnes=0.5)

    def test_internal_field_rejected(self):
        """Don't let consumers reach into private state."""
        v = _base()
        with pytest.raises(TypeError):
            v.override(_textures={})

    def test_error_lists_valid_keys(self):
        v = _base()
        with pytest.raises(TypeError, match="Valid keys"):
            v.override(unknown_field=42)


class TestRegistryMutationHazardFixed:
    """The motivating user story: derive a polished steel without
    corrupting the registry instance other callers see."""

    def test_polished_variant_does_not_touch_registry(self):
        import pymat

        steel = pymat["Stainless Steel 304"]
        original_finish = steel.vis._finish
        original_roughness = steel.vis.roughness
        original_mid = steel.vis.material_id

        polished = steel.vis.override(finish="polished", roughness=0.1)

        # Variant has the changes
        assert polished._finish == "polished"
        assert polished.roughness == 0.1
        assert polished.material_id != original_mid

        # Registry instance unchanged
        assert steel.vis._finish == original_finish
        assert steel.vis.roughness == original_roughness
        assert steel.vis.material_id == original_mid

    def test_two_variants_dont_cross_contaminate(self):
        import pymat

        steel = pymat["Stainless Steel 304"]
        a = steel.vis.override(roughness=0.2)
        b = steel.vis.override(roughness=0.8)
        a.finishes["custom_a"] = {"source": "x", "id": "a"}
        b.finishes["custom_b"] = {"source": "x", "id": "b"}
        assert "custom_a" in a.finishes and "custom_a" not in b.finishes
        assert "custom_b" in b.finishes and "custom_b" not in a.finishes
        assert "custom_a" not in steel.vis.finishes
        assert "custom_b" not in steel.vis.finishes


# ── Bugs caught by independent review of 3.6.0 ─────────────────


class TestTierOnlyChangePreservesFinish:
    """Issue #103. ``tier`` is an identity field but doesn't affect
    which finish-map entry is selected — clearing ``_finish`` on a
    tier-only change is over-eager. The stale-finish guard should
    only fire when ``source`` or ``material_id`` actually changes.
    """

    def test_tier_change_keeps_finish_label(self):
        v = _base()
        v.finish = "polished"
        v2 = v.override(tier="2k")
        assert v2._finish == "polished", (
            "tier change must not clear _finish — finishes pin (source, material_id), not tier"
        )
        # Same (source, material_id) as the polished entry → finish remains valid
        assert v2.source == "ambientcg"
        assert v2.material_id == "Metal049A"
        assert v2.tier == "2k"

    def test_tier_change_still_invalidates_cache(self):
        """Tier change must clear the texture cache (different bytes
        for 1k vs 2k) but leave the finish *label* alone."""
        v = _base()
        v.finish = "polished"
        v._textures = {"color": b"\x89PNG_1k_bytes"}
        v._fetched = True
        v2 = v.override(tier="2k")
        assert v2._textures == {}
        assert v2._fetched is False
        assert v2._finish == "polished"


class TestCallerSuppliedFinishesDeepCopied:
    """Issue #104. Caller-supplied ``finishes=`` dict must be
    deep-copied; storing by reference breaks the docstring promise
    and diverges from ``merge_from_toml``.
    """

    def test_caller_dict_mutation_does_not_leak(self):
        v = _base()
        caller_dict = {"matte": {"source": "x", "id": "y"}}
        v2 = v.override(finishes=caller_dict)
        # Caller mutates their own dict after the call
        caller_dict["matte"]["id"] = "TAMPERED"
        caller_dict["another"] = {"source": "z", "id": "w"}
        # Override result must be insulated
        assert v2.finishes["matte"]["id"] == "y"
        assert "another" not in v2.finishes

    def test_caller_dict_top_level_isolated(self):
        v = _base()
        caller_dict = {"matte": {"source": "x", "id": "y"}}
        v2 = v.override(finishes=caller_dict)
        assert v2.finishes is not caller_dict

    def test_finish_resolves_against_new_map(self):
        """``finish=`` runs after ``finishes=`` is applied, so the
        finish setter looks up in the *new* (deep-copied) map."""
        v = _base()
        new_map = {"matte": {"source": "polyhaven", "id": "metal_matte"}}
        v2 = v.override(finishes=new_map, finish="matte")
        assert v2._finish == "matte"
        assert v2.source == "polyhaven"
        assert v2.material_id == "metal_matte"

    def test_finish_against_replaced_map_unknown_raises(self):
        """If the new finishes map doesn't contain the requested
        finish, the finish setter raises (not the inherited map)."""
        v = _base()
        new_map = {"matte": {"source": "x", "id": "y"}}
        # 'polished' was in the original map but not in new_map
        with pytest.raises(ValueError, match="Unknown finish 'polished'"):
            v.override(finishes=new_map, finish="polished")


# ── Coverage gaps from review (#105) ──────────────────────────


class TestAdapterRoundTrip:
    """Override must flow into the cross-tool adapters. Otherwise
    a downstream consumer's tweaked variant is silently ignored."""

    def test_to_threejs_picks_up_overridden_roughness(self):
        from pymat import Material
        from pymat.vis.adapters import to_threejs

        m = Material(name="adapter probe")
        m.vis.roughness = 0.3
        m.vis.metallic = 1.0
        m.vis.base_color = (0.5, 0.5, 0.5, 1.0)

        # Mutate only the variant via override
        m2 = Material(name="adapter probe variant")
        new_vis = m.vis.override(roughness=0.7, metallic=0.0)
        m2._vis = new_vis  # bypass property to keep test focused on adapter

        d = to_threejs(m2)
        assert d["roughness"] == 0.7
        assert d["metalness"] == 0.0
        # Original Material's adapter output unchanged
        d_orig = to_threejs(m)
        assert d_orig["roughness"] == 0.3
        assert d_orig["metalness"] == 1.0

    def test_to_gltf_picks_up_overridden_color(self):
        from pymat import Material
        from pymat.vis.adapters import to_gltf

        m = Material(name="gltf probe")
        m.vis.base_color = (1.0, 0.0, 0.0, 1.0)

        v2 = m.vis.override(base_color=(0.0, 1.0, 0.0, 1.0))
        m2 = Material(name="gltf probe variant")
        m2._vis = v2

        d = to_gltf(m2)
        pbr = d.get("pbrMetallicRoughness", {})
        assert pbr.get("baseColorFactor") == [0.0, 1.0, 0.0, 1.0]


class TestScalarReset:
    """Setting a scalar back to ``None`` via override is allowed —
    consumer's way to undo an inherited value."""

    def test_roughness_reset_to_none(self):
        v = _base()
        assert v.roughness == 0.3
        v2 = v.override(roughness=None)
        assert v2.roughness is None
        # Other scalars untouched
        assert v2.metallic == 1.0

    def test_base_color_reset_to_none(self):
        v = _base()
        assert v.base_color is not None
        v2 = v.override(base_color=None)
        assert v2.base_color is None


class TestErrorMessageQuality:
    """Tighter assertions than the original 3.6.0 tests.

    Loose original: ``test_typo_raises_typeerror`` only matched the
    typo substring; didn't pin the fix-it hint. These pin both.
    """

    def test_typo_message_includes_typo_and_valid_keys(self):
        v = _base()
        with pytest.raises(TypeError) as exc:
            v.override(roughnes=0.5)
        msg = str(exc.value)
        assert "roughnes" in msg
        assert "Valid keys" in msg
        assert "roughness" in msg  # the correct name appears in the hint

    def test_internal_field_message_names_field(self):
        v = _base()
        with pytest.raises(TypeError, match="_textures"):
            v.override(_textures={})


class TestRegistryDataCoupling:
    """Replace the ``pymat["Stainless Steel 304"]``-coupled tests
    above with fixture-built Vises so the contract doesn't depend on
    TOML data shape staying constant. The original tests still run
    and still pass; these are an additional safety net."""

    def test_finish_change_independent_of_registry(self):
        v = _base()  # local fixture with brushed/polished
        v.finish = "brushed"
        v2 = v.override(finish="polished")
        assert v.material_id == "Metal012"  # original untouched
        assert v2.material_id == "Metal049A"

    def test_scalar_override_independent_of_registry(self):
        v = _base()
        v2 = v.override(roughness=0.99)
        assert v.roughness == 0.3  # local fixture's value
        assert v2.roughness == 0.99


class TestIdempotence:
    """``v.override()`` chained twice produces an equivalent result —
    confirms no hidden state accumulates."""

    def test_double_no_op_override_equals_single(self):
        v = _base()
        once = v.override()
        twice = once.override()
        assert once == twice
        assert once is not twice  # but distinct objects

    def test_double_scalar_override_overlay(self):
        v = _base()
        a = v.override(roughness=0.5)
        b = a.override(roughness=0.9)
        assert b.roughness == 0.9
        # Original and intermediate untouched
        assert v.roughness == 0.3
        assert a.roughness == 0.5
