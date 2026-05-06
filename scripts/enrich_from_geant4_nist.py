#!/usr/bin/env python3
"""Compare mat's scintillator + plastic properties against the Geant4
G4NistMaterialBuilder constants — issue #167.

Geant4 ships ~300 NIST-derived compounds in
`source/materials/src/G4NistMaterialBuilder.cc` (NaI, CsI, BGO, BaF₂,
polystyrene, vinyltoluene plastic-scintillator base, polycarbonate,
teflon, etc.). The constants travel under the **Geant4 Software License**
(BSD-like, attribution required). Coverage:

* `density`     — g/cm³, already canonical for py-mat
* `mean ionisation potential` (a.k.a. mean excitation energy) — eV,
  written into `[<material>.nuclear].mean_excitation_energy_eV`
  (schema field added in #157)
* `composition` — element fractions; py-mat does NOT yet store
  composition arrays (no schema field), so this enricher SKIPS the
  composition column. When/if a `[composition]` sub-table lands,
  re-run this script with the new column wired in.

Light yield, decay times, and emission spectra are NOT in
`G4NistMaterialBuilder` — those live in physics-process tables and
vendor datasheets, out of scope for this enricher.

This is NOT a runtime dependency of mat — lives in scripts/ for data
curation. Shared helpers live in `scripts/_curation.py`.

## Reproducibility

The Geant4 numbers are mirrored **by hand** into the `G4_NIST` dict
below — we do NOT fetch the source at runtime. That's deliberate:
Geant4 minor versions are stable across these constants, the upstream
file is a 2000-line C++ source that can't be parsed cleanly without a
real C++ frontend, and a curation script must be reproducible offline.
The mirror is pinned to **Geant4 v11.2.0** (current LTS).

Each mirrored entry corresponds to one `AddMaterial(...)` call in the
upstream file and cites the line number explicitly:

    Upstream: source/materials/src/G4NistMaterialBuilder.cc
    Public mirror: https://gitlab.cern.ch/geant4/geant4/-/blob/v11.2.0/source/materials/src/G4NistMaterialBuilder.cc
    GitHub mirror: https://github.com/Geant4/geant4/blob/v11.2.0/source/materials/src/G4NistMaterialBuilder.cc
    Signature: AddMaterial(name, density_g_cm3, Z, mean_excitation_eV, ncomp, state)

Bumping the pin: re-fetch the same file at the new tag, diff
`AddMaterial(...)` lines for the keys we mirror, update the dict, and
update the `GEANT4_VERSION` constant + the line numbers in each entry.

## Usage

    python scripts/enrich_from_geant4_nist.py                     # comparison report
    python scripts/enrich_from_geant4_nist.py --key bgo --dry-run # one material, offline
    python scripts/enrich_from_geant4_nist.py --write             # apply add-only writeback
    python scripts/enrich_from_geant4_nist.py --report out.md     # write report to file
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
    fmt_delta,
    load_material_keys,
    writeback,
)

from pymat import load_all  # noqa: E402

GEANT4_VERSION = "11.2.0"
G4_SOURCE_FILE = "source/materials/src/G4NistMaterialBuilder.cc"

# Tighter than the Wikidata enricher's 5%: Geant4's numbers are NIST
# reference values, so a >1% gap is curator-actionable.
DEFAULT_TOL = 0.01


# --------------------------------------------------------------------------- #
# Mirrored G4 NIST constants — Geant4 v11.2.0                                 #
# --------------------------------------------------------------------------- #
#
# Each entry mirrors one `AddMaterial(name, dens, Z, pot, ncomp, state)` call.
# `mee_eV` is the `pot` argument (mean ionisation potential in eV); a value
# of `None` means upstream passes 0.0 — Geant4 treats that as "compute from
# composition" and there is no canonical scalar to compare against.
#
# Composition is intentionally NOT mirrored: py-mat has no schema field for
# element fraction arrays today (see module docstring).


@dataclass(frozen=True)
class G4Entry:
    name: str  # e.g. "G4_BGO"
    density_g_cm3: float
    mee_eV: float | None  # None → upstream passes 0.0 (compute from composition)
    line: int  # line in G4NistMaterialBuilder.cc (Geant4 v11.2.0)


# Scintillators — mapped onto src/pymat/data/scintillators.toml entries.
# The Tl/Na-doped variants of NaI and CsI map onto the same host crystal;
# Geant4 does not differentiate dopant-induced shifts in MEE/density at
# this layer (those are downstream physics processes).
G4_NIST: dict[str, G4Entry] = {
    # ----- scintillator hosts -----
    "bgo": G4Entry("G4_BGO", 7.13, 534.1, 920),
    "nai": G4Entry("G4_SODIUM_IODIDE", 3.667, 452.0, 1673),
    "nai.Tl": G4Entry("G4_SODIUM_IODIDE", 3.667, 452.0, 1673),
    "csi": G4Entry("G4_CESIUM_IODIDE", 4.51, 553.1, 1062),
    "csi.Tl": G4Entry("G4_CESIUM_IODIDE", 4.51, 553.1, 1062),
    "csi.Na": G4Entry("G4_CESIUM_IODIDE", 4.51, 553.1, 1062),
    # PWO has MEE=0 in upstream (compute-from-composition sentinel) — we
    # still cross-check the density but skip MEE writeback.
    "pwo": G4Entry("G4_PbWO4", 8.28, None, 1833),
    # Plastic scintillator base + commercial variants — all derive from
    # G4_PLASTIC_SC_VINYLTOLUENE. BC-400 / EJ-200 are the same vinyltoluene-
    # based PVT formulation at Geant4's resolution.
    "plastic_scint": G4Entry("G4_PLASTIC_SC_VINYLTOLUENE", 1.032, 64.7, 1481),
    "plastic_scint.BC400": G4Entry("G4_PLASTIC_SC_VINYLTOLUENE", 1.032, 64.7, 1481),
    "plastic_scint.EJ200": G4Entry("G4_PLASTIC_SC_VINYLTOLUENE", 1.032, 64.7, 1481),
    # ----- plastics (subset that has a Geant4 NIST equivalent) -----
    # PMMA → G4_LUCITE (NIST treats them as equivalent).
    "pmma": G4Entry("G4_LUCITE", 1.19, 74.0, 1846),
    "pc": G4Entry("G4_POLYCARBONATE", 1.2, 73.1, 1499),
    "ptfe": G4Entry("G4_TEFLON", 2.2, 99.1, 1544),
    "pe": G4Entry("G4_POLYETHYLENE", 0.94, 57.4, 1515),
    "nylon": G4Entry("G4_NYLON-6-6", 1.14, 63.9, 1441),
    "delrin": G4Entry("G4_POLYOXYMETHYLENE", 1.425, 77.4, 1530),
    "pctfe": G4Entry("G4_POLYTRIFLUOROCHLOROETHYLENE", 2.1, 120.7, 1548),
}

# Materials we know exist in our TOMLs but Geant4 NIST does NOT cover.
# Logged in the report so the rationale is in the artifact, not in tribal
# knowledge.
KNOWN_NOT_IN_G4_NIST: dict[str, str] = {
    "lyso": (
        "G4_LYSO is not a NIST-mirrored material in Geant4 11.2; "
        "modeled at G4 build time via mixture"
    ),
    "lyso.Ce": "see lyso",
    "labr3": "G4 11.2 has G4_LANTHANUM_OXYBROMIDE (LaOBr) but not LaBr3:Ce",
    "peek": "PEEK is not in G4NistMaterialBuilder",
    "ultem": "Ultem (PEI) not in G4NistMaterialBuilder",
    "esr": "3M ESR multilayer is a vendor product, not a NIST compound",
    "pla": "PLA not in G4NistMaterialBuilder",
    "abs": "ABS not in G4NistMaterialBuilder",
    "petg": "PETG not in G4NistMaterialBuilder (G4_DACRON exists but is PET, distinct)",
    "tpu": "TPU not in G4NistMaterialBuilder",
    "vespel": "Vespel (polyimide) not in G4NistMaterialBuilder",
    "torlon": "Torlon (PAI) not in G4NistMaterialBuilder",
}

# Categories this enricher walks. The runtime catalog has many more, but
# G4NistMaterialBuilder is most useful for the scintillator + plastics
# columns — metals and ceramics get better coverage from Wikidata / NIST
# WebBook (and we don't want to silently triple-cite).
TARGET_CATEGORIES = ("scintillators", "plastics")


# --------------------------------------------------------------------------- #
# Property mapping (TOML field → G4 attribute)                                #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class PropertySpec:
    group: str  # property sub-table: "mechanical" or "nuclear"
    field: str  # field name on the dataclass
    g4_attr: str  # attribute name on G4Entry
    canonical_unit: str | None  # `None` → field is bare scalar (no _unit suffix)
    writable: bool = True


_PROPERTIES: list[PropertySpec] = [
    PropertySpec("mechanical", "density", "density_g_cm3", "g/cm^3"),
    # mean_excitation_energy_eV is a bare scalar — unit baked into name.
    PropertySpec("nuclear", "mean_excitation_energy_eV", "mee_eV", None),
]


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


def _make_source_row(entry: G4Entry, field: str) -> dict[str, str]:
    """Build a `_sources` row for one (entry, field) pair.

    `kind = "handbook"` is the closest fit in our allow-list — Geant4's
    table is itself a handbook of constants, indexed by material name and
    cited by line number into a single C++ source.
    """
    note = f"Geant4 v{GEANT4_VERSION} {entry.name}; field '{field}' mirrored on {_today_iso()}"
    return build_source_row(
        citation=f"Geant4 G4NistMaterialBuilder v{GEANT4_VERSION}",
        kind="handbook",
        ref=f"{Path(G4_SOURCE_FILE).name}:{entry.line}",
        license="Geant4-SL",
        note=note,
    )


def _apply_writeback(
    *,
    toml_path: Path,
    material_key: str,
    spec: PropertySpec,
    value: float,
    entry: G4Entry,
) -> None:
    """Conservative add-only writeback. Caller verifies the field is absent."""
    material_path = material_key.split(".") + [spec.group]
    row = _make_source_row(entry, spec.field)
    if spec.canonical_unit is None:
        # Bare scalar — no `_value`/`_unit` pair (e.g. mean_excitation_energy_eV).
        updates = {spec.field: value}
    else:
        updates = {f"{spec.field}_value": value, f"{spec.field}_unit": spec.canonical_unit}
    writeback(
        toml_path,
        material_path,
        updates,
        sources={spec.field: row},
    )


# --------------------------------------------------------------------------- #
# Comparison                                                                  #
# --------------------------------------------------------------------------- #


@dataclass
class Row:
    category: str
    key: str
    g4_name: str
    cells: dict[str, str]
    diffs: list[str]
    missing: list[str]


def _compare_one(
    *,
    category: str,
    material_key: str,
    entry: G4Entry,
    mats: dict,
    toml_path: Path,
    write: bool,
    tol: float = DEFAULT_TOL,
) -> Row:
    cells: dict[str, str] = {}
    diffs: list[str] = []
    missing: list[str] = []

    doc = _read_doc(toml_path)
    material_node = _walk(doc, material_key)

    for spec in _PROPERTIES:
        ours = _ours_value(mats.get(material_key), spec.group, spec.field)
        theirs = getattr(entry, spec.g4_attr)
        cell = fmt_delta(ours, theirs, tol=tol)
        cells[spec.field] = cell
        if "DIFF" in cell:
            diffs.append(spec.field)
        if ours is None and theirs is not None and spec.writable:
            missing.append(spec.field)
            if write:
                # Defensive: only write if the TOML truly lacks the field.
                # The loaded `mat` could be None because the property
                # group itself doesn't exist yet.
                group_node = (
                    material_node.get(spec.group) if isinstance(material_node, dict) else None
                )
                if spec.canonical_unit is None:
                    already_set = isinstance(group_node, dict) and spec.field in group_node
                else:
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
                    )

    return Row(
        category=category,
        key=material_key,
        g4_name=entry.name,
        cells=cells,
        diffs=diffs,
        missing=missing,
    )


# --------------------------------------------------------------------------- #
# Report                                                                      #
# --------------------------------------------------------------------------- #


def _render_report(
    rows: list[Row],
    skipped: list[tuple[str, str]],
    write: bool,
) -> str:
    lines: list[str] = []
    lines.append("# Geant4 NIST enrichment report")
    lines.append("")
    lines.append(f"Date: {_today_iso()}")
    lines.append(f"Geant4 version: v{GEANT4_VERSION}")
    lines.append(f"Mode: {'write (add-only)' if write else 'comparison-only'}")
    lines.append(f"Tolerance: {DEFAULT_TOL * 100:.1f}% (DIFF flag threshold)")
    lines.append(f"Materials checked: {len(rows)}")
    lines.append(f"Materials skipped (no G4 mirror): {len(skipped)}")
    lines.append("")

    header = ["material", "g4_name"] + [s.field for s in _PROPERTIES]
    lines.append(" | ".join(header))
    lines.append(" | ".join("---" for _ in header))
    for r in rows:
        cells = [r.key, r.g4_name]
        for spec in _PROPERTIES:
            cell = r.cells.get(spec.field, "—")
            cells.append(cell.replace("|", "/"))
        lines.append(" | ".join(cells))
    lines.append("")

    diff_rows = [r for r in rows if r.diffs]
    miss_rows = [r for r in rows if r.missing]
    lines.append(f"DIFF rows: {len(diff_rows)}")
    for r in diff_rows:
        lines.append(f"  DIFF  {r.key} ({r.g4_name}): {', '.join(r.diffs)}")
    lines.append(f"MISSING rows: {len(miss_rows)}")
    for r in miss_rows:
        action = "WROTE" if write else "would-write"
        lines.append(f"  MISSING  {r.key} ({r.g4_name}): {', '.join(r.missing)}  [{action}]")
    if skipped:
        lines.append("")
        lines.append("Skipped (no G4 NIST mirror):")
        for key, reason in skipped:
            lines.append(f"  SKIP  {key}: {reason}")
    lines.append("")
    lines.append(
        f"Geant4 values mirrored from {G4_SOURCE_FILE} v{GEANT4_VERSION}; "
        "license = Geant4-SL (BSD-like, attribution required)."
    )
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Driver                                                                      #
# --------------------------------------------------------------------------- #


def _enumerate_targets(
    key_filter: str | None,
) -> tuple[list[tuple[str, str, G4Entry]], list[tuple[str, str]]]:
    """Walk every key in TARGET_CATEGORIES; split into (matches, skipped).

    Materials with a G4 mirror entry → matches. Materials without →
    skipped (logged in the report). When `key_filter` is set, both
    lists are filtered down to that single key.
    """
    matches: list[tuple[str, str, G4Entry]] = []
    skipped: list[tuple[str, str]] = []
    for category in TARGET_CATEGORIES:
        # Tolerate a missing category TOML — happens in tests (which
        # only stage one category into tmp_path) and would also be the
        # right behavior if a category file were deleted in production.
        if not (DATA_DIR / f"{category}.toml").exists():
            continue
        for mkey in load_material_keys(category):
            if key_filter is not None and mkey != key_filter:
                continue
            entry = G4_NIST.get(mkey)
            if entry is None:
                reason = KNOWN_NOT_IN_G4_NIST.get(mkey, "no Geant4 NIST mirror")
                skipped.append((mkey, reason))
                continue
            matches.append((category, mkey, entry))
    return matches, skipped


def compare(
    key_filter: str | None = None,
    *,
    dry_run: bool = False,  # noqa: ARG001 — kept for CLI parity with Wikidata
    write: bool = False,
    report_path: Path | None = None,
) -> int:
    """Run the comparison; print or write the report.

    `--dry-run` is accepted for muscle-memory parity with the Wikidata
    enricher but is a no-op here: the G4 values are mirrored offline,
    so this enricher never makes a network call.
    """
    mats = load_all()
    matches, skipped = _enumerate_targets(key_filter)

    if not matches and not skipped:
        msg = (
            f"No targets matched key={key_filter!r}"
            if key_filter
            else f"No materials found in {TARGET_CATEGORIES}"
        )
        print(msg, file=sys.stderr)
        return 1

    rows: list[Row] = []
    for category, mkey, entry in matches:
        toml_path = DATA_DIR / f"{category}.toml"
        rows.append(
            _compare_one(
                category=category,
                material_key=mkey,
                entry=entry,
                mats=mats,
                toml_path=toml_path,
                write=write,
            )
        )

    report = _render_report(rows, skipped, write)
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
            "No-op for this enricher (kept for CLI parity with "
            "enrich_from_wikidata.py). Geant4 values are mirrored "
            "offline; no network call is ever made."
        ),
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help=(
            "Apply add-only writeback: when a TOML field is missing and "
            "G4_NIST has a value, write the value plus a `_sources` row. "
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
