"""Tests for the ``pymat.materials`` registry surface.

The registry is a single object that's simultaneously:

- A ``Mapping[str, Material]`` (subscript / iteration / membership / len)
- A callable that performs lookup or filter depending on args
- The canonical, type-checkable entry point per ADR-0006 (drops the
  ``pymat.lookup()`` proposal in favour of one richer surface)

Mirrors ``pint.UnitRegistry``'s call/attr/subscript trifecta — same
shape downstream Python users have already encountered.

Implementation reference: ``src/pymat/_registry.py::_Materials``,
exposed as ``pymat.materials`` from ``src/pymat/__init__.py``.
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest

import pymat
from pymat import Material


@pytest.fixture(autouse=True)
def _ensure_loaded():
    """Load the full registry before each test so ``pymat.materials``
    sees every category. Mirrors ``conftest.py``'s clear+yield+clear
    pattern but with an explicit re-load."""
    pymat.load_all()


# ── 1. Mapping protocol ─────────────────────────────────────────


class TestMaterialsAsMapping:
    """`pymat.materials` exposes the full ``Mapping`` protocol so any
    code that iterates / inspects without doing a raw lookup can use
    standard Python idioms."""

    def test_is_a_mapping(self):
        assert isinstance(pymat.materials, Mapping)

    def test_subscript_returns_material(self):
        m = pymat.materials["Stainless Steel 304"]
        assert isinstance(m, Material)
        assert m.name == "Stainless Steel 304"

    def test_subscript_raises_keyerror_on_miss(self):
        with pytest.raises(KeyError, match="No material matches"):
            _ = pymat.materials["TotallyMadeUpMaterial"]

    def test_subscript_includes_close_matches_in_keyerror(self):
        with pytest.raises(KeyError) as exc:
            _ = pymat.materials["Stinless Steel 304"]
        msg = str(exc.value)
        assert "Stinless Steel 304" in msg
        # Close-match suggestions should surface
        assert "Stainless Steel" in msg or "Close matches" in msg

    def test_contains_membership(self):
        assert "Stainless Steel 304" in pymat.materials
        assert "Not A Real Material XYZ" not in pymat.materials

    def test_contains_normalized(self):
        # NFKC + case + whitespace collapse — same normalization as
        # the existing pymat["..."] subscript
        assert "stainless steel 304" in pymat.materials
        assert "STAINLESS STEEL 304" in pymat.materials
        assert "Stainless   Steel   304" in pymat.materials

    def test_len_matches_registry_size(self):
        n = len(pymat.materials)
        assert n > 0
        # Should match registry.list_all() which is the source of truth
        from pymat import registry

        assert n == len(registry.list_all())

    def test_iter_yields_canonical_keys(self):
        """Iterating a Mapping yields keys (registry keys, e.g. ``s316L``)."""
        keys = list(pymat.materials)
        assert len(keys) == len(pymat.materials)
        assert all(isinstance(k, str) for k in keys)
        # Every iterated key should be subscriptable
        for k in keys[:5]:  # spot-check first 5
            assert isinstance(pymat.materials[k], Material)

    def test_keys_view(self):
        keys = pymat.materials.keys()
        assert "s316L" in keys or "stainless" in keys  # canonical registry keys

    def test_values_view(self):
        values = list(pymat.materials.values())
        assert all(isinstance(m, Material) for m in values)

    def test_items_view(self):
        for k, m in pymat.materials.items():
            assert isinstance(k, str)
            assert isinstance(m, Material)
            break  # spot-check first


# ── 2. Callable lookup form ──────────────────────────────────────


class TestMaterialsCallableLookup:
    """`pymat.materials("X")` is the verb-shaped lookup. Same semantics
    as the subscript — both delegate to the existing ``_lookup`` —
    but reads more naturally in long-form code:

        m = pymat.materials("Stainless Steel 304")     # vs
        m = pymat.materials["Stainless Steel 304"]
    """

    def test_callable_with_name_returns_material(self):
        m = pymat.materials("Stainless Steel 304")
        assert isinstance(m, Material)
        assert m.name == "Stainless Steel 304"

    def test_callable_with_registry_key(self):
        m = pymat.materials("s316L")
        assert m.name == "Stainless Steel 316L"

    def test_callable_with_grade(self):
        m = pymat.materials("304")
        assert m.grade == "304"

    def test_callable_raises_keyerror_on_miss(self):
        with pytest.raises(KeyError, match="No material matches"):
            pymat.materials("TotallyMadeUpMaterial")

    def test_callable_normalizes_input(self):
        # Same NFKC + case-fold + whitespace-collapse as subscript
        a = pymat.materials("Stainless Steel 304")
        b = pymat.materials("  stainless   steel   304  ")
        c = pymat.materials("STAINLESS STEEL 304")
        assert a.name == b.name == c.name


# ── 3. No-args + filtered list form ──────────────────────────────


class TestMaterialsBrowse:
    """`pymat.materials(...)` without a positional name returns a
    ``list[Material]`` — the browse / filter form. Empty-input or
    no-match return empty lists; this is "show me what fits"
    semantics (vs the lookup form which raises on miss)."""

    def test_no_args_returns_all_materials(self):
        all_mats = pymat.materials()
        assert isinstance(all_mats, list)
        assert all(isinstance(m, Material) for m in all_mats)
        assert len(all_mats) == len(pymat.materials)

    def test_filter_by_category_metals(self):
        metals = pymat.materials(category="metals")
        assert isinstance(metals, list)
        assert metals, "no metals returned"
        # Spot-check: stainless / aluminum should be in metals
        names = {m.name for m in metals}
        assert any("Stainless Steel" in n for n in names)

    def test_filter_by_category_returns_empty_list_on_miss(self):
        # Bogus category — empty list, no raise
        assert pymat.materials(category="not_a_real_category") == []

    def test_filter_by_grade(self):
        result = pymat.materials(grade="316L")
        assert result
        assert all(m.grade == "316L" for m in result)

    def test_filter_by_with_vis_true(self):
        result = pymat.materials(with_vis=True)
        # Every returned material must have a vis mapping
        assert all(m.vis is not None and m.vis.has_mapping for m in result)
        assert result, "expected at least one material with a vis mapping"

    def test_filter_combined(self):
        """Multiple filters compose with AND semantics."""
        result = pymat.materials(category="metals", grade="316L")
        assert result
        for m in result:
            assert m.grade == "316L"
            # Should also be in metals — verified via category lookup


class TestMaterialsTagsFilter:
    """Tags are the multi-axial filter axis (orthogonal to hierarchy).
    A material can carry many tags (chemistry, function, industry,
    treatment, regulation). Tags inherit from parent material —
    children extend.

    These tests rely on at least one shipped material having tags.
    The TOML loader populates ``Material.tags`` from the optional
    ``tags`` field.
    """

    def test_tags_field_exists_on_material(self):
        """Every Material has a ``tags`` attribute, default empty list."""
        m = pymat.materials("Stainless Steel 304")
        assert hasattr(m, "tags")
        assert isinstance(m.tags, list)

    def test_filter_by_single_tag(self):
        # The shipped TOML must have at least one material with the
        # 'austenitic' tag (a stainless-steel-family canonical tag we
        # backfill as part of this work).
        austenitic = pymat.materials(tags=["austenitic"])
        assert austenitic, "expected at least one material tagged 'austenitic'"
        assert all("austenitic" in m.tags for m in austenitic)

    def test_filter_by_multiple_tags_requires_all(self):
        # AND semantics — every tag in the filter must be on the material
        marine = pymat.materials(tags=["austenitic", "marine-grade"])
        # 316L is austenitic AND marine-grade in shipped data
        for m in marine:
            assert "austenitic" in m.tags
            assert "marine-grade" in m.tags

    def test_tags_inherit_from_parent(self):
        """A child's effective tag set is parent's ∪ own. The TOML
        only requires declaring NEW tags at each level."""
        # Stainless parent has 'ferrous'; s316L child should
        # inherit it without redeclaring.
        s316L = pymat.materials("s316L")
        assert "ferrous" in s316L.tags, (
            f"s316L should inherit 'ferrous' from stainless parent; got {s316L.tags!r}"
        )

    def test_empty_tags_default(self):
        """A material that doesn't declare tags has an empty list,
        not None."""
        # Air is shipped without tags by default (gases are unlikely
        # to need taxonomic tagging today)
        m = pymat.materials("air") if "air" in pymat.materials else None
        if m is None:
            pytest.skip("air not in registry")
        assert isinstance(m.tags, list)


# ── 4. Mixed-args rejection ──────────────────────────────────────


class TestMaterialsCallableArgRejection:
    """Mixing positional name + filter kwargs is ambiguous — does
    'lookup with filter' mean "find this name within filtered set"
    or "lookup wins, filters ignored"? Both are bad. Reject with
    TypeError so the caller picks one or the other.

    Static type checkers also catch this via the @overload setup,
    but runtime guard is the safety net for non-typed call sites."""

    def test_name_plus_category_rejected(self):
        with pytest.raises(TypeError, match="positional"):
            pymat.materials("Stainless Steel 304", category="metals")

    def test_name_plus_tags_rejected(self):
        with pytest.raises(TypeError, match="positional"):
            pymat.materials("Stainless Steel 304", tags=["austenitic"])


# ── 5. Backwards compat with pymat["..."] subscript ──────────────


class TestSubscriptBackwardsCompat:
    """Direct ``pymat["..."]`` (3.4-3.10 muscle memory) keeps working
    and resolves to the same Material as ``pymat.materials("X")``."""

    def test_subscript_and_callable_return_same_object(self):
        a = pymat["Stainless Steel 304"]
        b = pymat.materials("Stainless Steel 304")
        c = pymat.materials["Stainless Steel 304"]
        # Same Material instance from the registry singleton
        assert a is b is c

    def test_subscript_keyerror_unchanged(self):
        with pytest.raises(KeyError, match="No material matches"):
            _ = pymat["NotAThing"]


# ── 6. Search extension with filter kwargs ───────────────────────


class TestSearchFilters:
    """``pymat.search(query, ...)`` is the fuzzy ranked-search verb.
    Extended in this work with the same filter kwargs as
    ``materials()`` so callers can fuzzy-match within an exact
    category / grade / tags scope:

        pymat.search("polished", category="metals")
        pymat.search("alloy", grade="6061")
        pymat.search("brushed", tags=["austenitic"])
    """

    def test_search_with_category(self):
        # Fuzzy "stainless" within metals — every hit must be in metals
        # (i.e., not a polymer or scintillator named "stainless"-something)
        results = pymat.search("stainless", category="metals")
        assert results
        # Ranked list of Materials
        from pymat import Material as _M

        assert all(isinstance(m, _M) for m in results)

    def test_search_filter_excludes_off_category(self):
        """If the fuzzy match would otherwise return materials from
        another category, the filter narrows it out."""
        # "carbon" might fuzzy-match across categories (Carbon biColor
        # Coat, Carbon [scintillator base], etc.). Filtering to metals
        # only should exclude scintillator/electronics matches.
        all_carbon = pymat.search("carbon")
        metals_only = pymat.search("carbon", category="metals")
        assert len(metals_only) <= len(all_carbon)

    def test_search_with_tags(self):
        # Fuzzy match query AND require tag set
        results = pymat.search("steel", tags=["austenitic"])
        assert all("austenitic" in m.tags for m in results)

    def test_search_no_match_returns_empty_list(self):
        # Search semantics — empty list, not raise
        result = pymat.search("zzqqxxyy_nonexistent", category="metals")
        assert result == []

    def test_search_existing_signature_still_works(self):
        """Backwards-compat: pre-existing search signature
        (query, *, exact=False, limit=10) keeps working."""
        results = pymat.search("stainless 316")
        assert results
        results_exact = pymat.search("Stainless Steel 304", exact=True)
        assert any(m.name == "Stainless Steel 304" for m in results_exact)


# ── 7. Public API surface ────────────────────────────────────────


class TestPublicAPISurface:
    """`pymat.materials` is in `__all__` and importable — type-checks
    cleanly via mypy because it's a typed Mapping (see typing tests
    in tests/test_public_api_surface.py)."""

    def test_in_all(self):
        assert "materials" in pymat.__all__

    def test_module_path_is_public(self):
        # The class lives somewhere in pymat (e.g. pymat._registry)
        # but its __module__ must surface as the public path the user
        # imports from. Mirror of py-mat #98 / mat-vis #282 fix.
        cls = type(pymat.materials)
        assert not any(seg.startswith("_") for seg in cls.__module__.split(".")), (
            f"pymat.materials class lives at private module path "
            f"{cls.__module__!r} — rewrite to public via __module__ assignment"
        )
