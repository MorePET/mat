"""Tests for `scripts/enrich_from_pubchem.py` — issue #165.

Mirrors the test layout of `test_nist_webbook_enrichment.py` (PR #203)
and `test_refractiveindex_enrichment.py` (PR #201) so the enricher CLIs
stay interchangeable for curators. Covers:

* PubChem PUG-View / PUG-REST JSON parsers on a captured fixture
  (`tests/fixtures/pubchem_water.json` — the four bundled responses
  for CID 962, captured 2026-05-07).
* `--dry-run` produces the comparison report without mutating files
  and without hitting the network (the `cached_get` shim is
  monkey-patched to dispatch from the fixture).
* `--write` adds missing fields + the paired `_sources` row.
* `--write` does NOT overwrite an existing value, even if PubChem
  diverges. Comments survive the round-trip.
* Density writeback is gated by `density_writeback` on the entry —
  gas entries never write density even when the field is missing.
* Unit conversions are exercised: PubChem MP/BP arrive in °C, and the
  source note converts °C → K so a curator reading the TOML sees the
  conventional Kelvin number.

Skip if `requests`/`tomlkit` aren't installed: those live in
`scripts/requirements-curation.txt` and aren't part of the runtime
install.
"""

from __future__ import annotations

import importlib
import json
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
WATER_FIXTURE = FIXTURE_DIR / "pubchem_water.json"


@pytest.fixture
def enricher():
    """Re-import fresh per test so module-level state doesn't leak."""
    if "enrich_from_pubchem" in sys.modules:
        del sys.modules["enrich_from_pubchem"]
    return importlib.import_module("enrich_from_pubchem")


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _load_fixture() -> dict:
    return json.loads(WATER_FIXTURE.read_text(encoding="utf-8"))


def _patch_data_dir(monkeypatch, enricher, tmp_path: Path) -> None:
    """Redirect both module-level DATA_DIR pointers to `tmp_path`."""
    import _curation

    monkeypatch.setattr(_curation, "DATA_DIR", tmp_path)
    monkeypatch.setattr(enricher, "DATA_DIR", tmp_path)


def _stub_load_all(enricher, monkeypatch, mats: dict) -> None:
    monkeypatch.setattr(enricher, "load_all", lambda: mats)


def _stub_fetch_with_fixture(enricher, monkeypatch) -> None:
    """Replace `cached_get` so each PubChem URL/heading returns the fixture.

    The fixture bundles the four responses that `fetch_compound(962)`
    makes (property + Density + MeltingPoint + BoilingPoint). The stub
    dispatches by `params['heading']` for the PUG-View calls and falls
    back to the property table for the PUG-REST call. Tests targeting
    other CIDs would set up their own stub.
    """
    bundle = _load_fixture()

    def fake(url, params=None, **kwargs):  # noqa: ARG001
        params = params or {}
        heading = params.get("heading")
        if heading == "Density":
            return bundle["density"]
        if heading == "Melting Point":
            return bundle["melting"]
        if heading == "Boiling Point":
            return bundle["boiling"]
        # No heading → the property endpoint.
        return bundle["property"]

    monkeypatch.setattr(enricher, "cached_get", fake)


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
    """`PD-USGov` is the license tag for every PubChem source row;
    if a refactor accidentally drops it from the allow-list, every
    writeback would silently fail. This test is the canary."""
    import _curation
    from check_licenses import ALLOWED

    assert "PD-USGov" in _curation.LICENSE_ALLOWLIST
    assert "PD-USGov" in ALLOWED


# --------------------------------------------------------------------------- #
# CID map sanity                                                              #
# --------------------------------------------------------------------------- #


def test_entry_map_only_targets_known_materials(enricher):
    """Every entry's `material_key` must exist in the corresponding
    category — guards against typos like `co2` vs `carbon_dioxide`."""
    from pymat import _CATEGORY_BASES

    for key, entry in enricher.ENTRY_MAP.items():
        assert entry.category in _CATEGORY_BASES, f"unknown category for {key}"
        bases = _CATEGORY_BASES[entry.category]
        # `material_key` is dotted; check just the head exists.
        head = entry.material_key.split(".")[0]
        assert head in bases, (
            f"ENTRY_MAP[{key!r}].material_key={entry.material_key!r} "
            f"head {head!r} not in {entry.category}: {bases}"
        )


def test_density_writeback_gated_for_gases(enricher):
    """Gas entries must NEVER auto-write density: PubChem reports density
    at the cryogenic / liquid reference state, not at our STP."""
    for key, entry in enricher.ENTRY_MAP.items():
        if entry.category == "gases":
            assert not entry.density_writeback, (
                f"ENTRY_MAP[{key!r}] is a gas but density_writeback=True — "
                "PubChem density is the wrong reference state for gases."
            )


# --------------------------------------------------------------------------- #
# Parsers                                                                     #
# --------------------------------------------------------------------------- #


def test_parse_temperature_C_picks_first_clean_celsius(enricher):
    # Real PubChem strings — the °F line comes first; our parser must
    # walk past it to find the °C duplicate that PubChem reliably ships.
    strings = ["32 °F", "0 °C", "0 °C"]
    assert enricher._parse_temperature_C(strings) == pytest.approx(0.0)


def test_parse_temperature_C_accepts_negative(enricher):
    strings = ["-354 °F (USCG, 1999)", "-210.01 °C (63.14K)", "-210 °C"]
    assert enricher._parse_temperature_C(strings) == pytest.approx(-210.01)


def test_parse_temperature_C_skips_table_refs(enricher):
    strings = ["Chemical and physical properties[Table#8152]", "0 °C"]
    assert enricher._parse_temperature_C(strings) == pytest.approx(0.0)


def test_parse_temperature_C_returns_none_when_only_F(enricher):
    strings = ["212 °F at 760 mmHg"]
    assert enricher._parse_temperature_C(strings) is None


def test_parse_density_g_per_cm3_clean_string(enricher):
    strings = ["1", "0.9950 g/cu cm at 25 °C", "Chemical and physical properties[Table#8152]"]
    assert enricher._parse_density_g_per_cm3(strings) == pytest.approx(0.9950)


def test_parse_density_g_per_cm3_alternate_unit_spelling(enricher):
    strings = ["density: 1.000000 g/cm3 at 4 °C"]
    assert enricher._parse_density_g_per_cm3(strings) == pytest.approx(1.0)


def test_parse_density_g_per_cm3_rejects_g_per_L(enricher):
    """`g/L` (gas density) should NOT be silently treated as `g/cm³`."""
    strings = ["1.251 g/L at 0 °C and 1 atm"]
    assert enricher._parse_density_g_per_cm3(strings) is None


def test_parse_density_g_per_cm3_rejects_kg_per_L(enricher):
    strings = ["Density (at the boiling point of the liquid): 0.808 kg/l"]
    assert enricher._parse_density_g_per_cm3(strings) is None


def test_parse_density_g_per_cm3_rejects_prose(enricher):
    strings = [
        "Less dense than water; will float",
        "VAPOR DENSITY @ NORMAL TEMP APPROX SAME AS AIR",
    ]
    assert enricher._parse_density_g_per_cm3(strings) is None


def test_parse_molecular_weight_extracts_title_and_mw(enricher):
    bundle = _load_fixture()
    title, formula, mw = enricher._parse_molecular_weight(bundle["property"])
    assert title == "Water"
    assert formula == "H2O"
    assert mw == pytest.approx(18.015)


def test_parse_molecular_weight_handles_missing(enricher):
    title, formula, mw = enricher._parse_molecular_weight({"PropertyTable": {"Properties": []}})
    assert title is None and formula is None and mw is None


# --------------------------------------------------------------------------- #
# fetch_compound                                                              #
# --------------------------------------------------------------------------- #


def test_fetch_compound_assembles_record_from_fixture(enricher, monkeypatch):
    _stub_fetch_with_fixture(enricher, monkeypatch)
    rec = enricher.fetch_compound(962)
    assert rec.cid == 962
    assert rec.title == "Water"
    assert rec.molecular_formula == "H2O"
    assert rec.molecular_weight_g_mol == pytest.approx(18.015)
    assert rec.density_g_per_cm3 == pytest.approx(0.9950)
    assert rec.melting_point_C == pytest.approx(0.0)
    assert rec.boiling_point_C == pytest.approx(99.974)


# --------------------------------------------------------------------------- #
# --dry-run / report-only mode                                                #
# --------------------------------------------------------------------------- #


def test_dry_run_produces_report_offline(enricher, monkeypatch, capsys, tmp_path):
    """`--dry-run` against the fixture: no network, report rendered."""
    _stub_fetch_with_fixture(enricher, monkeypatch)
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
            melting_point_value = 0
            melting_point_unit = "degC"
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
                thermal={"melting_point": 0},
            )
        },
    )

    rc = enricher.compare(key_filter="water", dry_run=True)
    assert rc == 0

    out = capsys.readouterr().out
    assert "# PubChem (PUG-REST / PUG-View) enrichment report" in out
    assert "Mode: comparison-only" in out
    assert "water" in out
    assert "962" in out  # CID
    assert "density" in out and "melting_point" in out
    assert "molecular_weight_g_mol" in out  # surfaced even though schema-gap
    assert "boiling_point_K" in out
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
    # density already curated; melting_point block is the gap.
    density_value = 0.998
    density_unit = "g/cm^3"

    [water.thermal]
    # melting_point intentionally absent — this is the writeback target.
    """
)


def test_write_adds_missing_melting_point_and_sources_row(enricher, monkeypatch, tmp_path):
    """`--write`: missing thermal.melting_point + PubChem has a value →
    writes the `_value`/`_unit` pair and a `_sources` row keyed
    `thermal.melting_point`."""
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
                thermal={"melting_point": None},
            )
        },
    )

    rc = enricher.compare(key_filter="water", dry_run=True, write=True)
    assert rc == 0

    out = toml_path.read_text()
    # PubChem MP for water = 0 °C, written into degC field.
    assert "melting_point_value = 0" in out
    assert 'melting_point_unit = "degC"' in out
    # _sources row attached at the material level, keyed by group.field.
    assert "[water._sources]" in out
    assert "thermal.melting_point" in out
    assert "PD-USGov" in out
    assert "PubChem CID 962" in out
    assert "Water" in out
    # The note converts °C → K for the Kelvin-conventional summary.
    assert "MP=273.1 K" in out or "MP=273.2 K" in out
    assert "BP=373.1 K" in out or "BP=373.1 K" in out  # 99.974 °C → 373.124 K
    # Top-of-file comment survives.
    assert "# top-of-file comment" in out


def test_write_does_not_overwrite_existing_value(enricher, monkeypatch, tmp_path):
    """`--write`: existing density diverges from PubChem → DIFF reported, no write."""
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
        melting_point_value = 0
        melting_point_unit = "degC"
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
                thermal={"melting_point": 0},
            )
        },
    )

    rc = enricher.compare(key_filter="water", dry_run=True, write=True)
    assert rc == 0

    after = toml_path.read_text()
    # The divergent value is exactly what the curator wrote.
    assert "density_value = 1.234" in after
    # The PubChem density (0.9950) is NOT silently injected.
    assert "0.995" not in after
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
                thermal={"melting_point": None},
            )
        },
    )

    rc = enricher.compare(key_filter="water", dry_run=True, write=False)
    assert rc == 0
    assert toml_path.read_text() == before


# --------------------------------------------------------------------------- #
# Density-writeback gating                                                    #
# --------------------------------------------------------------------------- #


def test_density_not_written_for_gas_entry(enricher, monkeypatch, tmp_path):
    """Even if a gas's density field is missing AND PubChem has a value,
    the writeback must SKIP — gases sit at our STP reference state and
    PubChem mostly reports the cryogenic-liquid density. Use a synthetic
    `nitrogen` entry that re-uses the water fixture (we only care about
    the density-skipping codepath here)."""
    _stub_fetch_with_fixture(enricher, monkeypatch)

    # Override ENTRY_MAP so this test doesn't depend on which gases ship.
    monkeypatch.setattr(
        enricher,
        "ENTRY_MAP",
        {
            "nitrogen": enricher.CompoundEntry(
                cid=962,  # reuse fixture; CID identity isn't the point here
                material_key="nitrogen",
                category="gases",
                density_writeback=False,
            )
        },
    )

    toml_path = tmp_path / "gases.toml"
    toml_path.write_text(
        dedent(
            """\
            [nitrogen]
            name = "Nitrogen"

            [nitrogen.mechanical]
            # density intentionally absent.

            [nitrogen.thermal]
            # melting_point intentionally absent — this WILL be written.
            """
        )
    )
    _patch_data_dir(monkeypatch, enricher, tmp_path)
    _stub_load_all(
        enricher,
        monkeypatch,
        {
            "nitrogen": _StubMaterial(
                mechanical={"density": None},
                thermal={"melting_point": None},
            )
        },
    )

    rc = enricher.compare(key_filter="nitrogen", dry_run=True, write=True)
    assert rc == 0

    out = toml_path.read_text()
    # Density was NOT written despite being missing — gating worked.
    assert "density_value" not in out
    assert "mechanical.density" not in out  # no _sources row either
    # Melting point WAS written — gating only affects density.
    assert "melting_point_value = 0" in out
    assert "thermal.melting_point" in out


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
                thermal={"melting_point": None},
            )
        },
    )

    out_path = tmp_path / "pubchem-report.md"
    rc = enricher.compare(key_filter="water", dry_run=True, report_path=out_path)
    assert rc == 0
    assert out_path.exists()
    content = out_path.read_text()
    assert "# PubChem (PUG-REST / PUG-View) enrichment report" in content
    assert "962" in content
    # When --report is set, stdout stays quiet (file path printed to stderr).
    captured = capsys.readouterr()
    assert "# PubChem" not in captured.out


# --------------------------------------------------------------------------- #
# Source-row sanity                                                           #
# --------------------------------------------------------------------------- #


def test_source_row_is_well_formed(enricher, monkeypatch):
    """The `_sources` row built by the enricher must satisfy the curation
    helper's schema (kind in allow-list, license in allow-list, non-empty
    citation/ref) and carry the K-converted MP/BP for traceability."""
    _stub_fetch_with_fixture(enricher, monkeypatch)
    record = enricher.fetch_compound(962)
    entry = enricher.ENTRY_MAP["water"]
    src = enricher._make_source_row(entry, record)
    assert src["kind"] == "handbook"
    assert src["license"] == "PD-USGov"
    assert "PubChem CID 962" in src["citation"]
    assert "Water" in src["citation"]
    assert "pubchem.ncbi.nlm.nih.gov/compound/962" in src["ref"]
    # MW + MP-in-K + BP-in-K all fold into the note.
    assert "MW=18.015 g/mol" in src["note"]
    assert "MP=273.1 K" in src["note"] or "MP=273.2 K" in src["note"]
    # BP = 99.974 + 273.15 = 373.124 → ".4g" format → "373.1"
    assert "BP=373.1 K" in src["note"]


def test_source_row_handles_no_scalars(enricher):
    """If PubChem returns nothing parseable, the note still renders
    rather than crashing — `no scalars parsed` is a curator-friendly
    placeholder."""
    rec = enricher.PubChemRecord(
        cid=999,
        title="NoData",
        molecular_formula=None,
        molecular_weight_g_mol=None,
        density_g_per_cm3=None,
        melting_point_C=None,
        boiling_point_C=None,
    )
    entry = enricher.CompoundEntry(
        cid=999, material_key="x", category="liquids", density_writeback=True
    )
    src = enricher._make_source_row(entry, rec)
    assert "no scalars parsed" in src["note"]
    assert src["license"] == "PD-USGov"
