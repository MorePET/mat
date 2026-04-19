"""Tests for pymat.search — fuzzy find over the domain library.

Covers the full contract documented in the search module docstring:

- tokenization (whitespace, case)
- target weighting (key > name/grade > hierarchy path)
- conjunctive matching (every token must hit somewhere)
- tie-breaks (shorter key wins)
- limit truncation
- load_all() side effect on first call
- empty / whitespace query
- missing optional attributes (grade=None, parent=None)
"""

from __future__ import annotations

import pymat
from pymat import Material, search
from pymat.search import _score, _targets


class TestTopLevelSurface:
    """``pymat.search`` is a public top-level verb, returning Materials."""

    def test_callable_from_package_root(self):
        assert callable(pymat.search)

    def test_in_package_all(self):
        assert "search" in pymat.__all__

    def test_returns_list_of_materials(self):
        hits = pymat.search("stainless")
        assert isinstance(hits, list)
        for m in hits:
            assert isinstance(m, Material)


class TestEmptyQuery:
    """An empty or whitespace-only query returns [], never the whole registry."""

    def test_empty_string(self):
        assert search("") == []

    def test_whitespace_only(self):
        assert search("   \t\n  ") == []


class TestExactKeyMatch:
    """A query that's an exact registry key must return that Material
    first — the high-weight key target outranks name / path matches."""

    def test_exact_key_ranks_first(self):
        hits = search("s316L")
        assert hits, "exact-key query returned no hits"
        # The s316L registry entry's Material.name is "Stainless Steel 316L"
        assert hits[0].name == "Stainless Steel 316L"

    def test_lowercase_query_matches_camelcase_key(self):
        """Search is case-insensitive — "s316l" matches registry key "s316L"."""
        hits = search("s316l")
        assert hits and hits[0].name == "Stainless Steel 316L"


class TestNameMatch:
    """Substring of ``Material.name`` must match even when the registry
    key is different — users search for human names, not registry keys."""

    def test_name_substring_match(self):
        # 'steel' appears in name "Stainless Steel" etc., not in keys
        hits = search("steel")
        assert any("Steel" in m.name for m in hits)

    def test_human_word_matches_name(self):
        hits = search("aluminum")
        assert hits
        assert all("Aluminum" in m.name for m in hits)


class TestGradeMatch:
    """``Material.grade`` is a separate target — a bare grade number
    should find the Material even if it's not in the key or full name."""

    def test_grade_number_finds_grade_materials(self):
        # 'T6' is both a registry key alias AND a grade value;
        # hitting either target gets s316L-style materials.
        hits = search("6061")
        assert hits, "grade-number query returned no hits"
        assert any("6061" in m.name for m in hits)


class TestMultiTokenConjunctive:
    """All tokens must match somewhere — a miss on any token rejects."""

    def test_both_tokens_must_match(self):
        """'stainless 316' matches only grades with both — not bare
        Stainless Steel parent, not bare 'Metal063'."""
        hits = search("stainless 316")
        assert hits
        # Every hit's name must contain BOTH 'stainless' and '316' case-insensitively
        for m in hits:
            lowered = m.name.lower()
            assert "stainless" in lowered
            assert "316" in lowered

    def test_token_miss_rejects_match(self):
        """A token that matches nothing rejects the Material entirely —
        even if other tokens match strongly."""
        hits = search("stainless unobtainium_xyz")
        assert hits == []

    def test_tokens_across_name_and_hierarchy(self):
        """Tokens can match different targets on the same Material —
        one in the name, another in the parent chain."""
        hits = search("lyso saint")
        assert hits
        # saint_gobain parent + lyso in name → must hit Saint-Gobain LYSO
        assert any("Saint-Gobain" in m.name and "LYSO" in m.name for m in hits)


class TestRanking:
    """Key matches outrank name matches; ties broken by shorter key."""

    def test_key_beats_name_when_both_match(self):
        """If a query matches both a registry key exactly AND a name
        partially elsewhere, the exact-key hit ranks higher."""
        # 'T6' is a registry key (= Aluminum 6061-T6 alias), and 'T6'
        # also appears in the name of every T6-ed aluminum. The T6 key
        # entry should come first.
        hits = search("T6")
        assert hits
        # First hit's key-match is higher weight than name-only matches
        # lower in the list.
        assert hits[0].name == "Aluminum 6061-T6"

    def test_shorter_key_tiebreaks_first(self):
        """With equal scores, shorter registry key wins — so parents
        come before their longer-keyed descendants when both match."""
        # Both 'stainless' (parent) and e.g. 's316L' match 'stainless'
        # via name — but parent has a key-level hit AND shorter key.
        hits = search("stainless")
        assert hits[0].name == "Stainless Steel"  # the parent

    def test_limit_respects_ranking(self):
        """``limit=`` truncates AFTER ranking, not before."""
        all_hits = search("steel", limit=50)
        top3 = search("steel", limit=3)
        assert len(top3) == 3
        # top3 must be a strict prefix of all_hits (same ranking order)
        assert [m.name for m in top3] == [m.name for m in all_hits[:3]]


class TestLimitParameter:
    def test_default_limit_is_ten(self):
        # Registry has >10 steel-related materials; default should cap at 10.
        hits = search("steel")
        assert len(hits) <= 10

    def test_custom_limit(self):
        hits = search("steel", limit=2)
        assert len(hits) <= 2

    def test_limit_zero_returns_empty(self):
        assert search("steel", limit=0) == []


class TestLoadingBehavior:
    """``search`` triggers ``load_all`` so results are exhaustive even
    when categories haven't been touched yet."""

    def test_search_loads_all_categories(self):
        # Any query should find materials across every category.
        # 'lyso' lives in scintillators, 'fr4' in electronics, 'ptfe'
        # in plastics — a query for each must return hits regardless
        # of prior lazy-load state.
        for q, expected in [
            ("lyso", "LYSO"),
            ("fr4", "FR4"),
            ("ptfe", "PTFE"),
        ]:
            hits = search(q)
            assert hits, f"no hits for {q!r}"
            assert any(expected in m.name for m in hits), f"no {expected} in hits for {q!r}"


class TestInternalScoring:
    """Unit tests for the scoring helpers — pinned so refactors can't
    silently change weights."""

    def test_targets_include_key_and_name(self):
        from pymat.search import _WEIGHT_KEY, _WEIGHT_NAME

        m = Material(name="Test Material", grade="42")
        pairs = _targets("test_key", m)
        # Tuple flattening — check by target text + weight
        assert ("test_key", _WEIGHT_KEY) in pairs
        assert ("test material", _WEIGHT_NAME) in pairs

    def test_targets_include_grade_when_present(self):
        from pymat.search import _WEIGHT_GRADE

        m = Material(name="Test", grade="42")
        pairs = _targets("k", m)
        assert ("42", _WEIGHT_GRADE) in pairs

    def test_targets_omit_grade_when_none(self):
        """No grade set → ``_targets`` must not add a grade pair.
        Compared by content (not weight, since name + grade share a
        weight today)."""
        m = Material(name="Test")
        assert m.grade is None
        pairs = _targets("k", m)
        # Expected pairs: key + name only. No grade-valued entry.
        # The grade value, if present, would be the string form of
        # whatever m.grade holds — here None. So simply assert the
        # set is exactly key + name.
        assert pairs == [("k", 10), ("test", 5)]

    def test_targets_walk_parent_chain(self):
        """Hierarchy parent names must appear as path-weighted targets."""
        from pymat.search import _WEIGHT_PATH

        parent = Material(name="Parent Material")
        child = Material(name="Child Material")
        child.parent = parent  # simulate hierarchy attachment

        pairs = _targets("child_key", child)
        path_pairs = [t for t, w in pairs if w == _WEIGHT_PATH]
        assert "parent material" in path_pairs

    def test_score_all_tokens_must_match(self):
        targets = [("stainless steel 316l", 5), ("s316l", 10)]
        # Both tokens present → positive
        assert _score(["stainless", "316"], targets) > 0
        # One token missing → 0 (rejected)
        assert _score(["stainless", "xyz"], targets) == 0

    def test_score_picks_highest_weight_per_token(self):
        from pymat.search import _WEIGHT_KEY, _WEIGHT_NAME

        # "316" appears in both a key target (weight 10) and a name
        # target (weight 5) — the higher one counts.
        targets = [
            ("s316l", _WEIGHT_KEY),  # has "316"
            ("stainless steel 316l", _WEIGHT_NAME),  # has "316"
        ]
        score = _score(["316"], targets)
        assert score == _WEIGHT_KEY


class TestDeterminism:
    """Two identical queries must return the same list in the same
    order — no hash-randomization surprises leaking through."""

    def test_same_query_same_order(self):
        a = search("steel", limit=5)
        b = search("steel", limit=5)
        assert [m.name for m in a] == [m.name for m in b]


class TestRegressionGuards:
    """Specific realistic queries that users are likely to type.
    These pin behavior the README / docstring examples advertise."""

    def test_stainless_parent_first(self):
        hits = search("stainless")
        assert hits[0].name == "Stainless Steel"

    def test_stainless_316_returns_316L_grade(self):
        hits = search("stainless 316")
        assert hits[0].grade == "316L"

    def test_lyso_ce_saint_hits_prelude(self):
        """Deep-hierarchy query: a scintillator vendor's product."""
        hits = search("lyso ce saint")
        names = [m.name for m in hits]
        assert any("PreLude" in n for n in names) or any(
            "Saint-Gobain" in n and "LYSO" in n for n in names
        )
