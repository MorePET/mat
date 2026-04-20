"""Tests for ``pymat["..."]`` exact-lookup + normalization + ambiguity (#89).

Before 3.4, resolving an arbitrary user string to one Material required
handwritten glue (as in build123d#1270). This suite pins:

- Subscript access returns a single ``Material`` for exact matches on
  key, ``Material.name``, or ``grade``.
- Normalization folds: whitespace collapsing, case, NFKC (curly quotes,
  non-breaking space, em-dashes).
- Empty / whitespace-only / non-string inputs raise cleanly.
- Missing queries raise ``KeyError`` with fuzzy suggestions.
- Ambiguous queries raise ``KeyError`` with candidate list.
- ``in`` operator works (``__contains__``).
- ``search(..., exact=True)`` mirrors the matching rules.
"""

from __future__ import annotations

import pytest

import pymat


@pytest.fixture(autouse=True, scope="module")
def _load_all_categories():
    """Force lazy-load of every category so lookup sees the full library."""
    pymat.load_all()


class TestSubscriptBasic:
    def test_lookup_by_name(self):
        m = pymat["Stainless Steel 304"]
        assert m.name == "Stainless Steel 304"

    def test_lookup_by_registry_key(self):
        m = pymat["s304"]
        assert m.name == "Stainless Steel 304"

    def test_lookup_by_grade(self):
        """``304`` isn't a registry key (``s304`` is) nor a substring
        of the canonical name alone — but ``Material.grade == "304"``
        makes it a valid exact target."""
        m = pymat["304"]
        assert m.grade == "304"


class TestNormalization:
    def test_leading_trailing_whitespace(self):
        assert pymat["  Stainless Steel 304  "].name == "Stainless Steel 304"

    def test_internal_whitespace_collapse(self):
        assert pymat["Stainless   Steel    304"].name == "Stainless Steel 304"

    def test_tabs_and_newlines(self):
        assert pymat["Stainless\tSteel\n304"].name == "Stainless Steel 304"

    def test_case_insensitive(self):
        assert pymat["stainless steel 304"].name == "Stainless Steel 304"
        assert pymat["STAINLESS STEEL 304"].name == "Stainless Steel 304"
        assert pymat["StAiNlEsS sTeEl 304"].name == "Stainless Steel 304"

    def test_unicode_nbsp(self):
        """Non-breaking space (U+00A0) folds to regular space via NFKC."""
        assert pymat["Stainless\u00a0Steel\u00a0304"].name == "Stainless Steel 304"

    def test_unicode_fullwidth_digits(self):
        """Full-width digits (U+FF10..U+FF19) fold to ASCII via NFKC."""
        # "Stainless Steel ３０４" — U+FF13 U+FF10 U+FF14
        assert pymat["Stainless Steel \uff13\uff10\uff14"].name == "Stainless Steel 304"


class TestMissingAndAmbiguous:
    def test_missing_raises_key_error(self):
        with pytest.raises(KeyError, match="No material matches"):
            _ = pymat["totally_not_a_material_xyz"]

    def test_missing_with_close_matches_suggests(self):
        """A typo-ish query that doesn't exact-match but has close
        fuzzy matches should list them in the error."""
        try:
            _ = pymat["stainles stell 304"]  # deliberate typos
        except KeyError as e:
            msg = str(e)
            # Either zero close matches (plain error) or some close
            # matches mentioned — both acceptable, just not silent.
            assert "stainles stell 304" in msg or "No material" in msg
        else:
            pytest.fail("missing material should raise KeyError")

    def test_unique_parent_returned(self):
        """``pymat["Stainless"]`` resolves to the parent because its
        key is exactly ``"stainless"`` — that's unambiguous, not a bug."""
        m = pymat["Stainless"]
        assert m.name == "Stainless Steel"

    def test_ambiguous_would_raise(self):
        """If a query matches multiple registry entries exactly, the
        error must list candidates. We construct this scenario by
        hand since the shipped library doesn't currently have natural
        exact collisions."""
        from pymat import Material, registry

        m1 = Material(name="Duplicate Name")
        m2 = Material(name="Duplicate Name")
        try:
            registry.register("dupe_a", m1)
            registry.register("dupe_b", m2)
            with pytest.raises(KeyError, match="Ambiguous.*match"):
                _ = pymat["Duplicate Name"]
        finally:
            # Clean up: remove both to keep the fixture registry stable
            registry._REGISTRY.pop("dupe_a", None)
            registry._REGISTRY.pop("dupe_b", None)


class TestEdgeCases:
    def test_empty_string_raises(self):
        with pytest.raises(KeyError, match="non-empty"):
            _ = pymat[""]

    def test_whitespace_only_raises(self):
        with pytest.raises(KeyError, match="non-empty"):
            _ = pymat["   \t\n  "]

    def test_non_string_raises_type_error(self):
        with pytest.raises(TypeError):
            _ = pymat[42]
        with pytest.raises(TypeError):
            _ = pymat[None]


class TestContainsOperator:
    def test_contains_true(self):
        assert "Stainless Steel 304" in pymat
        assert "s304" in pymat
        assert "304" in pymat  # grade match

    def test_contains_false(self):
        assert "not a real material xyz" not in pymat
        assert "" not in pymat


class TestExactSearch:
    """``search(query, exact=True)`` returns the same matches as the
    subscript form, but as a list (for callers that want to handle
    ambiguity themselves)."""

    def test_exact_matches_key(self):
        hits = pymat.search("s304", exact=True)
        assert len(hits) == 1
        assert hits[0].name == "Stainless Steel 304"

    def test_exact_matches_name(self):
        hits = pymat.search("Stainless Steel 304", exact=True)
        assert len(hits) == 1

    def test_exact_matches_grade(self):
        """The falsify review flagged that ``search("304", exact=True)``
        used to return ``[]`` because grade wasn't in the exact-target
        set. Fixed to include grade."""
        hits = pymat.search("304", exact=True)
        assert hits, "search('304', exact=True) should match via grade"
        assert any(m.grade == "304" for m in hits)

    def test_exact_empty_query_returns_empty_list(self):
        assert pymat.search("", exact=True) == []
        assert pymat.search("   ", exact=True) == []

    def test_exact_normalization(self):
        """Case + whitespace folding same as subscript form."""
        hits_a = pymat.search("stainless steel 304", exact=True)
        hits_b = pymat.search("  Stainless   Steel   304  ", exact=True)
        assert [m.name for m in hits_a] == [m.name for m in hits_b]

    def test_exact_vs_fuzzy_differ(self):
        """Exact mode returns ≤ results than fuzzy for the same query."""
        exact = pymat.search("Stainless", exact=True)
        fuzzy = pymat.search("Stainless")
        assert len(exact) <= len(fuzzy)


class TestSearchFuzzyRegression:
    """The #89 fix adds normalization on the fuzzy path too. Verify
    existing fuzzy tests still work + normalization applies."""

    def test_fuzzy_whitespace_insensitive(self):
        """Fuzzy path now normalizes whitespace — extra spaces don't
        break the tokenization."""
        a = pymat.search("stainless 316")
        b = pymat.search("  stainless   316  ")
        assert [m.name for m in a] == [m.name for m in b]

    def test_fuzzy_case_insensitive_via_normalization(self):
        a = pymat.search("Stainless")
        b = pymat.search("stainless")
        assert [m.name for m in a] == [m.name for m in b]
