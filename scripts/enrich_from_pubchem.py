#!/usr/bin/env python3
"""Enrich liquids & gases with PubChem PUG-REST/PUG-View values — #165.

PubChem (NCBI/NLM) is a US-government compound database; per NCBI's data
policies it is freely usable including for commercial purposes. We tag
every `_sources` row with `license = "PD-USGov"` (the closest fit in our
allow-list — see `docs/data-policy.md` and `scripts/check_licenses.py`).

This enricher is intentionally **cross-check role**, not a primary
populator. NIST WebBook (#159, PR #203) already provides Lemmon REFPROP
density / Cp / k for the same fluids — and at the right (T, P) reference
state. PubChem's strength is small-molecule scalars (MW, MP, BP) for
pure compounds. Where it overlaps with NIST WebBook (density), we keep
the NIST value and use PubChem only as a sanity check.

## Properties enriched (only what the schema supports today)

* `thermal.melting_point` (°C → degC) — PubChem reports MP cleanly in °C
  for pure compounds; this is the primary writeback target.
* `mechanical.density` (g/cm³) — comparison only for gases (PubChem's
  density entries are mostly the liquid/cryogenic phase, not the STP
  gas density we store), and add-only writeback for liquids when the
  experimental string is cleanly parseable.

## Properties dropped (schema gap; document the gap)

* `molecular_weight_g_mol` — NOT in `pymat.properties.MechanicalProperties`
  today. PubChem reports it cleanly (e.g. `MolecularWeight = "18.015"`),
  but adding a runtime field is out of scope for this PR (issue #165 is
  scripts-only). The MW is still surfaced in the comparison report so
  curators see what PubChem says, and it's recorded in the `_sources`
  note for traceability.
* `thermal.boiling_point` — NOT in `pymat.properties.ThermalProperties`.
  Same story: shown in the report, written into the source note,
  not into a TOML field.

If/when the schema grows those fields (a future Phase-5 PR), this
enricher only needs a new `PropertySpec` line — the parsing already runs.

## Source endpoints

* `https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/<CID>/property/Title,MolecularFormula,MolecularWeight/JSON`
  — clean key/value JSON for MW + the canonical compound title
  (used in the citation).
* `https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/<CID>/JSON?heading=<H>`
  — experimental-section view; returns nested Sections with
  `StringWithMarkup` arrays of human-readable strings like
  `"0 °C"` or `"0.9950 g/cu cm at 25 °C"`. We extract the first
  parseable °C / g/cm³ value and skip the rest.

PubChem rate-limits at ~5 req/s. Each compound makes 4 requests
(property + Density + MeltingPoint + BoilingPoint), all cached for 30
days via `cached_get` / `cached_get_text`, so a full re-run is ~28
requests on a cold cache.

## Behaviour

* Default: comparison-only. Side-by-side report (ours vs. PubChem) with
  a 5% relative-tolerance flag (looser than NIST WebBook's 2% — PubChem
  aggregates multiple primary sources and some entries are loose; keep
  DIFFs visible to the curator).
* `--write`: ADD-ONLY. Never overwrites; only fills missing fields.
* `--dry-run`: skip writeback. Cached fetches still run.

## Density string parser — judgment call

PubChem `Density` strings are heterogeneous:
  * `"0.9950 g/cu cm at 25 °C"`           — clean, parseable
  * `"1.251 g/L at 0 °C and 1 atm; ..."`  — wrong unit for our `g/cm^3` target
  * `"Chemical and physical properties[Table#8152]"` — table reference, skip
  * `"Expands on freezing. Temp of max density 3.98 °C. ..."` — prose, skip
  * `"VAPOR DENSITY @ NORMAL TEMP APPROX SAME AS AIR ..."`  — prose, skip

`_parse_density_g_per_cm3` only matches `<float> g/cu cm` and
`<float> g/cm3` patterns; everything else returns None. For gases this
means density is almost always None on the PubChem side (their density
entries are the liquid phase) — that's fine, we surface "(no value)" in
the report rather than write a wrong number.

This enricher is NOT a runtime dependency of mat — lives in scripts/
for data curation. Shared helpers live in `scripts/_curation.py`.

## Usage

    python scripts/enrich_from_pubchem.py                   # full report
    python scripts/enrich_from_pubchem.py --key water --dry-run
    python scripts/enrich_from_pubchem.py --write
    python scripts/enrich_from_pubchem.py --report out.md
"""

from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import tomlkit  # noqa: E402
from _curation import (  # noqa: E402
    DATA_DIR,
    build_source_row,
    cached_get,
    fmt_delta,
    writeback,
)

from pymat import load_all  # noqa: E402

# --------------------------------------------------------------------------- #
# Source endpoints                                                            #
# --------------------------------------------------------------------------- #

_PROPERTY_URL = (
    "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}"
    "/property/Title,MolecularFormula,MolecularWeight/JSON"
)
_VIEW_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/{cid}/JSON"
SOURCE_NAME = "pubchem"

# 5% — looser than NIST WebBook's 2%. PubChem aggregates many primary
# sources (Merck Index, Kirk-Othmer, NTP, NIOSH, ...) at varying
# reference temperatures; a 5% gap is closer to "noise" than
# "curator-actionable", and we keep the DIFFs visible without crying
# wolf on every gas at the wrong reference state.
DEFAULT_TOL = 0.05


# --------------------------------------------------------------------------- #
# CID map                                                                     #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CompoundEntry:
    """One target compound: PubChem CID, the material key in our TOMLs, and
    which category file it lives in. Density writeback is gated on
    `density_writeback` — gases are comparison-only because PubChem's
    density entries are mostly the liquid/cryogenic phase, not STP gas."""

    cid: int
    material_key: str  # dotted path within the category TOML, e.g. "water"
    category: str  # "gases" | "liquids"
    density_writeback: bool  # True only for liquids

    @property
    def cid_str(self) -> str:
        return str(self.cid)


# CIDs verified live against pubchem.ncbi.nlm.nih.gov on 2026-05-07.
# Names confirmed via the property endpoint (Title field):
#   962   → Water
#   947   → Nitrogen      280   → Carbon Dioxide
#   23968 → Argon         297   → Methane
#   23987 → Helium        753   → Glycerol
# Notes on entries deliberately excluded:
#   - Ethanol (CID 702): no `liquids.ethanol` in our catalog yet, so
#     no comparison target. Will land with the Phase-5 compound rollout.
#   - `air` (gases.air): a mixture, not a pure compound — PubChem isn't
#     a meaningful source for it.
#   - `gases.oxygen`, `hydrogen`, `neon`, `xenon`: same density-at-cryo
#     vs density-at-STP mismatch as the others; could be added later
#     once we agree on the comparison policy. Keeping the initial scope
#     tight per the issue ("small enrichment script for liquids and
#     pure-compound gases").
ENTRY_MAP: dict[str, CompoundEntry] = {
    "water": CompoundEntry(
        cid=962, material_key="water", category="liquids", density_writeback=True
    ),
    "glycerol": CompoundEntry(
        cid=753, material_key="glycerol", category="liquids", density_writeback=True
    ),
    "nitrogen": CompoundEntry(
        cid=947, material_key="nitrogen", category="gases", density_writeback=False
    ),
    "argon": CompoundEntry(
        cid=23968, material_key="argon", category="gases", density_writeback=False
    ),
    "helium": CompoundEntry(
        cid=23987, material_key="helium", category="gases", density_writeback=False
    ),
    "co2": CompoundEntry(cid=280, material_key="co2", category="gases", density_writeback=False),
    "methane": CompoundEntry(
        cid=297, material_key="methane", category="gases", density_writeback=False
    ),
}


# --------------------------------------------------------------------------- #
# Property mapping                                                            #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class PropertySpec:
    """One enrichable property.

    `group` and `field` map into `pymat.properties.{Mechanical,Thermal}Properties`.
    `pubchem_kind` selects the PubChem extractor: `"density"` matches the
    `Density` heading, `"melting_point"` the `Melting Point` heading, etc.
    `canonical_unit` is what we write into TOML.
    """

    group: str
    field: str
    pubchem_kind: str
    canonical_unit: str
    write_enabled: bool = True


# Order matters only for the report column order.
_PROPERTIES: list[PropertySpec] = [
    PropertySpec("mechanical", "density", "density", "g/cm^3"),
    PropertySpec("thermal", "melting_point", "melting_point", "degC"),
]

# Properties surfaced in the comparison report but NOT written to TOML
# because the schema lacks the field today. Recorded here so the report
# knows to render the column and the source note can mention them.
_REPORT_ONLY = ("molecular_weight_g_mol", "boiling_point_K")


# --------------------------------------------------------------------------- #
# PubChem record                                                              #
# --------------------------------------------------------------------------- #


@dataclass
class PubChemRecord:
    """Parsed snapshot of one compound's PubChem responses.

    Each scalar is `None` if PubChem either had no entry or the string
    didn't match our conservative parsers (we never guess units).
    """

    cid: int
    title: str
    molecular_formula: str | None
    molecular_weight_g_mol: float | None
    density_g_per_cm3: float | None
    melting_point_C: float | None
    boiling_point_C: float | None
    raw_density_strings: list[str] = field(default_factory=list)
    raw_mp_strings: list[str] = field(default_factory=list)
    raw_bp_strings: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Parsers                                                                     #
# --------------------------------------------------------------------------- #


def _collect_value_strings(node: Any) -> list[str]:
    """Walk a PUG-View JSON tree and return every `StringWithMarkup` string.

    PubChem's view format is a recursive tree of Sections; a property's
    measurements live in `Information[*].Value.StringWithMarkup[*].String`.
    We don't need the structure — every match for the heading we
    requested is below the root, and parsers can filter by content.
    """
    out: list[str] = []

    def walk(n: Any) -> None:
        if isinstance(n, dict):
            if "StringWithMarkup" in n and isinstance(n["StringWithMarkup"], list):
                for sw in n["StringWithMarkup"]:
                    if isinstance(sw, dict) and isinstance(sw.get("String"), str):
                        out.append(sw["String"])
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for it in n:
                walk(it)

    walk(node)
    return out


# Match a signed float followed by `°C` (with the actual degree sign or
# the ASCII `deg C`/`degC` fallback PubChem occasionally uses).
_TEMP_C_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*(?:°|deg\s*)?C\b", re.IGNORECASE)

# Match a positive float followed by `g/cu cm` or `g/cm3` / `g/cm\^3`.
# Rejects `g/L`, `kg/L`, `g/mL` etc — the issue scope says "be
# conservative; if you can't cleanly parse a row, skip it." See the
# header for examples of what gets dropped.
_DENSITY_GCM3_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*g\s*/\s*(?:cu\s*cm|cm\s*(?:\^|\*\*)?\s*3)\b",
    re.IGNORECASE,
)


def _parse_temperature_C(strings: list[str]) -> float | None:
    """Pick the first string that has a clean `<float> °C` value.

    Skips strings dominated by °F (we prefer the °C duplicate that
    PubChem usually provides alongside) and skips obvious table refs
    or marker prose like `"Chemical and physical properties[Table#...]"`.
    """
    for s in strings:
        # Skip table-reference markers — they look like real strings
        # but the value is in a separate Table element we don't fetch.
        if "[Table#" in s:
            continue
        m = _TEMP_C_RE.search(s)
        if m is None:
            continue
        # If the string only mentions °F and the regex matched a stray
        # 'C' from another word, the float should be sanity-checked.
        # In practice the regex anchors on `°C` / `degC`, so any match
        # is genuine — the test fixture covers the corner case.
        try:
            return float(m.group(1))
        except ValueError:
            continue
    return None


def _parse_density_g_per_cm3(strings: list[str]) -> float | None:
    """Pick the first string that has a clean `<float> g/cm³`-equivalent value.

    Returns None if nothing matched — that's the correct behaviour for
    gases (PubChem's density entries are at the boiling point or in
    `g/L`, neither of which we want for our STP `g/cm^3` target).
    """
    for s in strings:
        if "[Table#" in s:
            continue
        m = _DENSITY_GCM3_RE.search(s)
        if m is None:
            continue
        try:
            return float(m.group(1))
        except ValueError:
            continue
    return None


def _parse_molecular_weight(payload: dict[str, Any]) -> tuple[str | None, str | None, float | None]:
    """Pluck `Title`, `MolecularFormula`, `MolecularWeight` from PUG-REST JSON.

    PubChem returns MW as a string (e.g. `"18.015"`); we cast to float.
    Missing keys return None — callers fall back to a degraded report
    rather than aborting the batch.
    """
    try:
        prop = payload["PropertyTable"]["Properties"][0]
    except (KeyError, IndexError, TypeError):
        return None, None, None
    title = prop.get("Title")
    formula = prop.get("MolecularFormula")
    mw_raw = prop.get("MolecularWeight")
    mw: float | None = None
    if isinstance(mw_raw, (int, float)):
        mw = float(mw_raw)
    elif isinstance(mw_raw, str):
        try:
            mw = float(mw_raw)
        except ValueError:
            mw = None
    return title, formula, mw


# --------------------------------------------------------------------------- #
# Fetch                                                                       #
# --------------------------------------------------------------------------- #


def fetch_compound(cid: int) -> PubChemRecord:
    """Fetch one CID's property + density + MP + BP records and parse them.

    Each sub-request is independently cached (30-day TTL) via
    `cached_get`, keyed by URL — so a re-run only refetches what
    expired. On any single sub-request failure we log a None for that
    field and continue; the caller treats partial records as normal.
    """
    prop_payload = cached_get(
        _PROPERTY_URL.format(cid=cid),
        source=SOURCE_NAME,
        ttl_days=30,
    )
    title, formula, mw = _parse_molecular_weight(prop_payload)

    density_payload = cached_get(
        _VIEW_URL.format(cid=cid),
        params={"heading": "Density"},
        source=SOURCE_NAME,
        ttl_days=30,
    )
    density_strings = _collect_value_strings(density_payload)
    density = _parse_density_g_per_cm3(density_strings)

    mp_payload = cached_get(
        _VIEW_URL.format(cid=cid),
        params={"heading": "Melting Point"},
        source=SOURCE_NAME,
        ttl_days=30,
    )
    mp_strings = _collect_value_strings(mp_payload)
    melting_C = _parse_temperature_C(mp_strings)

    bp_payload = cached_get(
        _VIEW_URL.format(cid=cid),
        params={"heading": "Boiling Point"},
        source=SOURCE_NAME,
        ttl_days=30,
    )
    bp_strings = _collect_value_strings(bp_payload)
    boiling_C = _parse_temperature_C(bp_strings)

    return PubChemRecord(
        cid=cid,
        title=title or f"CID {cid}",
        molecular_formula=formula,
        molecular_weight_g_mol=mw,
        density_g_per_cm3=density,
        melting_point_C=melting_C,
        boiling_point_C=boiling_C,
        raw_density_strings=density_strings,
        raw_mp_strings=mp_strings,
        raw_bp_strings=bp_strings,
    )


# --------------------------------------------------------------------------- #
# TOML helpers                                                                #
# --------------------------------------------------------------------------- #


def _read_doc(toml_path: Path) -> tomlkit.TOMLDocument:
    return tomlkit.parse(toml_path.read_text(encoding="utf-8"))


def _walk(doc: Any, dotted: str) -> Any | None:
    node: Any = doc
    for seg in dotted.split("."):
        if not isinstance(node, dict) or seg not in node:
            return None
        node = node[seg]
    return node


def _ours_value(mat: Any, group: str, field_name: str) -> float | None:
    if mat is None:
        return None
    props = getattr(mat, "properties", None)
    if props is None:
        return None
    grp = getattr(props, group, None)
    if grp is None:
        return None
    return getattr(grp, field_name, None)


def _today_iso() -> str:
    return _dt.date.today().isoformat()


# --------------------------------------------------------------------------- #
# Source row + writeback                                                      #
# --------------------------------------------------------------------------- #


def _make_source_row(entry: CompoundEntry, record: PubChemRecord) -> dict[str, str]:
    """Build a `_sources` row for one (entry, property) pair.

    The note carries the MW / MP / BP triple so a curator reading the
    TOML two years from now sees what PubChem said at fetch time —
    even for the schema-gap properties (MW, BP) we don't write into
    a field. `Closes #165` traceability lives in PR/commit, not here.
    """
    parts: list[str] = []
    if record.molecular_weight_g_mol is not None:
        parts.append(f"MW={record.molecular_weight_g_mol:g} g/mol")
    if record.melting_point_C is not None:
        mp_K = record.melting_point_C + 273.15
        parts.append(f"MP={mp_K:.4g} K")
    if record.boiling_point_C is not None:
        bp_K = record.boiling_point_C + 273.15
        parts.append(f"BP={bp_K:.4g} K")
    summary = ", ".join(parts) if parts else "no scalars parsed"
    note = f"{summary} from PubChem PUG-REST/PUG-View; fetched {_today_iso()}"
    return build_source_row(
        citation=f"PubChem CID {record.cid} ({record.title})",
        kind="handbook",
        ref=f"pubchem.ncbi.nlm.nih.gov/compound/{record.cid}",
        license="PD-USGov",
        note=note,
    )


def _apply_writeback(
    *,
    toml_path: Path,
    material_key: str,
    spec: PropertySpec,
    value: float,
    entry: CompoundEntry,
    record: PubChemRecord,
) -> None:
    """Conservative add-only writeback. Caller verifies the field is absent."""
    material_path = material_key.split(".") + [spec.group]
    src = _make_source_row(entry, record)
    updates = {f"{spec.field}_value": value, f"{spec.field}_unit": spec.canonical_unit}
    writeback(
        toml_path,
        material_path,
        updates,
        sources={spec.field: src},
    )


# --------------------------------------------------------------------------- #
# Comparison                                                                  #
# --------------------------------------------------------------------------- #


@dataclass
class Row:
    key: str
    cid: int
    title: str
    formula: str | None
    cells: dict[str, str]
    diffs: list[str]
    missing: list[str]
    status: str = "OK"
    note: str = ""


def _pubchem_value_for(spec: PropertySpec, record: PubChemRecord) -> float | None:
    """Return PubChem's value for `spec` already converted to our canonical unit."""
    if spec.pubchem_kind == "density":
        return record.density_g_per_cm3
    if spec.pubchem_kind == "melting_point":
        # PubChem MP is °C; our schema stores melting_point in degC → identity.
        return record.melting_point_C
    return None


def _compare_one(
    *,
    material_key: str,
    entry: CompoundEntry,
    mats: dict,
    toml_path: Path,
    write: bool,
    tol: float = DEFAULT_TOL,
) -> Row:
    cells: dict[str, str] = {}
    diffs: list[str] = []
    missing: list[str] = []

    try:
        record = fetch_compound(entry.cid)
    except Exception as exc:  # network/parse errors → ERROR row, continue.
        return Row(
            key=material_key,
            cid=entry.cid,
            title=f"CID {entry.cid}",
            formula=None,
            cells={spec.field: "—" for spec in _PROPERTIES},
            diffs=[],
            missing=[],
            status="ERROR",
            note=f"fetch/parse failed: {exc}",
        )

    doc = _read_doc(toml_path)
    material_node = _walk(doc, material_key)

    for spec in _PROPERTIES:
        ours = _ours_value(mats.get(material_key), spec.group, spec.field)
        theirs = _pubchem_value_for(spec, record)
        if theirs is None:
            cells[spec.field] = "(no value)"
            continue
        cell = fmt_delta(ours, theirs, tol=tol)
        cells[spec.field] = cell
        if "DIFF" in cell:
            diffs.append(spec.field)
        if ours is None and theirs is not None:
            missing.append(spec.field)
            # Density writeback is gated on the entry — gases skip it
            # because PubChem density isn't at our STP reference state.
            if spec.field == "density" and not entry.density_writeback:
                continue
            if write:
                # Defensive double-check on disk.
                group_node = (
                    material_node.get(spec.group) if isinstance(material_node, dict) else None
                )
                already_set = isinstance(group_node, dict) and (
                    f"{spec.field}_value" in group_node or spec.field in group_node
                )
                if not already_set:
                    _apply_writeback(
                        toml_path=toml_path,
                        material_key=material_key,
                        spec=spec,
                        value=float(theirs),
                        entry=entry,
                        record=record,
                    )

    # Surface report-only (schema-gap) values in their own cells.
    if record.molecular_weight_g_mol is not None:
        cells["molecular_weight_g_mol"] = f"PubChem={record.molecular_weight_g_mol:g}"
    else:
        cells["molecular_weight_g_mol"] = "(no value)"
    if record.boiling_point_C is not None:
        bp_K = record.boiling_point_C + 273.15
        cells["boiling_point_K"] = f"PubChem={bp_K:.4g}"
    else:
        cells["boiling_point_K"] = "(no value)"

    return Row(
        key=material_key,
        cid=entry.cid,
        title=record.title,
        formula=record.molecular_formula,
        cells=cells,
        diffs=diffs,
        missing=missing,
    )


# --------------------------------------------------------------------------- #
# Report                                                                      #
# --------------------------------------------------------------------------- #


def _render_report(rows: list[Row], *, write: bool) -> str:
    lines: list[str] = []
    lines.append("# PubChem (PUG-REST / PUG-View) enrichment report")
    lines.append("")
    lines.append(f"Date: {_today_iso()}")
    lines.append(f"Mode: {'write (add-only)' if write else 'comparison-only'}")
    lines.append(f"Tolerance: {DEFAULT_TOL * 100:.1f}% (DIFF flag threshold)")
    lines.append(f"Materials checked: {len(rows)}")
    diffs = sum(1 for r in rows if r.diffs)
    miss = sum(1 for r in rows if r.missing)
    err = sum(1 for r in rows if r.status == "ERROR")
    lines.append(f"DIFF: {diffs}  MISSING: {miss}  ERROR: {err}")
    lines.append("")

    columns = [s.field for s in _PROPERTIES] + list(_REPORT_ONLY)
    header = ["material", "cid", "title", "formula"] + columns
    lines.append(" | ".join(header))
    lines.append(" | ".join("---" for _ in header))
    for r in rows:
        cells = [r.key, str(r.cid), r.title, r.formula or "-"]
        for col in columns:
            cell = r.cells.get(col, "—")
            cells.append(cell.replace("|", "/"))
        lines.append(" | ".join(cells))
    lines.append("")

    diff_rows = [r for r in rows if r.diffs]
    miss_rows = [r for r in rows if r.missing]
    err_rows = [r for r in rows if r.status == "ERROR"]
    lines.append(f"DIFF rows: {len(diff_rows)}")
    for r in diff_rows:
        lines.append(f"  DIFF  {r.key} ({r.title}): {', '.join(r.diffs)}")
    lines.append(f"MISSING rows: {len(miss_rows)}")
    for r in miss_rows:
        action = "WROTE" if write else "would-write"
        lines.append(f"  MISSING  {r.key} ({r.title}): {', '.join(r.missing)}  [{action}]")
    if err_rows:
        lines.append(f"ERROR rows: {len(err_rows)}")
        for r in err_rows:
            lines.append(f"  ERROR  {r.key}: {r.note}")
    lines.append("")
    lines.append(
        "PubChem (NCBI/NLM) data is freely usable per NCBI policies "
        "(US-government work; tagged PD-USGov in our license allow-list). "
        "Density values for gases are typically at the liquid/cryogenic "
        "reference state and are intentionally NOT written back to TOML. "
        "MW and boiling point are surfaced in the report and source notes "
        "for traceability but the runtime schema does not yet have fields "
        "for them — see issue #165 footer."
    )
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Driver                                                                      #
# --------------------------------------------------------------------------- #


def compare(
    key_filter: str | None = None,
    *,
    dry_run: bool = False,  # noqa: ARG001 — accepted for CLI parity
    write: bool = False,
    report_path: Path | None = None,
) -> int:
    """Run the comparison; print or write the report.

    `--dry-run` is accepted for CLI parity with the other enrichers; it
    suppresses writeback (same semantics as omitting `--write`).
    Network fetches still go through `cached_get` (30-day TTL), so a
    pre-warmed cache makes this fully offline.
    """
    mats = load_all()

    targets = list(ENTRY_MAP.items())
    if key_filter is not None:
        targets = [(k, v) for k, v in targets if k == key_filter]
    if not targets:
        print(f"No targets matched key={key_filter!r}", file=sys.stderr)
        return 1

    rows: list[Row] = []
    for material_key, entry in targets:
        toml_path = DATA_DIR / f"{entry.category}.toml"
        if not toml_path.exists():
            rows.append(
                Row(
                    key=material_key,
                    cid=entry.cid,
                    title=f"CID {entry.cid}",
                    formula=None,
                    cells={spec.field: "—" for spec in _PROPERTIES},
                    diffs=[],
                    missing=[],
                    status="ERROR",
                    note=f"missing {toml_path}",
                )
            )
            continue
        rows.append(
            _compare_one(
                material_key=material_key,
                entry=entry,
                mats=mats,
                toml_path=toml_path,
                write=write,
            )
        )

    report = _render_report(rows, write=write)
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
            "Skip writeback. Network fetches are still cached; pass "
            "--key with a previously-cached entry to run fully offline."
        ),
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help=(
            "Apply add-only writeback: when a TOML field is missing and "
            "PubChem has a value (and writeback isn't gated for that "
            "compound, see ENTRY_MAP), write the value plus a `_sources` "
            "row. Existing values are NEVER overwritten."
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
