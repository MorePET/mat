"""Tests for `scripts/enrich_from_nist_webbook.py` — issue #159.

Mirrors the test layout of `test_geant4_enrichment.py` (PR #200) and
`test_refractiveindex_enrichment.py` (PR #201) so the enricher CLIs
stay interchangeable for curators. Covers:

* TSV parsing on a small captured fixture (`tests/fixtures/nist_webbook_water.txt`)
* `--dry-run` produces the comparison report without mutating files
  and without hitting the network (the `cached_get_text` shim is
  monkey-patched to return the fixture).
* `--write` adds missing fields + the paired `_sources` row.
* `--write` does NOT overwrite an existing value, even if NIST diverges.
* Round-trip preserves comments end-to-end.
* The license allow-list still includes `PD-USGov` — guarding against
  accidental removal that would silently break this enricher.

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

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
WATER_FIXTURE = FIXTURE_DIR / "nist_webbook_water.txt"


@pytest.fixture
def enricher():
    """Re-import fresh per test so module-level state doesn't leak."""
    if "enrich_from_nist_webbook" in sys.modules:
        del sys.modules["enrich_from_nist_webbook"]
    return importlib.import_module("enrich_from_nist_webbook")


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


def _stub_fetch_with_fixture(enricher, monkeypatch) -> None:
    """Replace `cached_get_text` so every call returns the water fixture.

    The fixture spans 293.15 K and 298.15 K at 1.0132 bar — enough to
    answer queries for `water` (293.15 K) without a network round-trip.
    Tests that target other fluids set up their own stub.
    """
    fixture_text = WATER_FIXTURE.read_text(encoding="utf-8")

    def fake(url, params=None, **kwargs):  # noqa: ARG001
        return fixture_text

    monkeypatch.setattr(enricher, "cached_get_text", fake)


class _StubMaterial:
    """Minimal stand-in for `pymat.Material` — only the attribute path
    `mat.properties.<group>.<field>` matters to the enricher."""

    def __init__(
        self,
        mechanical: dict | None = None,
        thermal: dict | None = None,
    ):
        self.properties = type(
            "P",
            (),
            {
                "mechanical": type("M", (), mechanical or {})(),
                "thermal": type("T", (), thermal or {})(),
            },
        )()


# --------------------------------------------------------------------------- #
# License allow-list integrity                                                #
# --------------------------------------------------------------------------- #


def test_license_allowlist_includes_pd_usgov():
    """`PD-USGov` is the license tag for every NIST WebBook source row;
    if a refactor accidentally drops it from the allow-list, every
    writeback would silently fail. This test is the canary."""
    import _curation
    from check_licenses import ALLOWED

    assert "PD-USGov" in _curation.LICENSE_ALLOWLIST
    assert "PD-USGov" in ALLOWED


# --------------------------------------------------------------------------- #
# TSV parsing                                                                 #
# --------------------------------------------------------------------------- #


def test_parse_isobar_tsv_extracts_two_rows(enricher):
    rows = enricher.parse_isobar_tsv(WATER_FIXTURE.read_text(encoding="utf-8"))
    assert len(rows) == 2
    assert rows[0].t_kelvin == pytest.approx(293.15)
    assert rows[1].t_kelvin == pytest.approx(298.15)
    # Density in kg/m³, Cp in J/(g·K), Therm. Cond. in W/(m·K).
    assert rows[0].header_to_value["Density (kg/m3)"] == pytest.approx(998.21)
    assert rows[0].header_to_value["Cp (J/g*K)"] == pytest.approx(4.1841)
    assert rows[0].header_to_value["Therm. Cond. (W/m*K)"] == pytest.approx(0.59801)
    assert rows[0].phase == "liquid"


def test_parse_rejects_non_tsv(enricher):
    with pytest.raises(ValueError, match="not look like a WebBook"):
        enricher.parse_isobar_tsv("<html>Range Error</html>")


def test_select_row_picks_target_temperature(enricher):
    rows = enricher.parse_isobar_tsv(WATER_FIXTURE.read_text(encoding="utf-8"))
    selected = enricher._select_row(rows, 293.15)
    assert selected.t_kelvin == pytest.approx(293.15)


def test_select_row_raises_when_target_missing(enricher):
    rows = enricher.parse_isobar_tsv(WATER_FIXTURE.read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match="no row at T=350"):
        enricher._select_row(rows, 350.0)


# --------------------------------------------------------------------------- #
# --dry-run / report-only mode                                                #
# --------------------------------------------------------------------------- #


def test_dry_run_produces_report_offline(enricher, monkeypatch, capsys, tmp_path):
    """`--dry-run` against the fixture: no network, report rendered."""
    _stub_fetch_with_fixture(enricher, monkeypatch)
    # We need a `liquids.toml` to walk; copy a minimal one into tmp_path.
    toml_path = tmp_path / "liquids.toml"
    toml_path.write_text(
        dedent(
            """\
            [water]
            name = "Water"
            formula = "H2O"

            [water.mechanical]
            density_value = 0.998
            density_unit = "g/cm^3"

            [water.thermal]
            thermal_conductivity_value = 0.598
            thermal_conductivity_unit = "W/(m*K)"
            specific_heat_value = 4182
            specific_heat_unit = "J/(kg*K)"
            """
        )
    )
    _patch_data_dir(monkeypatch, enricher, tmp_path)
    _stub_load_all(
        enricher,
        monkeypatch,
        {
            "water": _StubMaterial(
                mechanical={"density": 0.998},
                thermal={
                    "thermal_conductivity": 0.598,
                    "specific_heat": 4182,
                },
            )
        },
    )

    rc = enricher.compare(key_filter="water", dry_run=True)
    assert rc == 0

    out = capsys.readouterr().out
    assert "# NIST Chemistry WebBook (SRD 69) enrichment report" in out
    assert "Mode: comparison-only" in out
    assert "water" in out
    assert "C7732185" in out
    assert "density" in out and "specific_heat" in out and "thermal_conductivity" in out
    # AS-IS notice in the report footer.
    assert "AS IS" in out
    assert "PD-USGov" in out

    # The TOML was not mutated.
    assert "_sources" not in toml_path.read_text()


# --------------------------------------------------------------------------- #
# --write: add-only writeback                                                 #
# --------------------------------------------------------------------------- #


_SYNTHETIC_WATER_GAP = dedent(
    """\
    # top-of-file comment — must survive the round-trip
    [water]
    name = "Water"
    formula = "H2O"

    [water.mechanical]
    # density already curated; thermal block is the gap.
    density_value = 0.998
    density_unit = "g/cm^3"

    [water.thermal]
    # thermal_conductivity + specific_heat intentionally absent.
    """
)


def test_write_adds_missing_fields_and_sources_row(enricher, monkeypatch, tmp_path):
    """`--write`: missing thermal fields + NIST has values → write both
    the `_value`/`_unit` pair and a `_sources` row keyed
    `thermal.<field>`."""
    _stub_fetch_with_fixture(enricher, monkeypatch)
    toml_path = tmp_path / "liquids.toml"
    toml_path.write_text(_SYNTHETIC_WATER_GAP)

    _patch_data_dir(monkeypatch, enricher, tmp_path)
    # Stub: density set, thermal fields None — only the writeback gap.
    _stub_load_all(
        enricher,
        monkeypatch,
        {
            "water": _StubMaterial(
                mechanical={"density": 0.998},
                thermal={"thermal_conductivity": None, "specific_heat": None},
            )
        },
    )

    rc = enricher.compare(key_filter="water", dry_run=True, write=True)
    assert rc == 0

    out = toml_path.read_text()
    # NIST water at 293.15 K, 1.0132 bar:
    #   Cp = 4.1841 J/(g·K) → 4184.1 J/(kg·K)
    #   Therm. Cond. = 0.59801 W/(m·K)
    assert "specific_heat_value = 4184.1" in out
    assert 'specific_heat_unit = "J/(kg*K)"' in out
    assert "thermal_conductivity_value = 0.59801" in out
    assert 'thermal_conductivity_unit = "W/(m*K)"' in out
    # _sources rows attached at the material level, keyed by group.field.
    assert "[water._sources]" in out
    assert "thermal.specific_heat" in out
    assert "thermal.thermal_conductivity" in out
    assert "PD-USGov" in out
    assert "C7732185" in out
    assert "Lemmon REFPROP" in out
    # Top-of-file comment survives.
    assert "# top-of-file comment" in out


def test_write_does_not_overwrite_existing_value(enricher, monkeypatch, tmp_path):
    """`--write`: existing density diverges from NIST → DIFF reported, no write."""
    _stub_fetch_with_fixture(enricher, monkeypatch)
    src = dedent(
        """\
        [water]
        name = "Water"

        [water.mechanical]
        # Wrong on purpose — must not be silently corrected.
        density_value = 1.234
        density_unit = "g/cm^3"

        [water.thermal]
        thermal_conductivity_value = 0.598
        thermal_conductivity_unit = "W/(m*K)"
        specific_heat_value = 4182
        specific_heat_unit = "J/(kg*K)"
        """
    )
    toml_path = tmp_path / "liquids.toml"
    toml_path.write_text(src)

    _patch_data_dir(monkeypatch, enricher, tmp_path)
    _stub_load_all(
        enricher,
        monkeypatch,
        {
            "water": _StubMaterial(
                mechanical={"density": 1.234},
                thermal={
                    "thermal_conductivity": 0.598,
                    "specific_heat": 4182,
                },
            )
        },
    )

    rc = enricher.compare(key_filter="water", dry_run=True, write=True)
    assert rc == 0

    after = toml_path.read_text()
    # The divergent value is exactly what the curator wrote.
    assert "density_value = 1.234" in after
    # The NIST value (0.99821 g/cm³) is NOT in the file.
    assert "0.99821" not in after
    # No _sources row attached for density — silent updates are forbidden.
    assert "mechanical.density" not in after


def test_comparison_only_never_writes(enricher, monkeypatch, tmp_path):
    _stub_fetch_with_fixture(enricher, monkeypatch)
    toml_path = tmp_path / "liquids.toml"
    toml_path.write_text(_SYNTHETIC_WATER_GAP)
    before = toml_path.read_text()

    _patch_data_dir(monkeypatch, enricher, tmp_path)
    _stub_load_all(
        enricher,
        monkeypatch,
        {
            "water": _StubMaterial(
                mechanical={"density": 0.998},
                thermal={"thermal_conductivity": None, "specific_heat": None},
            )
        },
    )

    rc = enricher.compare(key_filter="water", dry_run=True, write=False)
    assert rc == 0
    assert toml_path.read_text() == before


# --------------------------------------------------------------------------- #
# --report writes to a markdown file                                          #
# --------------------------------------------------------------------------- #


def test_report_writes_markdown_file(enricher, monkeypatch, tmp_path, capsys):
    _stub_fetch_with_fixture(enricher, monkeypatch)
    toml_path = tmp_path / "liquids.toml"
    toml_path.write_text(_SYNTHETIC_WATER_GAP)
    _patch_data_dir(monkeypatch, enricher, tmp_path)
    _stub_load_all(
        enricher,
        monkeypatch,
        {
            "water": _StubMaterial(
                mechanical={"density": 0.998},
                thermal={"thermal_conductivity": None, "specific_heat": None},
            )
        },
    )

    out_path = tmp_path / "nist-report.md"
    rc = enricher.compare(key_filter="water", dry_run=True, report_path=out_path)
    assert rc == 0
    assert out_path.exists()
    content = out_path.read_text()
    assert "# NIST Chemistry WebBook (SRD 69) enrichment report" in content
    assert "C7732185" in content
    # When --report is set, stdout stays quiet.
    captured = capsys.readouterr()
    assert "# NIST Chemistry WebBook" not in captured.out


# --------------------------------------------------------------------------- #
# Source-row sanity                                                           #
# --------------------------------------------------------------------------- #


def test_source_row_is_well_formed(enricher):
    """The `_sources` row built by the enricher must satisfy the curation
    helper's schema (kind in allow-list, license in allow-list, non-empty
    citation/ref)."""
    entry = enricher.ENTRY_MAP["water"]
    row = enricher.parse_isobar_tsv(WATER_FIXTURE.read_text(encoding="utf-8"))[0]
    src = enricher._make_source_row(entry, "specific_heat", row)
    assert src["kind"] == "handbook"
    assert src["license"] == "PD-USGov"
    assert "NIST Chemistry WebBook SRD 69" in src["citation"]
    assert "Water" in src["citation"]
    assert "C7732185" in src["ref"]
    assert "T=293.15 K" in src["note"]
    assert "P=1.0132 bar" in src["note"]
    assert "Lemmon REFPROP" in src["note"]
