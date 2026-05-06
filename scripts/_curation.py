"""Shared curation helpers for the `scripts/enrich_*` family.

Phase 4 prep — extracted from `scripts/enrich_from_wikidata.py` so that
the upcoming per-source enrichers (Wikidata cleanup #158, NIST WebBook
#159, refractiveindex.info #164, MatWeb #165, PubChem #166, ASM #167)
share a single, audited implementation of:

* on-disk HTTP caching with TTL
* source-unit → py-mat canonical-unit normalization
* `_sources` row construction validated against the license allow-list
* TOML round-trip writeback that preserves comments and formatting
* material-key enumeration over a category TOML

Stdlib + `requests` + `tomlkit` only — see `scripts/requirements-curation.txt`.
This module is NOT a runtime dependency of mat; it lives in `scripts/` for
data curation only.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

import requests
import tomlkit

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = Path(__file__).resolve().parent / ".cache"
DATA_DIR = REPO_ROOT / "src" / "pymat" / "data"

USER_AGENT = "pymat-curation/0.1"

# Allow-list mirrors `scripts/check_licenses.py:ALLOWED`. Kept in sync
# manually — the audit (#175) treats that file as the single source of
# truth, but importing it here would create a cyclic dep with the
# license gate's stdlib-only constraint, so we copy.
LICENSE_ALLOWLIST = frozenset(
    {
        "CC0",
        "PD-USGov",
        "CC-BY-4.0",
        "CC-BY-SA-4.0",
        "proprietary-reference-only",
    }
)

SOURCE_KIND_ALLOWLIST = frozenset({"doi", "qid", "handbook", "vendor", "measured"})


# --------------------------------------------------------------------------- #
# 1. cached_get — HTTP cache with TTL                                         #
# --------------------------------------------------------------------------- #


def _cache_key(url: str, params: dict[str, Any] | None) -> str:
    """Stable hash for (url, params) — sorts params so dict order doesn't matter."""
    payload = {"url": url, "params": sorted((params or {}).items())}
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _cache_path(source: str, key: str, suffix: str = ".json") -> Path:
    return CACHE_DIR / source / f"{key}{suffix}"


def cached_get(
    url: str,
    params: dict[str, Any] | None = None,
    *,
    ttl_days: int = 30,
    source: str,
    method: str = "GET",
    data: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 20,
) -> dict[str, Any]:
    """Fetch a JSON response, caching it on disk under `scripts/.cache/<source>/`.

    Returns the parsed JSON body. On a cache hit within TTL, no network call
    is made. On miss (or TTL expiry), fetches via `requests`, persists, and
    returns. The `source` argument is the per-enricher namespace (e.g.
    "wikidata", "nist_webbook") and becomes a subdirectory name.

    Stdlib + `requests` only.
    """
    key = _cache_key(url, {**(params or {}), **(data or {}), "method": method})
    path = _cache_path(source, key, ".json")
    ttl_seconds = ttl_days * 86400

    if path.exists():
        age = time.time() - path.stat().st_mtime
        if age < ttl_seconds:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)

    merged_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    if headers:
        merged_headers.update(headers)

    if method.upper() == "POST":
        resp = requests.post(url, params=params, data=data, headers=merged_headers, timeout=timeout)
    else:
        resp = requests.get(url, params=params, headers=merged_headers, timeout=timeout)
    resp.raise_for_status()
    body = resp.json()

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(body, f, indent=2)
    return body


# --------------------------------------------------------------------------- #
# 2. UnitNormalizer — source unit string → py-mat canonical                  #
# --------------------------------------------------------------------------- #


class UnitNormalizer:
    """Registry mapping source-specific unit identifiers to canonical py-mat units.

    Sources speak different unit dialects:
      * Wikidata: QIDs like `Q11573` (metre), `Q12438` (kg/m³)
      * NIST WebBook: short strings like `'g/cm**3'`, `'K'`
      * refractiveindex.info: bare floats with implied wavelength units

    The registry is keyed by `(source, source_unit)` and yields the
    canonical unit string from `pymat.units.STANDARD_UNITS`. The
    `target_property` argument is reserved for future per-property unit
    overrides (e.g. resistivity in `Ω·cm` for ceramics, `Ω·m` for metals);
    today it is informational and only surfaces in error messages.
    """

    def __init__(self) -> None:
        # source -> source_unit -> (canonical_unit, scale)
        # `scale` lets us collapse Q-IDs that mean "kg/m³" → "g/cm³" (×1e-3)
        # without bolting a parallel scaling layer onto callers.
        self._mappings: dict[str, dict[str, tuple[str, float]]] = {}

    def register(
        self,
        source: str,
        source_unit: str,
        canonical_unit: str,
        scale: float = 1.0,
    ) -> None:
        """Register `(source, source_unit) → (canonical_unit, scale)`.

        `scale` is multiplied with the value before returning, so
        `register("wikidata", "Q844211", "g/cm^3", scale=1e-3)` converts
        a kg/m³ value to g/cm³ on the fly.
        """
        self._mappings.setdefault(source, {})[source_unit] = (canonical_unit, scale)

    def normalize(
        self,
        source: str,
        value: float,
        source_unit: str,
        target_property: str,
    ) -> tuple[float, str]:
        """Convert (value, source_unit) → (value, canonical_unit) for `target_property`.

        Raises `KeyError` if `(source, source_unit)` is unknown — callers
        should treat that as "skip this datapoint, log it" rather than
        guess a unit.
        """
        try:
            canonical, scale = self._mappings[source][source_unit]
        except KeyError as e:
            raise KeyError(
                f"No unit mapping for source={source!r} unit={source_unit!r} "
                f"(target property: {target_property!r}). Register one with "
                f"UnitNormalizer.register() before normalizing."
            ) from e
        return value * scale, canonical


def default_normalizer() -> UnitNormalizer:
    """Build the normalizer with the registrations needed by the existing
    `enrich_from_wikidata.py` script. New enrichers extend this with their
    own `.register(...)` calls."""
    n = UnitNormalizer()
    # Wikidata QIDs we currently understand. Extend as more property types
    # come online (#158 widens this set).
    n.register("wikidata", "Q13147228", "g/cm^3")  # g/cm³
    n.register("wikidata", "Q844211", "g/cm^3", scale=1e-3)  # kg/m³ → g/cm³
    n.register("wikidata", "Q25267", "degC")  # °C
    n.register("wikidata", "Q11579", "degC", scale=1.0)  # K → handled below
    return n


# --------------------------------------------------------------------------- #
# 3. build_source_row — typed-dict builder for `_sources` entries            #
# --------------------------------------------------------------------------- #


def build_source_row(
    citation: str,
    kind: str,
    ref: str,
    license: str,
    note: str | None = None,
) -> dict[str, str]:
    """Build a `_sources` entry dict, validating `kind` and `license`.

    Reviewer #2 ask: every enricher writes the same shape, so we
    centralize it here. Mirrors the schema enforced by
    `scripts/check_licenses.py` and the loader in `pymat/sources.py`.

    Raises `ValueError` if `kind` or `license` is outside the allow-lists.
    """
    if kind not in SOURCE_KIND_ALLOWLIST:
        allowed = ", ".join(sorted(SOURCE_KIND_ALLOWLIST))
        raise ValueError(f"kind={kind!r} not in allow-list ({allowed})")
    if license not in LICENSE_ALLOWLIST:
        allowed = ", ".join(sorted(LICENSE_ALLOWLIST))
        raise ValueError(f"license={license!r} not in allow-list ({allowed})")
    if not citation:
        raise ValueError("citation must be a non-empty string")
    if not ref:
        raise ValueError("ref must be a non-empty string")

    row: dict[str, str] = {
        "citation": citation,
        "kind": kind,
        "ref": ref,
        "license": license,
    }
    if note is not None:
        row["note"] = note
    return row


# --------------------------------------------------------------------------- #
# 4. writeback — comment-preserving TOML round-trip                          #
# --------------------------------------------------------------------------- #


def _walk_to(doc: tomlkit.TOMLDocument, path: list[str]) -> Any:
    """Walk into the tomlkit doc along `path`, creating tables as needed."""
    node: Any = doc
    for segment in path:
        if segment not in node:
            node[segment] = tomlkit.table()
        node = node[segment]
    return node


def writeback(
    toml_path: Path,
    material_path: list[str],
    updates: dict[str, Any],
    sources: dict[str, dict[str, str]] | None = None,
) -> bool:
    """Update `[material_path]` in `toml_path` with `updates`, preserving formatting.

    * `material_path` is the dotted path into the document, e.g.
      `["aluminum", "al6061", "mechanical"]` for `[aluminum.al6061.mechanical]`.
    * `updates` is a flat dict of key → value to set on that table.
    * `sources` is an optional `{property_key: source_row}` map; entries
      are attached to `[<material>._sources]` keyed by `<group>.<key>`
      where `<group>` is the last segment of `material_path` (e.g.
      `mechanical.density`). The material-level `_sources` table lives
      one level above the property group.

    Returns True if the file was modified.
    """
    text = toml_path.read_text(encoding="utf-8")
    doc = tomlkit.parse(text)

    target = _walk_to(doc, material_path)
    for key, value in updates.items():
        target[key] = value

    if sources:
        if len(material_path) < 2:
            raise ValueError(
                "writeback(sources=...) requires material_path of length >= 2 "
                "(material + property group)"
            )
        material_node = _walk_to(doc, material_path[:-1])
        group = material_path[-1]
        if "_sources" not in material_node:
            material_node["_sources"] = tomlkit.table()
        sources_table = material_node["_sources"]
        for prop_key, row in sources.items():
            entry = tomlkit.inline_table()
            for k, v in row.items():
                entry[k] = v
            sources_table[f"{group}.{prop_key}"] = entry

    new_text = tomlkit.dumps(doc)
    if new_text == text:
        return False
    toml_path.write_text(new_text, encoding="utf-8")
    return True


# --------------------------------------------------------------------------- #
# 5. load_material_keys — enumerate every material in a category TOML        #
# --------------------------------------------------------------------------- #


def load_material_keys(category: str, data_dir: Path | None = None) -> list[str]:
    """Return dotted paths to every material node in `<category>.toml`.

    Walks two levels deep: top-level tables (the family node, e.g.
    `aluminum`) and one nested level for grades (e.g. `aluminum.al6061`).
    Underscore-prefixed keys (`_sources`, `_default`, ...) and known
    property-group names are excluded.
    """
    base = data_dir if data_dir is not None else DATA_DIR
    path = base / f"{category}.toml"
    text = path.read_text(encoding="utf-8")
    doc = tomlkit.parse(text)

    # Property-group sub-tables that aren't materials.
    PROPERTY_GROUPS = {
        "mechanical",
        "thermal",
        "electrical",
        "manufacturing",
        "appearance",
        "vis",
        "sourcing",
        "magnetic",
        "nuclear",
        "optical",
    }

    result: list[str] = []
    for fam_key, fam_val in doc.items():
        if fam_key.startswith("_") or not isinstance(fam_val, dict):
            continue
        result.append(fam_key)
        for grade_key, grade_val in fam_val.items():
            if grade_key.startswith("_") or grade_key in PROPERTY_GROUPS:
                continue
            if not isinstance(grade_val, dict):
                continue
            result.append(f"{fam_key}.{grade_key}")
    return result


# --------------------------------------------------------------------------- #
# 6. fmt_delta — comparison cell formatter                                   #
# --------------------------------------------------------------------------- #


def fmt_delta(ours: float | None, theirs: float | None, tol: float) -> str:
    """Format a side-by-side comparison cell.

    `OK` if relative diff <= tol, `DIFF` otherwise; `—` if both missing,
    parenthetical note if exactly one is missing. Lifted verbatim from
    `enrich_from_wikidata._fmt_delta` so the output format is unchanged.
    """
    if ours is None and theirs is None:
        return "—"
    if ours is None:
        return f"(ours missing; wd={theirs:.4g})"
    if theirs is None:
        return f"(wd missing; ours={ours:.4g})"
    diff = abs(ours - theirs)
    rel = diff / max(abs(ours), abs(theirs), 1e-9)
    marker = "OK" if rel <= tol else "DIFF"
    return f"{marker}  ours={ours:.4g} wd={theirs:.4g} Δ={diff:.4g} ({rel * 100:.1f}%)"


__all__ = [
    "CACHE_DIR",
    "DATA_DIR",
    "LICENSE_ALLOWLIST",
    "SOURCE_KIND_ALLOWLIST",
    "USER_AGENT",
    "UnitNormalizer",
    "build_source_row",
    "cached_get",
    "default_normalizer",
    "fmt_delta",
    "load_material_keys",
    "writeback",
]


def _cli_clear_cache() -> int:  # pragma: no cover — admin helper
    """`python scripts/_curation.py --clear-cache` for forcing refetch."""
    import shutil

    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
        print(f"Cleared {CACHE_DIR}")
    else:
        print("No cache directory.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    if "--clear-cache" in sys.argv:
        sys.exit(_cli_clear_cache())
    print(__doc__)
