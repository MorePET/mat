#!/usr/bin/env python3
"""Compare mat's mechanical/thermal properties against Wikidata reference values.

Wikidata is CC0 and has no auth — ideal for curation-time cross-checks.
This script takes a mapping of (material_key → Wikidata Q-ID), runs a
single SPARQL query, and prints a side-by-side report so a human can
decide whether to update the TOMLs.

This is NOT a runtime dependency of mat — it lives in scripts/ for
data curation. Shared helpers live in `scripts/_curation.py`.

Usage:
    python scripts/enrich_from_wikidata.py              # full report
    python scripts/enrich_from_wikidata.py --key copper # one material
    python scripts/enrich_from_wikidata.py --dry-run    # use fixture, no network

Source: https://query.wikidata.org/sparql
Property IDs used:
    P2054 — density       (unit Q13147228 = g/cm³, Q844211 = kg/m³)
    P2101 — melting point (unit Q11579 = K, Q25267 = °C)
    P274  — chemical formula
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests  # noqa: E402
from _curation import USER_AGENT, fmt_delta  # noqa: E402

from pymat import load_all  # noqa: E402

SPARQL_URL = "https://query.wikidata.org/sparql"
FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "wikidata_sample.json"
)

# Curator-maintained mapping. Start with entries that have a clear
# Wikidata identity; specific grades (s304, a6061, hdpe) don't belong
# here — cross-check the base polymer/element instead.
WIKIDATA_QIDS: dict[str, str] = {
    # Metals & alloys
    "aluminum": "Q663",  # aluminium (element)
    "copper": "Q753",  # copper (element)
    "titanium": "Q669",  # titanium (element)
    "tungsten": "Q731",  # tungsten (element)
    "lead": "Q708",  # lead (element)
    "brass": "Q39782",  # brass (alloy)
    "stainless": "Q172736",  # stainless steel (alloy)
    # Plastics (polymer Q-IDs — coverage on Wikidata varies)
    "peek": "Q145387",  # polyether ether ketone
    "pc": "Q62246",  # polycarbonate
    "pmma": "Q146123",  # poly(methyl methacrylate)
    "ptfe": "Q143252",  # polytetrafluoroethylene
    "pla": "Q413769",  # polylactic acid
    "nylon": "Q109454",  # nylon 6
    "delrin": "Q146139",  # polyoxymethylene
}

# Wikidata unit Q-IDs we understand. Anything else → mark as "unknown unit".
# Kept inline (not yet via UnitNormalizer) because density and melting
# point both have a special case (Kelvin offset, kg/m³ scale) that the
# generic registry can't express in a single multiplicative scale; the
# QID set itself is the only piece worth lifting and it stays here as a
# curated whitelist for clarity.
_UNIT_G_CM3 = "Q13147228"
_UNIT_KG_M3 = "Q844211"
_UNIT_KELVIN = "Q11579"
_UNIT_CELSIUS = "Q25267"


def _normalize_density(amount: float, unit_qid: str) -> float | None:
    """Normalize density to g/cm³."""
    if unit_qid == _UNIT_G_CM3:
        return amount
    if unit_qid == _UNIT_KG_M3:
        return amount / 1000.0
    return None


def _normalize_melting_point(amount: float, unit_qid: str) -> float | None:
    """Normalize melting point to °C."""
    if unit_qid == _UNIT_CELSIUS:
        return amount
    if unit_qid == _UNIT_KELVIN:
        return amount - 273.15
    return None


def _build_sparql(qids: list[str]) -> str:
    values_clause = " ".join(f"wd:{q}" for q in qids)
    return f"""
    SELECT ?item ?itemLabel ?density ?densityUnit ?melt ?meltUnit ?formula WHERE {{
      VALUES ?item {{ {values_clause} }}
      OPTIONAL {{
        ?item p:P2054 ?dStmt . ?dStmt psv:P2054 ?dv .
        ?dv wikibase:quantityAmount ?density .
        ?dv wikibase:quantityUnit ?densityUnit .
      }}
      OPTIONAL {{
        ?item p:P2101 ?mStmt . ?mStmt psv:P2101 ?mv .
        ?mv wikibase:quantityAmount ?melt .
        ?mv wikibase:quantityUnit ?meltUnit .
      }}
      OPTIONAL {{ ?item wdt:P274 ?formula . }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
    }}
    """


def _sparql_query(qids: list[str]) -> dict[str, dict]:
    """Run a single SPARQL query for the given Q-IDs; return {qid: props}."""
    query = _build_sparql(qids)
    r = requests.post(
        SPARQL_URL,
        data={"query": query, "format": "json"},
        headers={
            "User-Agent": f"{USER_AGENT} (https://github.com/MorePet/py-mat)",
            "Accept": "application/sparql-results+json",
        },
        timeout=20,
    )
    r.raise_for_status()
    return _parse_sparql_bindings(r.json())


def _load_fixture() -> dict:
    if not FIXTURE_PATH.exists():
        raise FileNotFoundError(f"--dry-run requires fixture at {FIXTURE_PATH}; not found")
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _parse_sparql_bindings(payload: dict) -> dict[str, dict]:
    """Parse a SPARQL JSON payload into our `{qid: {...}}` shape."""
    out: dict[str, dict] = {}
    for b in payload["results"]["bindings"]:
        qid = b["item"]["value"].rsplit("/", 1)[-1]
        entry = out.setdefault(qid, {"label": b.get("itemLabel", {}).get("value", "")})
        if "density" in b and "densityUnit" in b:
            unit = b["densityUnit"]["value"].rsplit("/", 1)[-1]
            entry["density_g_cm3"] = _normalize_density(float(b["density"]["value"]), unit)
            entry["density_raw"] = (float(b["density"]["value"]), unit)
        if "melt" in b and "meltUnit" in b:
            unit = b["meltUnit"]["value"].rsplit("/", 1)[-1]
            entry["melt_c"] = _normalize_melting_point(float(b["melt"]["value"]), unit)
            entry["melt_raw"] = (float(b["melt"]["value"]), unit)
        if "formula" in b:
            entry["formula"] = b["formula"]["value"]
    return out


def compare(key_filter: str | None = None, dry_run: bool = False) -> int:
    mats = load_all()
    targets = {k: q for k, q in WIKIDATA_QIDS.items() if (key_filter is None or k == key_filter)}
    if not targets:
        print(f"No material '{key_filter}' in WIKIDATA_QIDS mapping", file=sys.stderr)
        return 1

    if dry_run:
        wd = _parse_sparql_bindings(_load_fixture())
    else:
        wd = _sparql_query(list(targets.values()))

    print(f"{'material':<14} {'density (g/cm³)':<52} {'melt (°C)':<52}")
    print("-" * 120)
    diffs = 0
    for key, qid in targets.items():
        mat = mats.get(key)
        if mat is None:
            continue
        ours_d = mat.properties.mechanical.density
        ours_m = mat.properties.thermal.melting_point
        entry = wd.get(qid, {})
        wd_d = entry.get("density_g_cm3")
        wd_m = entry.get("melt_c")
        d_cell = fmt_delta(ours_d, wd_d, tol=0.05)
        m_cell = fmt_delta(ours_m, wd_m, tol=0.05)
        if "DIFF" in d_cell or "DIFF" in m_cell:
            diffs += 1
        print(f"{key:<14} {d_cell:<52} {m_cell:<52}")

    print()
    print(f"{diffs} material(s) show >5% relative divergence — review these first")
    print("Wikidata values are CC0; cite as Q-IDs in TOML comments when merging")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key", help="Only compare this material key")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Use the bundled SPARQL fixture instead of hitting the live "
            "endpoint — for offline reproducibility."
        ),
    )
    args = parser.parse_args()
    sys.exit(compare(args.key, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
