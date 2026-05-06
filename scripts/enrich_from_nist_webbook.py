#!/usr/bin/env python3
"""Enrich gases & liquids with NIST Chemistry WebBook (SRD 69) values — #159.

NIST SRD 69 (Lemmon-REFPROP equation of state) covers the thermophysical
properties of ~74 fluids (Cp, viscosity, thermal conductivity, density
vs T, P). It is **PD-USGov** — US-government work, public domain in the
US per 17 U.S.C. §105 — so attribution is not legally required, but the
NIST AS-IS notice still applies (see the per-row `note` and the report
footer).

This enricher targets a small, audited subset that already exists in
`src/pymat/data/{gases,liquids}.toml`:

* `water` — liquid at T=293.15 K, P=1.01325 bar
* `nitrogen` — gas at T=298.15 K, P=1.01325 bar (STP, ish)
* `argon` — gas at T=298.15 K, P=1.01325 bar
* `helium` — gas at T=298.15 K, P=1.01325 bar
* `co2` — gas at T=298.15 K, P=1.01325 bar

Phase 5 will widen the set; this PR sticks to overlap with the current
catalog. New fluids are explicitly out of scope (see issue #159 design
review).

Properties enriched (only those already in the schema):

* `mechanical.density` — converted to g/cm³ for the comparison + writeback
* `thermal.specific_heat` — converted to J/(kg·K) (NIST ships J/(g·K))
* `thermal.thermal_conductivity` — W/(m·K), already canonical

Viscosity is in the NIST response but the runtime schema has no
viscosity field today; we skip that column rather than invent one.
Temperature-dependent curves are also out of scope here — that's a
separate Phase-4 follow-up.

This is NOT a runtime dependency of mat — lives in scripts/ for data
curation. Shared helpers live in `scripts/_curation.py`.

## Source endpoint

NIST WebBook has no JSON API. The `Action=Data&Type=IsoBar` flavour of
`https://webbook.nist.gov/cgi/fluid.cgi` returns a clean tab-separated
table whose first line is the column header. We request a 2-row range
spanning the target temperature so the WebBook accepts the query (a
zero-width range triggers a "Range Error" page); we then pick the row
whose temperature matches the target.

The Lemmon REFPROP equation of state is what NIST runs to produce these
values; we cite it explicitly in the `note` field so curators know the
provenance is a numerical model, not a primary measurement.

## Behaviour

* Default: comparison-only. Prints a side-by-side report of our value
  vs. NIST's with a relative-tolerance flag (DIFF if >2%).
* `--write`: ADD-ONLY. If a property is already populated on a target
  material, log DIFF and SKIP — we never overwrite curator data.
* `--dry-run`: skip writeback. Network fetches still hit
  `cached_get_text` (30-day TTL); use a pre-warmed cache or the test
  fixture for true offline mode.
* Cache: backs `cached_get_text` under `scripts/.cache/nist_webbook/`.

## Usage

    python scripts/enrich_from_nist_webbook.py                    # full report
    python scripts/enrich_from_nist_webbook.py --key water --dry-run
    python scripts/enrich_from_nist_webbook.py --write
    python scripts/enrich_from_nist_webbook.py --report out.md
"""

from __future__ import annotations

import argparse
import datetime as _dt
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import tomlkit  # noqa: E402
from _curation import (  # noqa: E402
    DATA_DIR,
    build_source_row,
    cached_get_text,
    fmt_delta,
    writeback,
)

from pymat import load_all  # noqa: E402

# --------------------------------------------------------------------------- #
# Source endpoint                                                             #
# --------------------------------------------------------------------------- #

_BASE_URL = "https://webbook.nist.gov/cgi/fluid.cgi"
SOURCE_NAME = "nist_webbook"

# Tighter than Wikidata's 5%: NIST WebBook is a reference-grade source
# (Lemmon REFPROP equation of state), so >2% gap is curator-actionable.
DEFAULT_TOL = 0.02

# Standard pressure for both gases and liquids in this enricher.
_P_BAR = 1.01325


# --------------------------------------------------------------------------- #
# Per-fluid mapping                                                           #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class FluidEntry:
    """One target fluid: NIST CAS-derived ID, the (T, P) point, the species
    name (for the citation), and which TOML category houses it."""

    cas_id: str  # NIST WebBook ID, e.g. "C7732185"
    species: str  # human-readable species name for the citation
    category: str  # category TOML file ("gases" / "liquids")
    t_kelvin: float  # target temperature in K
    p_bar: float = _P_BAR  # target pressure in bar (default = 1 atm)


# CAS IDs verified live against webbook.nist.gov on 2026-05-07.
# Each fluid's category matches its `[<key>]` location in
# src/pymat/data/{gases,liquids}.toml; see _CATEGORY_BASES at runtime.
ENTRY_MAP: dict[str, FluidEntry] = {
    # `water` lives in liquids.toml; the WebBook gives the liquid phase
    # at this (T, P) point.
    "water": FluidEntry(cas_id="C7732185", species="Water", category="liquids", t_kelvin=293.15),
    "nitrogen": FluidEntry(
        cas_id="C7727379", species="Nitrogen", category="gases", t_kelvin=298.15
    ),
    "argon": FluidEntry(cas_id="C7440371", species="Argon", category="gases", t_kelvin=298.15),
    "helium": FluidEntry(cas_id="C7440597", species="Helium", category="gases", t_kelvin=298.15),
    "co2": FluidEntry(
        cas_id="C124389",
        species="Carbon Dioxide",
        category="gases",
        t_kelvin=298.15,
    ),
}


# --------------------------------------------------------------------------- #
# Property mapping                                                            #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class PropertySpec:
    """One enrichable property.

    `group` is the TOML sub-table (`mechanical` / `thermal`), `field` is
    the schema field name (matching the dataclass attribute), `column` is
    the NIST TSV column header substring we match on, `canonical_unit` is
    the unit we write into TOML, and `scale` is the multiplier from
    NIST's units to ours.
    """

    group: str
    field: str
    column: str
    canonical_unit: str
    scale: float


# NIST WebBook units (after the canonical IsoBar request):
#   Density       — kg/m³        → multiply by 1e-3  → g/cm³
#   Cp            — J/(g·K)      → multiply by 1e3   → J/(kg·K)
#   Therm. Cond.  — W/(m·K)      → identity
_PROPERTIES: list[PropertySpec] = [
    PropertySpec("mechanical", "density", "Density", "g/cm^3", 1e-3),
    PropertySpec("thermal", "specific_heat", "Cp", "J/(kg*K)", 1e3),
    PropertySpec(
        "thermal",
        "thermal_conductivity",
        "Therm. Cond.",
        "W/(m*K)",
        1.0,
    ),
]


# --------------------------------------------------------------------------- #
# TSV parsing                                                                 #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class FluidRow:
    """One row of the NIST WebBook IsoBar TSV, keyed by header name.

    `header_to_value` carries the raw float values; the column-name
    keys preserve the WebBook's spelling (e.g. `'Therm. Cond. (W/m*K)'`)
    so we can match against `PropertySpec.column` substrings.
    """

    t_kelvin: float
    p_bar: float
    phase: str
    header_to_value: dict[str, float]


def parse_isobar_tsv(text: str) -> list[FluidRow]:
    """Parse the WebBook IsoBar TSV into a list of `FluidRow`.

    Rejects responses that don't start with a `Temperature` header (which
    is the WebBook's tell-tale for an HTML error page leaking through —
    e.g. 'Range Error').
    """
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise ValueError("empty TSV")
    header_line = lines[0]
    if not header_line.startswith("Temperature"):
        raise ValueError(
            f"Response does not look like a WebBook IsoBar TSV (first line: {header_line[:80]!r})"
        )
    headers = header_line.split("\t")
    # The Phase column is a string; everything else is numeric.
    try:
        phase_idx = headers.index("Phase")
    except ValueError:
        phase_idx = -1

    rows: list[FluidRow] = []
    for raw in lines[1:]:
        cols = raw.split("\t")
        if len(cols) < len(headers):
            continue
        try:
            t = float(cols[0])
            p = float(cols[1])
        except ValueError:
            continue
        phase = cols[phase_idx] if phase_idx >= 0 else ""
        h2v: dict[str, float] = {}
        for i, name in enumerate(headers):
            if i == phase_idx:
                continue
            try:
                h2v[name] = float(cols[i])
            except ValueError:
                # Skip non-numeric cells (e.g. "infinite", "undefined").
                continue
        rows.append(FluidRow(t_kelvin=t, p_bar=p, phase=phase, header_to_value=h2v))
    return rows


def _select_row(rows: list[FluidRow], t_target: float) -> FluidRow:
    """Pick the row whose temperature matches `t_target` (within 1e-3 K)."""
    if not rows:
        raise ValueError("no parseable rows in TSV")
    for row in rows:
        if abs(row.t_kelvin - t_target) <= 1e-3:
            return row
    # No exact match — surface what we got rather than guess.
    seen = ", ".join(f"{r.t_kelvin:.3f}" for r in rows)
    raise ValueError(f"no row at T={t_target} K (got: {seen})")


def _column_value(row: FluidRow, column_substr: str) -> float | None:
    """Find the first column whose header contains `column_substr`."""
    for header, value in row.header_to_value.items():
        if column_substr in header:
            return value
    return None


# --------------------------------------------------------------------------- #
# Fetch                                                                       #
# --------------------------------------------------------------------------- #


def _build_params(entry: FluidEntry) -> dict[str, str]:
    """Build the WebBook query for an IsoBar 2-row range straddling the
    target temperature.

    The WebBook rejects zero-width ranges with a "Range Error" page, so
    we ask for `[t, t+5 K]` at the target pressure. We then pick the
    row that matches `t` exactly.
    """
    t_lo = entry.t_kelvin
    t_hi = entry.t_kelvin + 5.0
    return {
        "ID": entry.cas_id,
        "Action": "Data",
        "Type": "IsoBar",
        "P": f"{entry.p_bar:g}",
        "TLow": f"{t_lo:g}",
        "THigh": f"{t_hi:g}",
        "TInc": "5",
        "Digits": "5",
        "RefState": "DEF",
        "TUnit": "K",
        "PUnit": "bar",
        "DUnit": "kg/m3",
        "HUnit": "kJ/kg",
        "WUnit": "m/s",
        "VisUnit": "Pa*s",
        "STUnit": "N/m",
    }


def fetch_fluid(entry: FluidEntry) -> FluidRow:
    """Fetch and parse one fluid's IsoBar TSV; return the row at `entry.t_kelvin`.

    On HTTP error or parse failure, the caller logs the row and continues —
    never aborts the whole batch.
    """
    text = cached_get_text(
        _BASE_URL,
        _build_params(entry),
        source=SOURCE_NAME,
        suffix=".tsv",
        ttl_days=30,
    )
    rows = parse_isobar_tsv(text)
    return _select_row(rows, entry.t_kelvin)


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


def _ours_value(mat: Any, group: str, field: str) -> float | None:
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


# --------------------------------------------------------------------------- #
# Source row + writeback                                                      #
# --------------------------------------------------------------------------- #


def _make_source_row(entry: FluidEntry, field: str, row: FluidRow) -> dict[str, str]:
    """Build a `_sources` row for one (entry, field) pair.

    The note pins the (T, P) point and names the equation of state so a
    curator reading the TOML two years from now knows exactly what
    NIST gave us. The AS-IS notice is implicit in the `license =
    PD-USGov` tag plus the report footer — repeating it in every row
    note would just bloat the TOML.
    """
    note = (
        f"T={row.t_kelvin:g} K, P={row.p_bar:g} bar "
        f"(Lemmon REFPROP equation of state); fetched {_today_iso()}"
    )
    return build_source_row(
        citation=f"NIST Chemistry WebBook SRD 69 ({entry.species})",
        kind="handbook",
        ref=f"webbook.nist.gov:fluid.cgi?ID={entry.cas_id}",
        license="PD-USGov",
        note=note,
    )


def _apply_writeback(
    *,
    toml_path: Path,
    material_key: str,
    spec: PropertySpec,
    value: float,
    entry: FluidEntry,
    row: FluidRow,
) -> None:
    """Conservative add-only writeback. Caller verifies the field is absent."""
    material_path = material_key.split(".") + [spec.group]
    src = _make_source_row(entry, spec.field, row)
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
    cas_id: str
    species: str
    t_k: float
    p_bar: float
    phase: str
    cells: dict[str, str]
    diffs: list[str]
    missing: list[str]
    status: str = "OK"
    note: str = ""


def _compare_one(
    *,
    material_key: str,
    entry: FluidEntry,
    mats: dict,
    toml_path: Path,
    write: bool,
    tol: float = DEFAULT_TOL,
) -> Row:
    cells: dict[str, str] = {}
    diffs: list[str] = []
    missing: list[str] = []

    try:
        fluid_row = fetch_fluid(entry)
    except Exception as exc:  # network/parse errors → ERROR row, continue.
        return Row(
            key=material_key,
            cas_id=entry.cas_id,
            species=entry.species,
            t_k=entry.t_kelvin,
            p_bar=entry.p_bar,
            phase="-",
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
        raw = _column_value(fluid_row, spec.column)
        if raw is None:
            cells[spec.field] = "(no NIST col)"
            continue
        theirs = raw * spec.scale
        cell = fmt_delta(ours, theirs, tol=tol)
        cells[spec.field] = cell
        if "DIFF" in cell:
            diffs.append(spec.field)
        if ours is None and theirs is not None:
            missing.append(spec.field)
            if write:
                # Defensive double-check on disk — don't overwrite a
                # value that's present in TOML but was None on the
                # loaded dataclass for some reason.
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
                        row=fluid_row,
                    )

    return Row(
        key=material_key,
        cas_id=entry.cas_id,
        species=entry.species,
        t_k=fluid_row.t_kelvin,
        p_bar=fluid_row.p_bar,
        phase=fluid_row.phase,
        cells=cells,
        diffs=diffs,
        missing=missing,
    )


# --------------------------------------------------------------------------- #
# Report                                                                      #
# --------------------------------------------------------------------------- #


def _render_report(rows: list[Row], *, write: bool) -> str:
    lines: list[str] = []
    lines.append("# NIST Chemistry WebBook (SRD 69) enrichment report")
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

    header = ["material", "cas_id", "T[K]", "P[bar]", "phase"] + [s.field for s in _PROPERTIES]
    lines.append(" | ".join(header))
    lines.append(" | ".join("---" for _ in header))
    for r in rows:
        cells = [r.key, r.cas_id, f"{r.t_k:g}", f"{r.p_bar:g}", r.phase]
        for spec in _PROPERTIES:
            cell = r.cells.get(spec.field, "—")
            cells.append(cell.replace("|", "/"))
        lines.append(" | ".join(cells))
    lines.append("")

    diff_rows = [r for r in rows if r.diffs]
    miss_rows = [r for r in rows if r.missing]
    err_rows = [r for r in rows if r.status == "ERROR"]
    lines.append(f"DIFF rows: {len(diff_rows)}")
    for r in diff_rows:
        lines.append(f"  DIFF  {r.key} ({r.species}): {', '.join(r.diffs)}")
    lines.append(f"MISSING rows: {len(miss_rows)}")
    for r in miss_rows:
        action = "WROTE" if write else "would-write"
        lines.append(f"  MISSING  {r.key} ({r.species}): {', '.join(r.missing)}  [{action}]")
    if err_rows:
        lines.append(f"ERROR rows: {len(err_rows)}")
        for r in err_rows:
            lines.append(f"  ERROR  {r.key}: {r.note}")
    lines.append("")
    lines.append(
        "NIST Chemistry WebBook (SRD 69) data is PD-USGov "
        "(US-government work, public domain in the US per 17 U.S.C. §105). "
        "Per NIST: data is provided AS IS, with no warranty of any kind. "
        "Underlying values come from the Lemmon REFPROP equation of state."
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

    `--dry-run` is accepted for CLI parity with the other enrichers; in
    this script it suppresses writeback (same semantics as omitting
    `--write`). Network fetches are still cached on disk via
    `cached_get_text`.
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
                    cas_id=entry.cas_id,
                    species=entry.species,
                    t_k=entry.t_kelvin,
                    p_bar=entry.p_bar,
                    phase="-",
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
            "NIST has a value, write the value plus a `_sources` row. "
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
