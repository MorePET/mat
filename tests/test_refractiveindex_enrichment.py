"""Tests for `scripts/enrich_from_refractiveindex.py` — issue #164.

Mirrors the layout of `test_geant4_enrichment.py` (PR #200) so the
enricher CLIs remain interchangeable for curators. Covers:

* YAML parser converts µm → nm (×1000) and survives a real-shape
  fixture file with `tabulated nk` data + a DOI in REFERENCES.
* Sellmeier `formula 1` blocks are evaluated on a wavelength grid; the
  Sellmeier path is exercised separately so a future formula change
  doesn't slip past the tabulated test.
* `--dry-run` against a stubbed fetch produces an expected report.
* `--write` adds the `optical.refractive_index_dispersion` field AND a
  paired `_sources` row when missing on a tmp-path TOML copy.
* `--write` does NOT overwrite an existing dispersion field.

Skip if `requests` / `tomlkit` / `yaml` aren't installed: those live in
`scripts/requirements-curation.txt` and aren't part of the runtime
install.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from textwrap import dedent

import pytest

pytest.importorskip("requests")
pytest.importorskip("tomlkit")
pytest.importorskip("yaml")

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

FIXTURE = Path(__file__).parent / "fixtures" / "refractiveindex_sample.yaml"


@pytest.fixture
def enricher():
    """Re-import fresh per test so module-level state doesn't leak."""
    if "enrich_from_refractiveindex" in sys.modules:
        del sys.modules["enrich_from_refractiveindex"]
    return importlib.import_module("enrich_from_refractiveindex")


def _patch_data_dir(monkeypatch, enricher, tmp_path: Path) -> None:
    """Redirect both module-level DATA_DIR pointers to `tmp_path`."""
    import _curation

    monkeypatch.setattr(_curation, "DATA_DIR", tmp_path)
    monkeypatch.setattr(enricher, "DATA_DIR", tmp_path)


def _stub_load_all(enricher, monkeypatch, mats: dict) -> None:
    monkeypatch.setattr(enricher, "load_all", lambda: mats)


def _stub_fetch(enricher, monkeypatch, payload_for: dict[str, str]) -> None:
    """Stub `cached_get_text` to return per-URL fixture YAML.

    Map keys are URL substrings; first match wins. Anything unmapped
    raises — tests should declare every URL they expect a hit on.
    """

    def fake_fetch(url, **kw):
        for needle, payload in payload_for.items():
            if needle in url:
                return payload
        raise AssertionError(f"unexpected fetch: {url}")

    monkeypatch.setattr(enricher, "cached_get_text", fake_fetch)


class _StubMaterial:
    def __init__(self, optical: dict | None = None):
        self.properties = type(
            "P",
            (),
            {"optical": type("O", (), optical or {})()},
        )()


# --------------------------------------------------------------------------- #
# Fixture validity                                                            #
# --------------------------------------------------------------------------- #


def test_fixture_file_is_valid_yaml():
    import yaml

    payload = yaml.safe_load(FIXTURE.read_text())
    assert "DATA" in payload
    assert payload["DATA"][0]["type"] == "tabulated nk"


# --------------------------------------------------------------------------- #
# Parser                                                                      #
# --------------------------------------------------------------------------- #


def test_parser_converts_micrometres_to_nanometres(enricher):
    """The fixture's wavelengths are 0.3 / 0.5 / 0.7 / 0.9 µm → 300 / 500
    / 700 / 900 nm. The ×1000 factor is the load-bearing thing here."""
    disp = enricher.parse_dispersion_yaml(FIXTURE.read_text())
    assert disp.wavelengths_nm == [300.0, 500.0, 700.0, 900.0]
    assert disp.n == [1.50, 1.55, 1.52, 1.50]
    assert disp.k == [0.001, 0.002, 0.003, 0.004]
    assert disp.type_label == "tabulated nk"
    assert disp.has_doi is True


def test_parser_handles_tabulated_n_only(enricher):
    src = dedent(
        """\
        REFERENCES: "Test"
        DATA:
          - type: tabulated n
            data: |
                0.4 1.50
                0.6 1.52
        """
    )
    disp = enricher.parse_dispersion_yaml(src)
    assert disp.wavelengths_nm == [400.0, 600.0]
    assert disp.n == [1.50, 1.52]
    assert disp.k is None


def test_parser_evaluates_sellmeier_formula_1(enricher):
    """formula 1 (Sellmeier) is evaluated on a log-spaced grid spanning
    the declared wavelength_range. Sanity-check NaI's well-known value
    n(589 nm) ≈ 1.77 falls between adjacent grid points."""
    src = dedent(
        """\
        REFERENCES: "Li 1976"
        DATA:
          - type: formula 1
            wavelength_range: 0.25 40
            coefficients: 0.478 1.532 0.170 4.27 86.21
        """
    )
    disp = enricher.parse_dispersion_yaml(src)
    assert disp.k is None
    assert disp.type_label == "formula 1"
    # 50 grid points across [0.25, 40] µm = [250, 40000] nm
    assert len(disp.wavelengths_nm) == enricher.SELLMEIER_GRID_POINTS
    assert disp.wavelengths_nm[0] == pytest.approx(250.0, rel=1e-6)
    assert disp.wavelengths_nm[-1] == pytest.approx(40000.0, rel=1e-6)
    # Well-formed Sellmeier => all positive, finite, within plausible
    # bounds. NaI's UV side approaches n ~ 1.93, and the IR side falls
    # off (n(40 µm) ~ 1.36) — the bounds reflect the full grid span.
    assert all(1.0 < n < 2.5 for n in disp.n)
    # Visible-band sanity: n(589 nm) ≈ 1.7745 (well-known for NaI).
    n_589 = enricher._eval_formula_1([0.478, 1.532, 0.170, 4.27, 86.21], 0.589)
    assert n_589 == pytest.approx(1.7745, abs=1e-3)


def test_parser_rejects_yaml_without_data(enricher):
    with pytest.raises(ValueError, match="DATA"):
        enricher.parse_dispersion_yaml("REFERENCES: nope")


def test_doi_extraction(enricher):
    refs = '<a href="https://doi.org/10.1364/AO.35.003562">Appl. Opt.</a>'
    assert enricher._extract_doi(refs) == "10.1364/AO.35.003562"
    assert enricher._extract_doi("no doi here") is None


# --------------------------------------------------------------------------- #
# --dry-run                                                                   #
# --------------------------------------------------------------------------- #


_SYNTHETIC_BGO_GAP = dedent(
    """\
    # top-of-file comment — must survive the round-trip
    [bgo]
    name = "BGO"
    formula = "Bi4Ge3O12"

    [bgo.optical]
    refractive_index = 2.15
    """
)


def test_dry_run_produces_expected_report(enricher, monkeypatch, tmp_path, capsys):
    toml_path = tmp_path / "scintillators.toml"
    toml_path.write_text(_SYNTHETIC_BGO_GAP)
    _patch_data_dir(monkeypatch, enricher, tmp_path)
    _stub_load_all(
        enricher,
        monkeypatch,
        {"bgo": _StubMaterial(optical={"refractive_index_dispersion": None})},
    )
    _stub_fetch(enricher, monkeypatch, {"Bi4Ge3O12": FIXTURE.read_text()})

    rc = enricher.compare(key_filter="bgo", dry_run=True)
    assert rc == 0
    out = capsys.readouterr().out
    assert "# refractiveindex.info enrichment report" in out
    assert "Mode: comparison-only" in out
    assert "bgo" in out
    assert "MISSING" in out
    assert "CC0" in out


# --------------------------------------------------------------------------- #
# --write: add-only                                                           #
# --------------------------------------------------------------------------- #


def test_write_adds_dispersion_and_sources_row(enricher, monkeypatch, tmp_path):
    toml_path = tmp_path / "scintillators.toml"
    toml_path.write_text(_SYNTHETIC_BGO_GAP)
    _patch_data_dir(monkeypatch, enricher, tmp_path)
    _stub_load_all(
        enricher,
        monkeypatch,
        {"bgo": _StubMaterial(optical={"refractive_index_dispersion": None})},
    )
    _stub_fetch(enricher, monkeypatch, {"Bi4Ge3O12": FIXTURE.read_text()})

    rc = enricher.compare(key_filter="bgo", dry_run=False, write=True)
    assert rc == 0

    out = toml_path.read_text()
    # Field landed under [bgo.optical] as an inline dispersion table.
    assert "refractive_index_dispersion" in out
    # µm → nm conversion: fixture is 0.3 µm → 300 nm.
    assert "wavelengths_nm = [300" in out
    # Source row tagged with the canonical group.field key.
    assert "[bgo._sources]" in out
    assert "optical.refractive_index_dispersion" in out
    assert "CC0" in out
    assert "refractiveindex.info" in out
    # Top-of-file comment survives the round-trip.
    assert "# top-of-file comment" in out


def test_write_does_not_overwrite_existing_dispersion(enricher, monkeypatch, tmp_path):
    """When the target field is already present, the writeback path
    must be a no-op even with --write."""
    src = dedent(
        """\
        [bgo]
        name = "BGO"

        [bgo.optical]
        refractive_index = 2.15
        # Curator-set value — must be preserved.
        refractive_index_dispersion = {wavelengths_nm = [400.0, 700.0], n = [2.20, 2.10]}
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
                optical={
                    "refractive_index_dispersion": {
                        "wavelengths_nm": [400.0, 700.0],
                        "n": [2.20, 2.10],
                    }
                }
            )
        },
    )
    _stub_fetch(enricher, monkeypatch, {"Bi4Ge3O12": FIXTURE.read_text()})

    rc = enricher.compare(key_filter="bgo", dry_run=False, write=True)
    assert rc == 0

    after = toml_path.read_text()
    # Original n values are still there; fixture's 1.50 didn't sneak in.
    assert "[2.2, 2.1]" in after or "2.2" in after
    assert "1.50" not in after
    # No source row was added (we never overwrote, so no provenance entry).
    assert "optical.refractive_index_dispersion" not in after


def test_comparison_only_never_writes(enricher, monkeypatch, tmp_path):
    toml_path = tmp_path / "scintillators.toml"
    toml_path.write_text(_SYNTHETIC_BGO_GAP)
    before = toml_path.read_text()
    _patch_data_dir(monkeypatch, enricher, tmp_path)
    _stub_load_all(
        enricher,
        monkeypatch,
        {"bgo": _StubMaterial(optical={"refractive_index_dispersion": None})},
    )
    _stub_fetch(enricher, monkeypatch, {"Bi4Ge3O12": FIXTURE.read_text()})

    rc = enricher.compare(key_filter="bgo", dry_run=True, write=False)
    assert rc == 0
    assert toml_path.read_text() == before


# --------------------------------------------------------------------------- #
# Source row sanity                                                           #
# --------------------------------------------------------------------------- #


def test_source_row_is_well_formed(enricher):
    disp = enricher.parse_dispersion_yaml(FIXTURE.read_text())
    row = enricher._make_source_row(
        citation_label="Williams 1996 (BGO ord. ray)",
        db_path="main/Bi4Ge3O12/nk/Williams",
        disp=disp,
    )
    assert row["license"] == "CC0"
    assert row["kind"] == "doi"  # fixture has a DOI in REFERENCES
    assert "via refractiveindex.info" in row["citation"]
    assert row["ref"].startswith("refractiveindex.info:")
    assert "fetched" in row["note"]
    assert "300-900 nm" in row["note"]


def test_source_row_falls_back_to_handbook_when_no_doi(enricher):
    src = dedent(
        """\
        REFERENCES: "no doi here"
        DATA:
          - type: tabulated n
            data: |
                0.4 1.50
                0.6 1.52
        """
    )
    disp = enricher.parse_dispersion_yaml(src)
    row = enricher._make_source_row(
        citation_label="X",
        db_path="main/X/nk/Y",
        disp=disp,
    )
    assert row["kind"] == "handbook"


# --------------------------------------------------------------------------- #
# --report                                                                    #
# --------------------------------------------------------------------------- #


def test_report_writes_markdown_file(enricher, monkeypatch, tmp_path, capsys):
    toml_path = tmp_path / "scintillators.toml"
    toml_path.write_text(_SYNTHETIC_BGO_GAP)
    _patch_data_dir(monkeypatch, enricher, tmp_path)
    _stub_load_all(
        enricher,
        monkeypatch,
        {"bgo": _StubMaterial(optical={"refractive_index_dispersion": None})},
    )
    _stub_fetch(enricher, monkeypatch, {"Bi4Ge3O12": FIXTURE.read_text()})

    out_path = tmp_path / "report.md"
    rc = enricher.compare(key_filter="bgo", dry_run=True, report_path=out_path)
    assert rc == 0
    assert out_path.exists()
    content = out_path.read_text()
    assert "# refractiveindex.info enrichment report" in content
    captured = capsys.readouterr()
    assert "# refractiveindex.info enrichment report" not in captured.out


# --------------------------------------------------------------------------- #
# Entry-map paths are well-formed                                             #
# --------------------------------------------------------------------------- #


def test_entry_map_paths_well_formed(enricher):
    """Each ENTRY_MAP value is `<book>/<page>/nk/<entry>` (4 path
    segments). Catches a typo that would 404 every fetch."""
    for key, (path, label) in enricher.ENTRY_MAP.items():
        parts = path.split("/")
        assert len(parts) == 4, f"{key}: unexpected path {path!r}"
        assert parts[0] == "main"
        assert parts[2] == "nk"
        assert label, f"{key}: empty citation label"
        assert key in enricher.CATEGORY_FOR


# --------------------------------------------------------------------------- #
# cached_get_text smoke test                                                  #
# --------------------------------------------------------------------------- #


def test_cached_get_text_persists_to_disk_and_reuses(monkeypatch, tmp_path):
    import _curation
    from _curation import cached_get_text

    monkeypatch.setattr(_curation, "CACHE_DIR", tmp_path / "cache")
    calls = {"n": 0}

    class _FakeResp:
        def __init__(self, text):
            self.text = text
            self.status_code = 200

        def raise_for_status(self):
            return None

    def fake_get(url, params=None, headers=None, timeout=None):
        calls["n"] += 1
        return _FakeResp(f"hello {calls['n']}")

    monkeypatch.setattr(_curation.requests, "get", fake_get)

    out1 = cached_get_text("https://example.test/x.yml", source="ut", suffix=".yaml")
    out2 = cached_get_text("https://example.test/x.yml", source="ut", suffix=".yaml")
    assert calls["n"] == 1
    assert out1 == out2 == "hello 1"
    # Persisted with the requested suffix.
    cached = list((tmp_path / "cache" / "ut").glob("*.yaml"))
    assert len(cached) == 1
