"""
Fuzzy search over the py-mat domain library.

``pymat.search("stainless 316")`` returns a ranked list of ``Material``
instances whose registry key, name, grade, or hierarchy path matches
the query tokens. Complements ``pymat.vis.search(...)`` (visual
catalog): two axes, same verb, no namespace collision.

Algorithm: tokenize query on whitespace; every token must match at
least one weighted target on a candidate Material for it to be
included. Score is the sum of per-token best-target weights.
"""

from __future__ import annotations

import unicodedata
from typing import TYPE_CHECKING

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


def _score(tokens: list[str], targets: list[tuple[str, int]]) -> int:
    """Score a Material against the query tokens.

    Every token must substring-match at least one target. Returns 0
    (rejected) if any token misses. Otherwise returns the sum of
    best-per-token weights — so a token matching the high-weight key
    beats a token matching only the low-weight path.
    """
    total = 0
    for token in tokens:
        best = 0
        for target, weight in targets:
            if token in target and weight > best:
                best = weight
        if best == 0:
            return 0  # token didn't match anywhere → reject
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

    scored: list[tuple[int, int, str, Material]] = []

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
                scored.append((0, len(key), key, material))
    else:
        tokens = normalized.split()
        for key, material in all_materials.items():
            targets = _targets(key, material)
            s = _score(tokens, targets)
            if s > 0:
                scored.append((-s, len(key), key, material))

    scored.sort()
    return [m for _, _, _, m in scored[:limit]]
