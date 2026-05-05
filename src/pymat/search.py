"""
Fuzzy search over the py-mat domain library.

``pymat.search("stainless 316")`` returns a ranked list of ``Material``
instances whose registry key, name, grade, or hierarchy path matches
the query tokens. Complements ``pymat.vis.search(...)`` (visual
catalog): two axes, same verb, no namespace collision.

Algorithm: tokenize query on whitespace; every token must clear a
similarity threshold against at least one weighted target on a
candidate Material for it to be included. Score is the sum of
per-token best-target weights, scaled by similarity ratio.

Similarity is ``rapidfuzz.fuzz.partial_ratio`` — finds the best-aligned
substring of the longer target whose length equals the token, then
scores edit distance there. Catches one- and two-character typos
(``"stinless"`` vs ``"stainless"``, ``"6016"`` vs ``"6061"``) without
matching arbitrary abbreviations (``"stl"`` won't auto-match
``"steel"`` — that requires an explicit alias). Closes #179.
"""

from __future__ import annotations

import unicodedata
from typing import TYPE_CHECKING

from rapidfuzz import fuzz

if TYPE_CHECKING:
    from .core import Material


def _normalize(s: str) -> str:
    """Normalize a lookup/search input: NFKC + lowercase + collapse whitespace.

    Picks up pasted curly quotes, em-dashes, non-breaking spaces, and other
    lookalikes that users paste from browser UIs.
    """
    return " ".join(unicodedata.normalize("NFKC", s).lower().split())


# Target weights — higher is a stronger match. Order matters: when a
# query token matches multiple targets on the same Material, the
# highest-weight hit counts.
_WEIGHT_KEY = 10  # registry key — "s316L"
_WEIGHT_NAME = 5  # Material.name — "Stainless Steel 316L"
_WEIGHT_GRADE = 5  # Material.grade — "316L"
_WEIGHT_PATH = 3  # hierarchy parent names

# Per-token similarity threshold (0-100 scale, rapidfuzz convention).
# 75 catches one-edit and most two-edit typos in 6-10 char strings
# (Levenshtein-bounded partial alignments) while rejecting arbitrary
# abbreviations like "stl" → "steel" (~67) that would auto-match too
# many materials. Calibrated against the existing search corpus —
# see tests/test_search.py for the pinned cases on both sides of
# the threshold.
_SIMILARITY_THRESHOLD = 75


def _targets(key: str, material: Material) -> list[tuple[str, int]]:
    """Return (lowered-target-string, weight) pairs for a Material.

    Hierarchy path walks ``parent`` up; skips the material's own name
    (already covered by the name target) and any None-named parents.
    """
    pairs: list[tuple[str, int]] = [(key.lower(), _WEIGHT_KEY)]

    if material.name:
        pairs.append((material.name.lower(), _WEIGHT_NAME))

    grade = getattr(material, "grade", None)
    if grade:
        pairs.append((str(grade).lower(), _WEIGHT_GRADE))

    # Walk the parent chain; skip the material itself (starts from parent).
    parent = getattr(material, "parent", None)
    while parent is not None:
        if parent.name:
            pairs.append((parent.name.lower(), _WEIGHT_PATH))
        parent = getattr(parent, "parent", None)

    return pairs


def _score(tokens: list[str], targets: list[tuple[str, int]]) -> float:
    """Score a Material against the query tokens.

    Every token must clear ``_SIMILARITY_THRESHOLD`` against at least
    one target. Returns 0 (rejected) if any token misses. Otherwise
    returns the sum of per-token best ``weight × (similarity / 100)``
    — so a perfect key match (10 × 1.0) outranks a fuzzy key match
    (10 × 0.8), which still outranks a perfect path match (3 × 1.0).

    Token matching uses ``rapidfuzz.fuzz.partial_ratio``: finds the
    best-aligned substring of the target of the token's length, then
    scores Levenshtein-equivalent similarity. This is the natural
    extension of the previous ``token in target`` (substring) check —
    a perfect substring scores 100; a one-edit typo on a short word
    typically scores in the high 80s / low 90s.
    """
    total = 0.0
    for token in tokens:
        best = 0.0
        for target, weight in targets:
            ratio = fuzz.partial_ratio(token, target)
            if ratio >= _SIMILARITY_THRESHOLD:
                token_score = weight * (ratio / 100.0)
                if token_score > best:
                    best = token_score
        if best == 0.0:
            return 0.0  # token didn't clear threshold anywhere → reject
        total += best
    return total


def search(query: str, *, exact: bool = False, limit: int = 10) -> list[Material]:
    """Find Materials in the loaded library by name, key, or grade.

    - **Fuzzy (default)**: tokenize ``query`` on whitespace; every token
      must match somewhere (registry key, ``Material.name``, ``grade``,
      or a hierarchy parent name). Ranked by summed target weight.
    - **Exact** (``exact=True``): the whole normalized query must equal
      the registry key OR ``Material.name`` OR ``Material.grade`` — same
      three targets the fuzzy path uses, but full-string equality. Use
      this to resolve a single known material without the list noise of
      fuzzy mode.

    Normalization: NFKC + case-fold + whitespace-collapse. Curly quotes,
    em-dashes, non-breaking spaces, leading/trailing and internal-run
    whitespace all fold away before comparison.

    Returns an empty list for an empty / whitespace-only query.

    Examples::

        pymat.search("stainless")
        # → [stainless, s304, s316L, s410, ...]

        pymat.search("stainless 316")
        # → [s316L]  — all tokens must match

        pymat.search("304", exact=True)
        # → [s304]  — grade match, no fuzz

        pymat.search("Stainless Steel", exact=True)
        # → [stainless]  — exact parent name

    Triggers ``load_all()`` on first call so results are exhaustive
    across categories.
    """
    normalized = _normalize(query)
    if not normalized:
        return []

    # Import lazily to avoid circular import at module load: pymat's
    # __init__.py hasn't finished initializing when this module loads.
    from . import load_all, registry

    load_all()
    all_materials = registry.list_all()

    scored: list[tuple[float, int, str, Material]] = []

    if exact:
        # Full-string equality against key / name / grade. Same three
        # targets the fuzzy path cares about.
        for key, material in all_materials.items():
            candidates = [key, material.name or ""]
            grade = getattr(material, "grade", None)
            if grade:
                candidates.append(str(grade))
            if any(_normalize(c) == normalized for c in candidates):
                # Single-match: tie-break by shorter key for determinism.
                scored.append((0.0, len(key), key, material))
    else:
        tokens = normalized.split()
        for key, material in all_materials.items():
            targets = _targets(key, material)
            s = _score(tokens, targets)
            if s > 0:
                scored.append((-s, len(key), key, material))

    scored.sort()
    return [m for _, _, _, m in scored[:limit]]
