#!/usr/bin/env python3
"""Enrich mat optical entries with n,k dispersion from refractiveindex.info — #164.

The Polyanskiy refractiveindex.info database is **CC0** (per
https://github.com/polyanskiy/refractiveindex.info-database). It is the
canonical bulk source for the `optical.refractive_index_dispersion`
schema field added in #146 / #152: a dict of
`{wavelengths_nm: [...], n: [...], k: [...]}` (k optional for absorbing
media — metals).

This enricher pulls per-material YAML files on demand from the project's
GitHub mirror (no submodule — the database is ~100 MB), parses the
`DATA:` block, converts wavelengths from micrometres to nanometres, and
adds-only writes the result into the relevant `[<material>.optical]`
table together with a `_sources` row tagged
`optical.refractive_index_dispersion`.

Both `formula 1` (Sellmeier) and `tabulated nk` data types are
supported. For Sellmeier entries we evaluate the formula on a 50-point
log-spaced grid spanning the database's declared `wavelength_range`,
which gives downstream Geant4 / OpticsBuilder consumers a tabulated
proxy without forcing them to embed a Sellmeier evaluator.

This is NOT a runtime dependency of mat — lives in scripts/ for data
curation. Shared helpers live in `scripts/_curation.py`.

## Phase-4 scope

Per the design review on #164 this PR enriches a small, audited subset:
five scintillator hosts (`nai`, `nai.Tl`, `csi`, `csi.Tl`, `csi.Na`,
`bgo`) and three metals (`aluminum`, `copper`, `gold`). BaF₂, YAG,
sapphire, fused-silica, PMMA, polystyrene are deferred — those entries
either don't exist in mat's TOMLs yet (Phase 5 material adds) or
warrant a follow-up enrichment PR.

## Behaviour

* `--dry-run` (default-on when neither `--write` nor a network call is
  needed for the comparison): produces the report without mutating
  anything.
* `--write`: ADD-ONLY. If `optical.refractive_index_dispersion` is
  already present on a material, log DIFF and SKIP (we never silently
  overwrite curator data).
* Cache: backs `cached_get_text` with a 30-day TTL under
  `scripts/.cache/refractiveindex/`.
* Missing entries: a `404` from the GitHub raw URL is caught and
  logged; the run continues for the remaining materials.

## Usage

    python scripts/enrich_from_refractiveindex.py                    # full report
    python scripts/enrich_from_refractiveindex.py --key bgo --dry-run
    python scripts/enrich_from_refractiveindex.py --write
    python scripts/enrich_from_refractiveindex.py --report out.md
"""

from __future__ import annotations

import argparse
import datetime as _dt
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests  # noqa: E402
import tomlkit  # noqa: E402
import yaml  # noqa: E402
from _curation import (  # noqa: E402
    DATA_DIR,
    build_source_row,
    cached_get_text,
    writeback,
)

from pymat import load_all  # noqa: E402

# --------------------------------------------------------------------------- #
# Source URL pattern + per-entry mapping                                      #
# --------------------------------------------------------------------------- #

# The repo's default branch is `main` (verified 2026-05; the issue
# mentioned `master` but that branch was renamed years ago).
_BASE_URL = (
    "https://raw.githubusercontent.com/polyanskiy/"
    "refractiveindex.info-database/main/database/data/{path}.yml"
)
SOURCE_NAME = "refractiveindex"

# When we synthesise a tabulated grid from a Sellmeier `formula 1` entry
# we use this many points across the declared `wavelength_range`.
SELLMEIER_GRID_POINTS = 50

# Maps a py-mat material key → (database path, citation label). The
# database path is everything after `database/data/` and before the
# `.yml` suffix. The citation label is what we put in the `_sources`
# row. All paths verified live against `main` HEAD on 2026-05-07.
ENTRY_MAP: dict[str, tuple[str, str]] = {
    # ----- scintillator hosts (formula 1 / Sellmeier) -----
    # Tl- and Na-doped variants share the host-crystal dispersion.
    "nai": ("main/NaI/nk/Li", "Li 1976 (NaI, 297 K)"),
    "nai.Tl": ("main/NaI/nk/Li", "Li 1976 (NaI, 297 K)"),
    "csi": ("main/CsI/nk/Li", "Li 1976 (CsI)"),
    "csi.Tl": ("main/CsI/nk/Li", "Li 1976 (CsI)"),
    "csi.Na": ("main/CsI/nk/Li", "Li 1976 (CsI)"),
    "bgo": ("main/Bi4Ge3O12/nk/Williams", "Williams 1996 (BGO ord. ray)"),
    # ----- metals (tabulated nk) -----
    "aluminum": ("main/Al/nk/Rakic-LD", "Rakic 1995 (Al, Lorentz-Drude)"),
    "copper": ("main/Cu/nk/Johnson", "Johnson & Christy 1972 (Cu)"),
    "gold": ("main/Au/nk/Johnson", "Johnson & Christy 1972 (Au)"),
}

# (material_key → category file). Kept explicit rather than scanning
# every category TOML — the mapping above is small and the explicit
# table makes scope review easy.
CATEGORY_FOR: dict[str, str] = {
    "nai": "scintillators",
    "nai.Tl": "scintillators",
    "csi": "scintillators",
    "csi.Tl": "scintillators",
    "csi.Na": "scintillators",
    "bgo": "scintillators",
    "aluminum": "metals",
    "copper": "metals",
    "gold": "metals",
}


# --------------------------------------------------------------------------- #
# YAML parsing                                                                #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Dispersion:
    """Tabulated n/k samples on a wavelength grid (nanometres).

    `k` is `None` for transparent dielectrics where the source provides
    only n (Sellmeier-derived scintillators); `k` is a list-of-floats
    when the source provides absorption (tabulated metals).
    """

    wavelengths_nm: list[float]
    n: list[float]
    k: list[float] | None
    type_label: str  # "tabulated nk" / "tabulated n" / "formula 1" — for the report
    has_doi: bool
    references: str


def _extract_doi(references: str) -> str | None:
    """Pull a DOI out of the YAML's REFERENCES block (best-effort).

    refractiveindex.info uses inline HTML like
    `<a href="https://doi.org/10.1364/...">...`. We grep the URL out and
    keep the bare DOI string for the `_sources.ref`.
    """
    m = re.search(r"https?://(?:dx\.)?doi\.org/(\S+?)(?:[\"<\s])", references + '"')
    return m.group(1) if m else None


def _parse_tabulated(
    data_block: str, has_k: bool
) -> tuple[list[float], list[float], list[float] | None]:
    """Parse the `data:` string for a tabulated nk / n entry.

    Each row: `wavelength_um n [k]`. Wavelengths are micrometres in the
    source — converted to nanometres here (×1000).
    """
    wavelengths: list[float] = []
    ns: list[float] = []
    ks: list[float] | None = [] if has_k else None
    for raw_line in data_block.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        cols = line.split()
        if len(cols) < 2:
            continue
        try:
            lam_um = float(cols[0])
            n_val = float(cols[1])
        except ValueError:
            continue
        wavelengths.append(lam_um * 1000.0)  # µm → nm
        ns.append(n_val)
        if has_k:
            assert ks is not None
            if len(cols) >= 3:
                try:
                    ks.append(float(cols[2]))
                except ValueError:
                    ks.append(0.0)
            else:
                ks.append(0.0)
    return wavelengths, ns, ks


def _eval_formula_1(coefficients: list[float], lam_um: float) -> float:
    """Evaluate refractiveindex.info `formula 1` (Sellmeier-like).

    Per the database's formula spec:
        n²(λ) - 1 = c[0] + Σᵢ c[2i-1] λ² / (λ² - c[2i]²)
    Coefficients arrive as a list of floats. λ is in µm.
    """
    n2m1 = coefficients[0]
    i = 1
    while i + 1 < len(coefficients):
        b = coefficients[i]
        c = coefficients[i + 1]
        n2m1 += b * lam_um * lam_um / (lam_um * lam_um - c * c)
        i += 2
    return math.sqrt(1.0 + n2m1)


def _logspace(lo: float, hi: float, n: int) -> list[float]:
    """Log-spaced grid of `n` points in [lo, hi] inclusive."""
    if n < 2:
        return [lo]
    log_lo = math.log(lo)
    log_hi = math.log(hi)
    step = (log_hi - log_lo) / (n - 1)
    return [math.exp(log_lo + step * i) for i in range(n)]


def _parse_wavelength_range(s: str | list[float]) -> tuple[float, float]:
    """Parse `wavelength_range: 0.305 1.00` (string OR list — yaml.safe_load
    can land it either way depending on whether the source uses spaces
    or commas)."""
    if isinstance(s, list):
        return float(s[0]), float(s[1])
    parts = str(s).split()
    return float(parts[0]), float(parts[1])


def parse_dispersion_yaml(text: str) -> Dispersion:
    """Parse a refractiveindex.info YAML payload into a `Dispersion`.

    Raises ValueError if no DATA block recognisably contains n,k.
    """
    doc = yaml.safe_load(text)
    if not isinstance(doc, dict) or "DATA" not in doc:
        raise ValueError("YAML missing top-level DATA block")
    data_blocks = doc["DATA"]
    if not isinstance(data_blocks, list) or not data_blocks:
        raise ValueError("DATA block is not a non-empty list")

    references = str(doc.get("REFERENCES", "")).strip()
    doi = _extract_doi(references)

    # Walk the DATA blocks; the first one we recognise wins. Per the
    # database's spec, multiple blocks of differing types may appear
    # (e.g. n2 + nk2). For our purposes we want a single n[,k] sample
    # set, so we commit to the first usable block.
    for block in data_blocks:
        if not isinstance(block, dict):
            continue
        btype = str(block.get("type", "")).strip()
        if btype == "tabulated nk":
            wavs, ns, ks = _parse_tabulated(block.get("data", ""), has_k=True)
            if not wavs:
                continue
            return Dispersion(
                wavelengths_nm=wavs,
                n=ns,
                k=ks,
                type_label=btype,
                has_doi=doi is not None,
                references=references,
            )
        if btype in ("tabulated n", "tabulated k"):
            wavs, ns, _ = _parse_tabulated(block.get("data", ""), has_k=False)
            if not wavs:
                continue
            return Dispersion(
                wavelengths_nm=wavs,
                n=ns,
                k=None,
                type_label=btype,
                has_doi=doi is not None,
                references=references,
            )
        if btype.startswith("formula"):
            # We currently only handle formula 1 (Sellmeier). Other
            # formulas (Cauchy, polynomial variants) require their own
            # evaluators and aren't in this PR's scope — log + skip.
            if btype != "formula 1":
                continue
            coeffs = block.get("coefficients")
            wrange = block.get("wavelength_range")
            if coeffs is None or wrange is None:
                continue
            if isinstance(coeffs, str):
                coeffs = [float(x) for x in coeffs.split()]
            else:
                coeffs = [float(x) for x in coeffs]
            lo, hi = _parse_wavelength_range(wrange)
            grid = _logspace(lo, hi, SELLMEIER_GRID_POINTS)
            n_vals = [_eval_formula_1(coeffs, lam) for lam in grid]
            return Dispersion(
                wavelengths_nm=[lam * 1000.0 for lam in grid],
                n=n_vals,
                k=None,
                type_label=btype,
                has_doi=doi is not None,
                references=references,
            )
    raise ValueError(
        "No usable DATA block found (expected `tabulated nk` / `tabulated n` / `formula 1`)"
    )


# --------------------------------------------------------------------------- #
# Source row + writeback                                                      #
# --------------------------------------------------------------------------- #


def _today_iso() -> str:
    return _dt.date.today().isoformat()


def _make_source_row(
    *,
    citation_label: str,
    db_path: str,
    disp: Dispersion,
) -> dict[str, str]:
    """Build a `_sources` row for an `optical.refractive_index_dispersion` write."""
    note = (
        f"n,k tabulated {len(disp.wavelengths_nm)} rows, "
        f"{disp.wavelengths_nm[0]:.0f}-{disp.wavelengths_nm[-1]:.0f} nm, "
        f"fetched {_today_iso()}"
    )
    return build_source_row(
        citation=f"{citation_label} via refractiveindex.info",
        kind="doi" if disp.has_doi else "handbook",
        ref=f"refractiveindex.info:{db_path}",
        license="CC0",
        note=note,
    )


def _build_dispersion_inline(disp: Dispersion) -> Any:
    """Build the tomlkit value for an `optical.refractive_index_dispersion` field.

    Schema is `Optional[Dict[str, List[float]]]`, so we emit a TOML
    inline table holding the parallel arrays. tomlkit keeps the
    `wavelengths_nm` first by insertion order.
    """
    table = tomlkit.inline_table()
    table["wavelengths_nm"] = [round(w, 4) for w in disp.wavelengths_nm]
    table["n"] = [round(v, 6) for v in disp.n]
    if disp.k is not None:
        table["k"] = [round(v, 6) for v in disp.k]
    return table


# --------------------------------------------------------------------------- #
# Comparison                                                                  #
# --------------------------------------------------------------------------- #


@dataclass
class Row:
    key: str
    db_path: str
    citation_label: str
    type_label: str
    n_rows: int
    wmin_nm: float
    wmax_nm: float
    has_k: bool
    status: str  # "OK" / "MISSING" / "DIFF" / "SKIP" / "ERROR"
    note: str = ""


def _read_doc(toml_path: Path) -> tomlkit.TOMLDocument:
    return tomlkit.parse(toml_path.read_text(encoding="utf-8"))


def _walk(doc: Any, dotted: str) -> Any | None:
    node: Any = doc
    for seg in dotted.split("."):
        if not isinstance(node, dict) or seg not in node:
            return None
        node = node[seg]
    return node


def _ours_dispersion(mat: Any) -> dict[str, list[float]] | None:
    """Read `properties.optical.refractive_index_dispersion` if present."""
    if mat is None:
        return None
    props = getattr(mat, "properties", None)
    if props is None:
        return None
    optical = getattr(props, "optical", None)
    if optical is None:
        return None
    return getattr(optical, "refractive_index_dispersion", None)


def _fetch_one(db_path: str, *, dry_run: bool) -> Dispersion | None:
    """Fetch + parse a single refractiveindex.info entry.

    Returns None on 404 or YAML parse failure (logged via the caller's
    Row). When `dry_run` is True we still hit the cache (the offline
    flag is on the test side via monkey-patching `cached_get_text`); a
    cache miss in dry-run will still trigger a network call. That
    matches enrich_from_wikidata.py's semantics — `--dry-run` means "no
    writeback", not "no network".
    """
    url = _BASE_URL.format(path=db_path)
    try:
        return parse_dispersion_yaml(
            cached_get_text(url, source=SOURCE_NAME, suffix=".yaml", ttl_days=30)
        )
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return None
        raise
    except ValueError:
        return None


def _compare_one(
    *,
    material_key: str,
    db_path: str,
    citation_label: str,
    mats: dict,
    toml_path: Path,
    write: bool,
    dry_run: bool,
) -> Row:
    disp = _fetch_one(db_path, dry_run=dry_run)
    if disp is None:
        return Row(
            key=material_key,
            db_path=db_path,
            citation_label=citation_label,
            type_label="-",
            n_rows=0,
            wmin_nm=0.0,
            wmax_nm=0.0,
            has_k=False,
            status="ERROR",
            note="fetch/parse failed (see network log; entry may not be on main HEAD)",
        )

    row = Row(
        key=material_key,
        db_path=db_path,
        citation_label=citation_label,
        type_label=disp.type_label,
        n_rows=len(disp.wavelengths_nm),
        wmin_nm=disp.wavelengths_nm[0],
        wmax_nm=disp.wavelengths_nm[-1],
        has_k=disp.k is not None,
        status="OK",
    )

    ours = _ours_dispersion(mats.get(material_key))
    doc = _read_doc(toml_path)
    optical_node = _walk(doc, f"{material_key}.optical")
    on_disk = isinstance(optical_node, dict) and "refractive_index_dispersion" in optical_node

    if ours is not None or on_disk:
        # NEVER overwrite. Compute overlap of wavelength ranges for the
        # report so curators can spot egregious mismatches by eye.
        their_lo, their_hi = disp.wavelengths_nm[0], disp.wavelengths_nm[-1]
        if ours is not None and ours.get("wavelengths_nm"):
            our_lo = float(min(ours["wavelengths_nm"]))
            our_hi = float(max(ours["wavelengths_nm"]))
            row.status = "DIFF"
            row.note = (
                f"ours={our_lo:.0f}-{our_hi:.0f} nm  "
                f"theirs={their_lo:.0f}-{their_hi:.0f} nm — kept ours"
            )
        else:
            row.status = "DIFF"
            row.note = (
                f"on-disk dispersion present (no parsed wavelength_nm grid); "
                f"theirs={their_lo:.0f}-{their_hi:.0f} nm — kept ours"
            )
        return row

    row.status = "MISSING"
    if write:
        material_path = material_key.split(".") + ["optical"]
        src_row = _make_source_row(citation_label=citation_label, db_path=db_path, disp=disp)
        writeback(
            toml_path,
            material_path,
            {"refractive_index_dispersion": _build_dispersion_inline(disp)},
            sources={"refractive_index_dispersion": src_row},
        )
    return row


# --------------------------------------------------------------------------- #
# Report                                                                      #
# --------------------------------------------------------------------------- #


def _render_report(rows: list[Row], *, write: bool) -> str:
    lines: list[str] = []
    lines.append("# refractiveindex.info enrichment report")
    lines.append("")
    lines.append(f"Date: {_today_iso()}")
    lines.append(f"Mode: {'write (add-only)' if write else 'comparison-only'}")
    lines.append(f"Materials checked: {len(rows)}")
    ok = sum(1 for r in rows if r.status == "OK" or r.status == "MISSING")
    diffs = sum(1 for r in rows if r.status == "DIFF")
    errors = sum(1 for r in rows if r.status == "ERROR")
    lines.append(f"OK: {ok}  DIFF: {diffs}  ERROR: {errors}")
    lines.append("")

    header = ["material", "db_path", "type", "rows", "wmin_nm", "wmax_nm", "k?", "status"]
    lines.append(" | ".join(header))
    lines.append(" | ".join("---" for _ in header))
    for r in rows:
        cells = [
            r.key,
            r.db_path,
            r.type_label,
            str(r.n_rows),
            f"{r.wmin_nm:.0f}",
            f"{r.wmax_nm:.0f}",
            "yes" if r.has_k else "no",
            r.status,
        ]
        lines.append(" | ".join(cells))
    lines.append("")
    notes = [r for r in rows if r.note]
    if notes:
        lines.append("Notes:")
        for r in notes:
            action = "WROTE" if (write and r.status == "MISSING") else r.status
            lines.append(f"  {action}  {r.key}: {r.note}")
    lines.append("")
    lines.append(
        "refractiveindex.info data is licensed CC0 "
        "(https://github.com/polyanskiy/refractiveindex.info-database)."
    )
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Driver                                                                      #
# --------------------------------------------------------------------------- #


def compare(
    key_filter: str | None = None,
    *,
    dry_run: bool = False,
    write: bool = False,
    report_path: Path | None = None,
) -> int:
    mats = load_all()

    targets = list(ENTRY_MAP.items())
    if key_filter is not None:
        targets = [(k, v) for k, v in targets if k == key_filter]
    if not targets:
        print(f"No targets matched key={key_filter!r}", file=sys.stderr)
        return 1

    rows: list[Row] = []
    for material_key, (db_path, citation_label) in targets:
        category = CATEGORY_FOR[material_key]
        toml_path = DATA_DIR / f"{category}.toml"
        if not toml_path.exists():
            rows.append(
                Row(
                    key=material_key,
                    db_path=db_path,
                    citation_label=citation_label,
                    type_label="-",
                    n_rows=0,
                    wmin_nm=0.0,
                    wmax_nm=0.0,
                    has_k=False,
                    status="ERROR",
                    note=f"missing {toml_path}",
                )
            )
            continue
        rows.append(
            _compare_one(
                material_key=material_key,
                db_path=db_path,
                citation_label=citation_label,
                mats=mats,
                toml_path=toml_path,
                write=write,
                dry_run=dry_run,
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
    parser.add_argument("--key", help="Only enrich this material key")
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
            "Apply add-only writeback: when `optical.refractive_index_dispersion` "
            "is missing on the target material, write the parsed dispersion plus "
            "a `_sources` row. Existing dispersion data is NEVER overwritten."
        ),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Write the enrichment report to this path (default: stdout).",
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
