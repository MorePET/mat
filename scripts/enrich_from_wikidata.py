#!/usr/bin/env python3
"""Compare mat's mechanical/thermal properties against Wikidata reference values.

Wikidata is CC0 and has no auth — ideal for curation-time cross-checks.
This script takes a mapping of (material_key → Wikidata Q-ID), runs a
single SPARQL query, and prints a side-by-side report so a human can
decide whether to update the TOMLs.

This is NOT a runtime dependency of mat — it lives in scripts/ for
data curation. Requires only `requests`.

Usage:
    python scripts/enrich_from_wikidata.py              # full report
    python scripts/enrich_from_wikidata.py --key copper # one material

Source: https://query.wikidata.org/sparql
Property IDs used:
    P2054 — density       (unit Q13147228 = g/cm³, Q844211 = kg/m³)
    P2101 — melting point (unit Q11579 = K, Q25267 = °C)
    P274  — chemical formula
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pymat import load_all

USER_AGENT = "pymat-curation/0.1 (https://github.com/MorePet/py-mat)"
SPARQL_URL = "https://query.wikidata.org/sparql"

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


def _sparql_query(qids: list[str]) -> dict[str, dict]:
    """Run a single SPARQL query for the given Q-IDs; return {qid: props}."""
    values_clause = " ".join(f"wd:{q}" for q in qids)
    query = f"""
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
    r = requests.post(
        SPARQL_URL,
        data={"query": query, "format": "json"},
        headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"},
        timeout=20,
    )
    r.raise_for_status()

    out: dict[str, dict] = {}
    for b in r.json()["results"]["bindings"]:
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


def _fmt_delta(ours: float | None, theirs: float | None, tol: float) -> str:
    """Format a comparison cell: ✓ within tolerance, Δ above, — missing."""
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


def compare(key_filter: str | None = None) -> int:
    mats = load_all()
    targets = {k: q for k, q in WIKIDATA_QIDS.items() if (key_filter is None or k == key_filter)}
    if not targets:
        print(f"No material '{key_filter}' in WIKIDATA_QIDS mapping", file=sys.stderr)
        return 1

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
        d_cell = _fmt_delta(ours_d, wd_d, tol=0.05)
        m_cell = _fmt_delta(ours_m, wd_m, tol=0.05)
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
    args = parser.parse_args()
    sys.exit(compare(args.key))


if __name__ == "__main__":
    main()
