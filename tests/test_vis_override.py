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
