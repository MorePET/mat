#!/usr/bin/env python3
"""Compare mat's thermal/mechanical properties against Wikidata reference values.

Wikidata is CC0 and has no auth — ideal for curation-time cross-checks.
This script enumerates every material in `src/pymat/data/*.toml`, looks
up its Wikidata QID (from `[<material>.sourcing].wikidata` or the
curator-maintained fallback dict below), runs a single SPARQL query
batch, and produces a side-by-side report.

With `--write`, the enricher applies a *conservative add-only* writeback:
it never overwrites an existing TOML value, but if our value is missing
and Wikidata has one, it writes the value and a paired `_sources` row
keyed by the dotted property path (e.g. `mechanical.density`) under
`[<material>._sources]`.

This is NOT a runtime dependency of mat — it lives in scripts/ for
data curation. Shared helpers live in `scripts/_curation.py`.

Usage:
    python scripts/enrich_from_wikidata.py                 # comparison report
    python scripts/enrich_from_wikidata.py --key copper    # one material
    python scripts/enrich_from_wikidata.py --dry-run       # use fixture, no network
    python scripts/enrich_from_wikidata.py --write         # apply add-only writeback
    python scripts/enrich_from_wikidata.py --report out.md # write report to file

Source: https://query.wikidata.org/sparql
Property IDs used:
    P2054 — density            (units: Q13147228 g/cm³, Q844211 kg/m³)
    P2101 — melting point      (units: Q11579 K, Q25267 °C)
    P2102 — boiling point      (units: Q11579 K, Q25267 °C) — REPORT ONLY
    P2068 — thermal conductivity (units: Q748857 W/(m·K))
    P2056 — heat capacity      (units: Q752197 J/(kg·K), Q21075844 J/(g·K))

Deferred (issue #158 scope discipline):
    P2153 — Young's modulus  — needs per-grade resolution; revisit in a
                                follow-up after the alloy-grade matrix
                                is settled.
    P2055 — electrical resistivity — Wikidata mixes Ω·m and Ω·cm by
                                domain (metals vs. ceramics) and has no
                                clean per-grade story; revisit after
                                #170/#171 ceramics work lands.

Boiling point (P2102) is fetched and reported, but the schema has no
`boiling_point` field today (`pymat.properties.ThermalProperties`), so
the writeback path skips it. Adding the schema field is out of scope —
this PR is curation tooling only.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests  # noqa: E402
import tomlkit  # noqa: E402
from _curation import (  # noqa: E402
    DATA_DIR,
    USER_AGENT,
    build_source_row,
    fmt_delta,
    load_material_keys,
    writeback,
)

from pymat import load_all  # noqa: E402

SPARQL_URL = "https://query.wikidata.org/sparql"
FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "wikidata_sample.json"
)

# Curator-maintained fallback mapping. Used when a TOML material has no
# `[<material>.sourcing].wikidata` field. Specific grades (s304, a6061,
# hdpe) intentionally don't appear here — they cross-check against the
# parent element/polymer.
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

# Wikidata unit QIDs we understand. Anything else → log and skip the
# datapoint. Keeping the whitelist explicit (rather than a generic
# UnitNormalizer registration) because melting/boiling points need a
# Kelvin offset — multiplicative scale alone can't express that.
_UNIT_G_CM3 = "Q13147228"
_UNIT_KG_M3 = "Q844211"
_UNIT_KELVIN = "Q11579"
_UNIT_CELSIUS = "Q25267"
_UNIT_W_M_K = "Q748857"  # watt per metre-kelvin
_UNIT_J_KG_K = "Q752197"  # joule per kilogram-kelvin
_UNIT_J_G_K = "Q21075844"  # joule per gram-kelvin (×1000 → J/(kg·K))
# Molar heat capacity (J/(mol·K), Q13035094) is intentionally NOT
# normalized: converting requires the material's molar mass and brings
# in molecule-vs-formula-unit ambiguity that's out of scope for #158.


# --------------------------------------------------------------------------- #
# Unit normalization                                                          #
# --------------------------------------------------------------------------- #


def _normalize_density(amount: float, unit_qid: str) -> float | None:
    """Normalize density to g/cm³."""
    if unit_qid == _UNIT_G_CM3:
        return amount
    if unit_qid == _UNIT_KG_M3:
        return amount / 1000.0
    return None


def _normalize_temperature_c(amount: float, unit_qid: str) -> float | None:
    """Normalize temperature to °C (used for melting + boiling)."""
    if unit_qid == _UNIT_CELSIUS:
        return amount
    if unit_qid == _UNIT_KELVIN:
        return amount - 273.15
    return None


def _normalize_thermal_conductivity(amount: float, unit_qid: str) -> float | None:
    """Normalize thermal conductivity to W/(m·K)."""
    if unit_qid == _UNIT_W_M_K:
        return amount
    return None


def _normalize_specific_heat(amount: float, unit_qid: str) -> float | None:
    """Normalize specific heat to J/(kg·K).

    Wikidata mixes J/(g·K) and J/(mol·K); the latter would need a molar
    mass lookup which is out of scope (see module docstring).
    """
    if unit_qid == _UNIT_J_KG_K:
        return amount
    if unit_qid == _UNIT_J_G_K:
        return amount * 1000.0
    return None


# --------------------------------------------------------------------------- #
# SPARQL                                                                      #
# --------------------------------------------------------------------------- #


def _build_sparql(qids: list[str]) -> str:
    """Build the SPARQL query for our property set.

    Kept readable (not auto-generated) so a curator can paste it into
    https://query.wikidata.org/ and tweak interactively.
    """
    values_clause = " ".join(f"wd:{q}" for q in qids)
    return f"""
    SELECT ?item ?itemLabel ?density ?densityUnit
           ?melt ?meltUnit ?boil ?boilUnit
           ?tcond ?tcondUnit ?cp ?cpUnit ?formula WHERE {{
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
      OPTIONAL {{
        ?item p:P2102 ?bStmt . ?bStmt psv:P2102 ?bv .
        ?bv wikibase:quantityAmount ?boil .
        ?bv wikibase:quantityUnit ?boilUnit .
      }}
      OPTIONAL {{
        ?item p:P2068 ?kStmt . ?kStmt psv:P2068 ?kv .
        ?kv wikibase:quantityAmount ?tcond .
        ?kv wikibase:quantityUnit ?tcondUnit .
      }}
      OPTIONAL {{
        ?item p:P2056 ?cStmt . ?cStmt psv:P2056 ?cv .
        ?cv wikibase:quantityAmount ?cp .
        ?cv wikibase:quantityUnit ?cpUnit .
      }}
      OPTIONAL {{ ?item wdt:P274 ?formula . }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
    }}
    """


def _sparql_query(qids: list[str]) -> dict[str, dict]:
    """Run a single SPARQL query for the given Q-IDs; return {qid: props}."""
    if not qids:
        return {}
    query = _build_sparql(qids)
    r = requests.post(
        SPARQL_URL,
        data={"query": query, "format": "json"},
        headers={
            "User-Agent": f"{USER_AGENT} (https://github.com/MorePet/py-mat)",
            "Accept": "application/sparql-results+json",
        },
        timeout=30,
    )
    r.raise_for_status()
    return _parse_sparql_bindings(r.json())


def _load_fixture() -> dict:
    if not FIXTURE_PATH.exists():
        raise FileNotFoundError(f"--dry-run requires fixture at {FIXTURE_PATH}; not found")
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _parse_sparql_bindings(payload: dict) -> dict[str, dict]:
    """Parse a SPARQL JSON payload into our `{qid: {...}}` shape.

    Each key in the returned dict yields normalized scalar values where
    possible. Unparseable units are silently dropped — they surface as
    `None` and the report logs them as missing rather than wrong.
    """
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
            entry["melt_c"] = _normalize_temperature_c(float(b["melt"]["value"]), unit)
            entry["melt_raw"] = (float(b["melt"]["value"]), unit)
        if "boil" in b and "boilUnit" in b:
            unit = b["boilUnit"]["value"].rsplit("/", 1)[-1]
            entry["boil_c"] = _normalize_temperature_c(float(b["boil"]["value"]), unit)
            entry["boil_raw"] = (float(b["boil"]["value"]), unit)
        if "tcond" in b and "tcondUnit" in b:
            unit = b["tcondUnit"]["value"].rsplit("/", 1)[-1]
            entry["thermal_conductivity_w_m_k"] = _normalize_thermal_conductivity(
                float(b["tcond"]["value"]), unit
            )
            entry["thermal_conductivity_raw"] = (float(b["tcond"]["value"]), unit)
        if "cp" in b and "cpUnit" in b:
            unit = b["cpUnit"]["value"].rsplit("/", 1)[-1]
            entry["specific_heat_j_kg_k"] = _normalize_specific_heat(float(b["cp"]["value"]), unit)
            entry["specific_heat_raw"] = (float(b["cp"]["value"]), unit)
        if "formula" in b:
            entry["formula"] = b["formula"]["value"]
    return out


# --------------------------------------------------------------------------- #
# Property mapping (TOML field → Wikidata key, group, unit)                   #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class PropertySpec:
    """Maps a Wikidata-derived value onto a `[<material>.<group>]` field."""

    group: str  # "mechanical" or "thermal"
    field: str  # "density", "melting_point", ...
    wd_key: str  # key in the parsed binding dict
    canonical_unit: str  # value to write into <field>_unit
    pid: str  # Wikidata property ID for the source note
    writable: bool = True  # False → report only, never writeback


# Order matters only for report column order.
_PROPERTIES: list[PropertySpec] = [
    PropertySpec("mechanical", "density", "density_g_cm3", "g/cm^3", "P2054"),
    PropertySpec("thermal", "melting_point", "melt_c", "degC", "P2101"),
    # Boiling point isn't in the schema today (no boiling_point field on
    # ThermalProperties). Keep it report-only — adding the schema field
    # is out of scope for #158.
    PropertySpec("thermal", "boiling_point", "boil_c", "degC", "P2102", writable=False),
    PropertySpec(
        "thermal",
        "thermal_conductivity",
        "thermal_conductivity_w_m_k",
        "W/(m*K)",
        "P2068",
    ),
    PropertySpec("thermal", "specific_heat", "specific_heat_j_kg_k", "J/(kg*K)", "P2056"),
]


# --------------------------------------------------------------------------- #
# QID resolution: TOML sourcing block first, fallback dict second             #
# --------------------------------------------------------------------------- #


def _read_doc(toml_path: Path) -> tomlkit.TOMLDocument:
    return tomlkit.parse(toml_path.read_text(encoding="utf-8"))


def _walk(doc: Any, dotted: str) -> Any | None:
    """Walk `doc` down `dotted` (e.g. 'aluminum.a6061'); return None if absent."""
    node: Any = doc
    for seg in dotted.split("."):
        if not isinstance(node, dict) or seg not in node:
            return None
        node = node[seg]
    return node


def _resolve_qid(doc: Any, material_key: str) -> str | None:
    """Look up the Wikidata QID for `material_key`.

    Preference order:
    1. `[<material_key>.sourcing].wikidata` in the TOML
    2. `WIKIDATA_QIDS[material_key]` (curator-maintained fallback)
    3. None — caller skips
    """
    node = _walk(doc, material_key)
    if isinstance(node, dict):
        sourcing = node.get("sourcing")
        if isinstance(sourcing, dict):
            wd = sourcing.get("wikidata")
            if isinstance(wd, str) and wd.startswith("Q"):
                return wd
    return WIKIDATA_QIDS.get(material_key)


# --------------------------------------------------------------------------- #
# Comparison + writeback                                                      #
# --------------------------------------------------------------------------- #


@dataclass
class Row:
    """One material's comparison row in the diff report."""

    category: str
    key: str
    qid: str
    cells: dict[str, str]  # field name → formatted comparison cell
    diffs: list[str]  # field names with DIFF flag
    missing: list[str]  # field names where ours is None and wd has a value


def _category_for_key(material_key: str) -> str | None:
    """Find which `<category>.toml` defines `material_key`."""
    for cat_path in DATA_DIR.glob("*.toml"):
        doc = _read_doc(cat_path)
        if _walk(doc, material_key) is not None:
            return cat_path.stem
    return None


def _ours_value(mat: Any, group: str, field: str) -> float | None:
    """Read the loaded scalar value for (group, field), or None."""
    if mat is None:
        return None
    props = getattr(mat, "properties", None)
    if props is None:
        return None
    grp = getattr(props, group, None)
    if grp is None:
        return None
    return getattr(grp, field, None)


def _today_iso() -> str:
    return _dt.date.today().isoformat()


def _apply_writeback(
    toml_path: Path,
    material_key: str,
    group: str,
    field: str,
    value: float,
    canonical_unit: str,
    qid: str,
    pid: str,
) -> None:
    """Write a missing value + paired `_sources` row.

    Conservative add-only — caller has already verified that `field`
    is absent in the TOML.
    """
    note = f"{pid} via SPARQL {_today_iso()}"
    row = build_source_row(
        citation=f"Wikidata {qid}",
        kind="qid",
        ref=qid,
        license="CC0",
        note=note,
    )
    material_path = material_key.split(".") + [group]
    writeback(
        toml_path,
        material_path,
        {f"{field}_value": value, f"{field}_unit": canonical_unit},
        sources={field: row},
    )


def _compare_one(
    *,
    category: str,
    material_key: str,
    qid: str,
    wd_entry: dict,
    mats: dict,
    toml_path: Path,
    write: bool,
    tol: float = 0.05,
) -> Row:
    """Compare every property for one material; optionally writeback."""
    cells: dict[str, str] = {}
    diffs: list[str] = []
    missing: list[str] = []

    # Re-parse the TOML each call so writeback() within this loop sees
    # the latest disk state. Cheap enough — `<category>.toml` is small.
    doc = _read_doc(toml_path)
    material_node = _walk(doc, material_key)

    for spec in _PROPERTIES:
        ours = _ours_value(mats.get(material_key), spec.group, spec.field)
        theirs = wd_entry.get(spec.wd_key)
        cell = fmt_delta(ours, theirs, tol=tol)
        cells[spec.field] = cell
        if "DIFF" in cell:
            diffs.append(spec.field)
        # MISSING: ours absent, wd present, AND the field is writable
        # (i.e. the schema knows about it). Boiling stays report-only.
        if ours is None and theirs is not None and spec.writable:
            missing.append(spec.field)

            if write:
                # Defensive: writeback only if the TOML truly lacks the
                # `<field>_value` key. The loaded `mat` could be None
                # because the property *group* doesn't exist yet.
                group_node = (
                    material_node.get(spec.group) if isinstance(material_node, dict) else None
                )
                already_set = isinstance(group_node, dict) and (
                    f"{spec.field}_value" in group_node or spec.field in group_node
                )
                if not already_set:
                    _apply_writeback(
                        toml_path,
                        material_key,
                        spec.group,
                        spec.field,
                        float(theirs),
                        spec.canonical_unit,
                        qid,
                        spec.pid,
                    )

    return Row(
        category=category,
        key=material_key,
        qid=qid,
        cells=cells,
        diffs=diffs,
        missing=missing,
    )


# --------------------------------------------------------------------------- #
# Report rendering                                                            #
# --------------------------------------------------------------------------- #


def _render_report(rows: list[Row], write: bool) -> str:
    """Render the diff report in a stable, greppable format."""
    lines: list[str] = []
    lines.append("# Wikidata enrichment report")
    lines.append("")
    lines.append(f"Date: {_today_iso()}")
    lines.append(f"Mode: {'write (add-only)' if write else 'comparison-only'}")
    lines.append(f"Materials checked: {len(rows)}")
    lines.append("")

    header = ["material", "qid"] + [s.field for s in _PROPERTIES]
    lines.append(" | ".join(header))
    lines.append(" | ".join("---" for _ in header))
    for r in rows:
        cells = [r.key, r.qid]
        for spec in _PROPERTIES:
            cell = r.cells.get(spec.field, "—")
            cells.append(cell.replace("|", "/"))
        lines.append(" | ".join(cells))
    lines.append("")

    # Inline DIFF / MISSING summary — easy to grep.
    diff_rows = [r for r in rows if r.diffs]
    miss_rows = [r for r in rows if r.missing]
    lines.append(f"DIFF rows: {len(diff_rows)}")
    for r in diff_rows:
        lines.append(f"  DIFF  {r.key} ({r.qid}): {', '.join(r.diffs)}")
    lines.append(f"MISSING rows: {len(miss_rows)}")
    for r in miss_rows:
        action = "WROTE" if write else "would-write"
        lines.append(f"  MISSING  {r.key} ({r.qid}): {', '.join(r.missing)}  [{action}]")
    lines.append("")
    lines.append("Wikidata values are CC0; cited via QIDs in `_sources` rows.")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Driver                                                                      #
# --------------------------------------------------------------------------- #


def _enumerate_targets(key_filter: str | None) -> list[tuple[str, str, str]]:
    """Return `(category, material_key, qid)` triples for every target.

    Iterates over every `<category>.toml` in `DATA_DIR`, walks each
    material via `load_material_keys`, and resolves the QID. Materials
    without a QID are silently skipped.
    """
    targets: list[tuple[str, str, str]] = []
    for cat_path in sorted(DATA_DIR.glob("*.toml")):
        category = cat_path.stem
        doc = _read_doc(cat_path)
        for mkey in load_material_keys(category):
            if key_filter is not None and mkey != key_filter:
                continue
            qid = _resolve_qid(doc, mkey)
            if qid is None:
                continue
            targets.append((category, mkey, qid))
    return targets


def compare(
    key_filter: str | None = None,
    *,
    dry_run: bool = False,
    write: bool = False,
    report_path: Path | None = None,
) -> int:
    """Run the comparison; print or write the report.

    Return code 0 on success regardless of DIFF count — the report is
    advisory. Non-zero only on hard errors (missing fixture, network).
    """
    mats = load_all()
    targets = _enumerate_targets(key_filter)

    if not targets:
        msg = (
            f"No targets matched key={key_filter!r}"
            if key_filter
            else "No materials with Wikidata QIDs found"
        )
        print(msg, file=sys.stderr)
        return 1

    if dry_run:
        wd = _parse_sparql_bindings(_load_fixture())
    else:
        # De-duplicate QIDs: brass and stainless map to distinct Q-IDs,
        # but a future curator could legitimately point two grades at
        # the same parent QID, and we shouldn't pay for it twice.
        unique_qids = sorted({qid for _, _, qid in targets})
        wd = _sparql_query(unique_qids)

    rows: list[Row] = []
    for category, mkey, qid in targets:
        toml_path = DATA_DIR / f"{category}.toml"
        wd_entry = wd.get(qid, {})
        rows.append(
            _compare_one(
                category=category,
                material_key=mkey,
                qid=qid,
                wd_entry=wd_entry,
                mats=mats,
                toml_path=toml_path,
                write=write,
            )
        )

    report = _render_report(rows, write)
    if report_path is None:
        print(report)
    else:
        report_path.write_text(report, encoding="utf-8")
        print(f"Report written to {report_path}", file=sys.stderr)

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
    parser.add_argument(
        "--write",
        action="store_true",
        help=(
            "Apply add-only writeback: when a TOML field is missing and "
            "Wikidata has a value, write the value plus a `_sources` row. "
            "Existing values are NEVER overwritten."
        ),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Write the diff report to this path (default: stdout).",
    )
    args = parser.parse_args()
    sys.exit(
        compare(
            args.key,
            dry_run=args.dry_run,
            write=args.write,
            report_path=args.report,
        )
    )


if __name__ == "__main__":
    main()
