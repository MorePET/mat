"""Tests for `scripts/enrich_from_geant4_nist.py` — issue #167.

Mirrors the test layout of `test_wikidata_enrichment.py` (PR #198) so
the enricher CLIs stay interchangeable for curators. Covers:

* `--dry-run` (no-op for this offline-only enricher) produces the
  comparison report from the embedded G4 mirror.
* `--write` adds `mean_excitation_energy_eV` AND the paired `_sources`
  row when the field is missing on a `tmp_path` TOML copy.
* `--write` does NOT overwrite an existing `mean_excitation_energy_eV`,
  even if our value diverges from Geant4's.
* Round-trip preserves comments end-to-end via the enricher.
* The license allow-list now includes `Geant4-SL` (the new license value
  introduced in #167) — guarding against accidental removal.

Skip if `requests`/`tomlkit` aren't installed: those live in
`scripts/requirements-curation.txt` and aren't part of the runtime
install. See `tests/test_curation_helpers.py` for the same pattern.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from textwrap import dedent

import pytest

pytest.importorskip("requests")
pytest.importorskip("tomlkit")

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def enricher():
    """Re-import fresh per test so module-level state doesn't leak."""
    if "enrich_from_geant4_nist" in sys.modules:
        del sys.modules["enrich_from_geant4_nist"]
    return importlib.import_module("enrich_from_geant4_nist")


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _patch_data_dir(monkeypatch, enricher, tmp_path: Path) -> None:
    """Redirect both module-level DATA_DIR pointers to `tmp_path`."""
    import _curation

    monkeypatch.setattr(_curation, "DATA_DIR", tmp_path)
    monkeypatch.setattr(enricher, "DATA_DIR", tmp_path)


def _stub_load_all(enricher, monkeypatch, mats: dict) -> None:
    monkeypatch.setattr(enricher, "load_all", lambda: mats)


class _StubMaterial:
    """Minimal stand-in for `pymat.Material` — only the attribute path
    `mat.properties.<group>.<field>` matters to the enricher."""

    def __init__(
        self,
        mechanical: dict | None = None,
        nuclear: dict | None = None,
    ):
        self.properties = type(
            "P",
            (),
            {
                "mechanical": type("M", (), mechanical or {})(),
                "nuclear": type("N", (), nuclear or {})(),
            },
        )()


# --------------------------------------------------------------------------- #
# License allow-list integrity (Reviewer #2 ask: catch accidental removal)    #
# --------------------------------------------------------------------------- #


def test_license_allowlist_includes_geant4_sl():
    """The Geant4-SL license value is the controversial bit of #167; if a
    refactor accidentally drops it from the allow-list, every Geant4
    enrichment writeback would silently fail. This test is the canary."""
    import _curation
    from check_licenses import ALLOWED

    assert "Geant4-SL" in _curation.LICENSE_ALLOWLIST
    assert "Geant4-SL" in ALLOWED


# --------------------------------------------------------------------------- #
# --dry-run / report-only mode                                                #
# --------------------------------------------------------------------------- #


def test_dry_run_produces_expected_report(enricher, capsys):
    """`--dry-run` produces a report without any monkey-patching: the
    enricher is offline-only, so this also implicitly verifies no
    network call is made."""
    rc = enricher.compare(key_filter="bgo", dry_run=True)
    assert rc == 0

    out = capsys.readouterr().out
    assert "# Geant4 NIST enrichment report" in out
    assert "Geant4 version: v11.2.0" in out
    assert "Mode: comparison-only" in out
    # bgo cells reference G4_BGO and the mean_excitation_energy_eV column.
    assert "bgo" in out
    assert "G4_BGO" in out
    assert "mean_excitation_energy_eV" in out
    assert "density" in out


def test_skipped_materials_appear_in_report(enricher, capsys):
    """`labr3` exists in scintillators.toml but has no Geant4 NIST
    equivalent — it should appear in the SKIP list, not the comparison
    table."""
    rc = enricher.compare(key_filter=None, dry_run=True)
    assert rc == 0
    out = capsys.readouterr().out
    assert "labr3" in out
    assert "Skipped (no G4 NIST mirror)" in out


# --------------------------------------------------------------------------- #
# --write: add-only writeback                                                 #
# --------------------------------------------------------------------------- #


_SYNTHETIC_BGO_GAP = dedent(
    """\
    # top-of-file comment — must survive the round-trip
    [bgo]
    name = "BGO"
    formula = "Bi4Ge3O12"

    [bgo.mechanical]
    # density already curated; MEE is the gap.
    density_value = 7.13
    density_unit = "g/cm^3"

    [bgo.nuclear]
    # mean_excitation_energy_eV intentionally absent — Geant4 fills it.
    radiation_length = 1.12
    """
)


def test_write_adds_missing_mee_and_sources_row(enricher, monkeypatch, tmp_path):
    """`--write`: missing `mean_excitation_energy_eV` + G4 has a value
    → write both the bare scalar and a `_sources` row keyed
    `nuclear.mean_excitation_energy_eV`."""
    toml_path = tmp_path / "scintillators.toml"
    toml_path.write_text(_SYNTHETIC_BGO_GAP)

    _patch_data_dir(monkeypatch, enricher, tmp_path)
    # Stub: density is set, MEE is None — only the writeback gap.
    _stub_load_all(
        enricher,
        monkeypatch,
        {
            "bgo": _StubMaterial(
                mechanical={"density": 7.13},
                nuclear={"mean_excitation_energy_eV": None},
            )
        },
    )

    rc = enricher.compare(key_filter="bgo", dry_run=True, write=True)
    assert rc == 0

    out = toml_path.read_text()
    # Bare scalar (no _value/_unit suffix) — schema convention for
    # mean_excitation_energy_eV (unit baked into the field name).
    assert "mean_excitation_energy_eV = 534.1" in out
    # _sources row attached at the material level.
    assert "[bgo._sources]" in out
    assert "nuclear.mean_excitation_energy_eV" in out
    assert "Geant4-SL" in out
    assert "G4NistMaterialBuilder.cc:920" in out
    assert "v11.2.0" in out
    # Top-of-file comment survives.
    assert "# top-of-file comment" in out


def test_write_does_not_overwrite_existing_mee(enricher, monkeypatch, tmp_path):
    """`--write`: existing MEE diverges from Geant4 → DIFF reported, no write."""
    src = dedent(
        """\
        [bgo]
        name = "BGO"

        [bgo.mechanical]
        density_value = 7.13
        density_unit = "g/cm^3"

        [bgo.nuclear]
        # Wrong on purpose — must not be silently corrected.
        mean_excitation_energy_eV = 999.9
        """
    )
    toml_path = tmp_path / "scintillators.toml"
    toml_path.write_text(src)

    _patch_data_dir(monkeypatch, enricher, tmp_path)
    _stub_load_all(
        enricher,
        monkeypatch,
        {
            "bgo": _StubMaterial(
                mechanical={"density": 7.13},
                nuclear={"mean_excitation_energy_eV": 999.9},
            )
        },
    )

    rc = enricher.compare(key_filter="bgo", dry_run=True, write=True)
    assert rc == 0

    after = toml_path.read_text()
    # The divergent value is exactly what the curator wrote.
    assert "mean_excitation_energy_eV = 999.9" in after
    assert "534.1" not in after
    # No _sources row attached — silent updates are forbidden, even with
    # provenance attached.
    assert "nuclear.mean_excitation_energy_eV" not in after


def test_write_round_trip_preserves_grade_level_comments(enricher, monkeypatch, tmp_path):
    """Comments at family + grade level survive a `--write` pass through
    a dotted material key (`plastic_scint.BC400`)."""
    src = dedent(
        """\
        # category-level comment
        [plastic_scint]
        name = "Plastic Scintillator"

        [plastic_scint.BC400]
        # grade-level comment — survival flag for tomlkit round-trips
        name = "BC-400 Plastic Scintillator"
        vendor = "eljen"

        [plastic_scint.BC400.optical]
        light_yield = 12000
        """
    )
    toml_path = tmp_path / "scintillators.toml"
    toml_path.write_text(src)

    _patch_data_dir(monkeypatch, enricher, tmp_path)
    _stub_load_all(
        enricher,
        monkeypatch,
        {
            "plastic_scint.BC400": _StubMaterial(
                mechanical={"density": None},
                nuclear={"mean_excitation_energy_eV": None},
            )
        },
    )

    rc = enricher.compare(key_filter="plastic_scint.BC400", dry_run=True, write=True)
    assert rc == 0

    out = toml_path.read_text()
    assert "# category-level comment" in out
    assert "# grade-level comment" in out
    # New _sources block lives at the grade level, not the family.
    assert "[plastic_scint.BC400._sources]" in out
    # Both the missing density and MEE got filled.
    assert "density_value = 1.032" in out
    assert "mean_excitation_energy_eV = 64.7" in out


# --------------------------------------------------------------------------- #
# Comparison-only mode never mutates files                                    #
# --------------------------------------------------------------------------- #


def test_comparison_only_never_writes(enricher, monkeypatch, tmp_path):
    toml_path = tmp_path / "scintillators.toml"
    toml_path.write_text(_SYNTHETIC_BGO_GAP)
    before = toml_path.read_text()

    _patch_data_dir(monkeypatch, enricher, tmp_path)
    _stub_load_all(
        enricher,
        monkeypatch,
        {
            "bgo": _StubMaterial(
                mechanical={"density": 7.13},
                nuclear={"mean_excitation_energy_eV": None},
            )
        },
    )

    rc = enricher.compare(key_filter="bgo", dry_run=True, write=False)
    assert rc == 0
    assert toml_path.read_text() == before


# --------------------------------------------------------------------------- #
# --report writes to a markdown file                                          #
# --------------------------------------------------------------------------- #


def test_report_writes_markdown_file(enricher, tmp_path, capsys):
    out_path = tmp_path / "g4-report.md"
    rc = enricher.compare(key_filter="bgo", dry_run=True, report_path=out_path)
    assert rc == 0
    assert out_path.exists()
    content = out_path.read_text()
    assert "# Geant4 NIST enrichment report" in content
    assert "G4_BGO" in content
    # When --report is set, stdout stays quiet.
    captured = capsys.readouterr()
    assert "# Geant4 NIST enrichment report" not in captured.out


# --------------------------------------------------------------------------- #
# Source-row sanity                                                           #
# --------------------------------------------------------------------------- #


def test_source_row_is_well_formed(enricher):
    """The `_sources` row built by the enricher must satisfy the curation
    helper's schema (kind in allow-list, license in allow-list, non-empty
    citation/ref)."""
    entry = enricher.G4_NIST["bgo"]
    row = enricher._make_source_row(entry, "mean_excitation_energy_eV")
    assert row["kind"] == "handbook"
    assert row["license"] == "Geant4-SL"
    assert "Geant4 G4NistMaterialBuilder" in row["citation"]
    assert "G4NistMaterialBuilder.cc:920" in row["ref"]
    assert "v11.2.0" in row["citation"]
    assert "G4_BGO" in row["note"]


def test_pwo_has_no_writable_mee(enricher):
    """G4_PbWO4 carries `pot=0.0` upstream (compute-from-composition
    sentinel). The mirror represents that as `mee_eV=None`, so the
    enricher must not attempt to write a MEE for `pwo` even if the
    field is missing in our TOML."""
    entry = enricher.G4_NIST["pwo"]
    assert entry.mee_eV is None
