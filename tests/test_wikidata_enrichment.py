"""Tests for `scripts/enrich_from_wikidata.py` — issue #158.

Covers the curation-tooling behaviors that the Phase 4 prep PR (#197)
shipped the foundations for and that #158 actually wires together:

* `--dry-run` mode produces a comparison report without touching the
  network (substring assertions against the fixture-driven output).
* `--write` against a `tmp_path` TOML copy adds the value AND the
  `_sources` row when the field was missing.
* `--write` does NOT overwrite an existing value, even if Wikidata
  diverges (the DIFF case must stay advisory).
* Round-trip preserves comments in the TOML — the same guarantee
  `_curation.writeback` makes, exercised end-to-end via the enricher.

These tests are gated on `requests` + `tomlkit` because the curation
deps live in `scripts/requirements-curation.txt`, not in the main
install — see `tests/test_curation_helpers.py` for the same pattern.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from textwrap import dedent

import pytest

pytest.importorskip("requests")
pytest.importorskip("tomlkit")

# scripts/ isn't a package; inject it onto sys.path so we can import
# the enricher module directly.
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def enricher():
    """Import (or re-import) the enricher module fresh per test."""
    if "enrich_from_wikidata" in sys.modules:
        del sys.modules["enrich_from_wikidata"]
    return importlib.import_module("enrich_from_wikidata")


# --------------------------------------------------------------------------- #
# --dry-run                                                                   #
# --------------------------------------------------------------------------- #


def test_dry_run_uses_fixture_and_reports_known_materials(enricher, monkeypatch, capsys):
    """`--dry-run` must consume the fixture and never hit the network."""

    def boom(*a, **kw):  # pragma: no cover — must not be called
        raise AssertionError("network must not be hit in --dry-run")

    monkeypatch.setattr(enricher.requests, "post", boom)
    monkeypatch.setattr(enricher.requests, "get", boom)

    rc = enricher.compare(key_filter=None, dry_run=True)
    assert rc == 0

    out = capsys.readouterr().out
    # Header + at least one fixture material (aluminum: Q663, copper: Q753).
    assert "# Wikidata enrichment report" in out
    assert "Mode: comparison-only" in out
    assert "aluminum" in out
    assert "Q753" in out
    # Property columns must be present.
    assert "density" in out
    assert "melting_point" in out
    assert "thermal_conductivity" in out
    assert "specific_heat" in out
    assert "boiling_point" in out


def test_dry_run_with_key_filter_limits_output(enricher, capsys):
    rc = enricher.compare(key_filter="copper", dry_run=True)
    assert rc == 0
    out = capsys.readouterr().out
    assert "Materials checked: 1" in out
    assert "copper" in out
    # Other fixture entries should NOT appear in a single-key run.
    assert "tungsten" not in out


# --------------------------------------------------------------------------- #
# --write: end-to-end add-only writeback                                      #
# --------------------------------------------------------------------------- #


_SYNTHETIC_TOML_WITH_GAP = dedent(
    """\
    # top-of-file comment — must survive the round-trip
    [aluminum]
    name = "Aluminum"

    [aluminum.mechanical]
    # density was already curated; melting point is the gap.
    density_value = 2.7
    density_unit = "g/cm^3"

    [aluminum.thermal]
    # melting_point intentionally absent — Wikidata fixture should fill it.
    thermal_conductivity_value = 235
    thermal_conductivity_unit = "W/(m*K)"
    """
)


_SYNTHETIC_TOML_DIVERGENT = dedent(
    """\
    [aluminum]
    name = "Aluminum"

    [aluminum.mechanical]
    # Deliberately wrong — the enricher must NOT silently fix it.
    density_value = 9.99
    density_unit = "g/cm^3"
    """
)


def _patch_data_dir(monkeypatch, enricher, tmp_path: Path) -> None:
    """Redirect the enricher's DATA_DIR + the helper module's DATA_DIR
    to `tmp_path` so writebacks land in the test sandbox."""
    import _curation

    monkeypatch.setattr(_curation, "DATA_DIR", tmp_path)
    monkeypatch.setattr(enricher, "DATA_DIR", tmp_path)


def _stub_load_all(enricher, monkeypatch, mats: dict) -> None:
    """Stub `pymat.load_all` so the enricher sees a known material map.

    The runtime loader can't easily be pointed at `tmp_path` without
    monkey-patching the package internals; faking `load_all` is the
    smallest-surface intervention.
    """
    monkeypatch.setattr(enricher, "load_all", lambda: mats)


class _StubMaterial:
    """Minimal stand-in for `pymat.Material` — only the attribute path
    `mat.properties.<group>.<field>` matters to the enricher."""

    def __init__(self, mechanical: dict | None = None, thermal: dict | None = None):
        self.properties = type(
            "P",
            (),
            {
                "mechanical": type("M", (), mechanical or {})(),
                "thermal": type("T", (), thermal or {})(),
            },
        )()


def test_write_adds_missing_value_and_sources_row(enricher, monkeypatch, tmp_path):
    """`--write`: missing field + Wikidata value → write both value and `_sources` row."""
    toml_path = tmp_path / "metals.toml"
    toml_path.write_text(_SYNTHETIC_TOML_WITH_GAP)

    _patch_data_dir(monkeypatch, enricher, tmp_path)
    # mat exists but `melting_point` is None — the writeback gap.
    _stub_load_all(
        enricher,
        monkeypatch,
        {
            "aluminum": _StubMaterial(
                mechanical={"density": 2.7},
                thermal={"melting_point": None, "thermal_conductivity": 235},
            )
        },
    )

    rc = enricher.compare(key_filter="aluminum", dry_run=True, write=True)
    assert rc == 0

    out = toml_path.read_text()
    # New value written under [aluminum.thermal]
    assert "melting_point_value" in out
    assert 'melting_point_unit = "degC"' in out
    # _sources row attached at the material level, keyed by `thermal.melting_point`.
    assert "[aluminum._sources]" in out
    assert "thermal.melting_point" in out
    assert "Q663" in out  # citation references the QID
    assert "CC0" in out
    assert "P2101" in out  # note carries the property ID
    # Top-of-file comment survived the round-trip.
    assert "# top-of-file comment" in out


def test_write_does_not_overwrite_existing_value(enricher, monkeypatch, tmp_path):
    """`--write`: existing value diverges from Wikidata → DIFF reported, NO write.

    We populate every property on the stub mat so the only candidate
    field for a writeback is the (already-set) divergent density. That
    isolates the DIFF behavior from the MISSING-add path tested above.
    """
    toml_path = tmp_path / "metals.toml"
    toml_path.write_text(_SYNTHETIC_TOML_DIVERGENT)

    _patch_data_dir(monkeypatch, enricher, tmp_path)
    _stub_load_all(
        enricher,
        monkeypatch,
        {
            "aluminum": _StubMaterial(
                mechanical={"density": 9.99},
                # Pre-fill thermal so no MISSING-add fires for those props.
                thermal={
                    "melting_point": 660,
                    "thermal_conductivity": 235,
                    "specific_heat": 900,
                },
            )
        },
    )

    rc = enricher.compare(key_filter="aluminum", dry_run=True, write=True)
    assert rc == 0

    after = toml_path.read_text()
    # The divergent value must still be exactly what the curator wrote.
    assert "density_value = 9.99" in after
    assert "density_value = 2.7" not in after
    # No `_sources` row attached for density — silent updates are
    # forbidden, even when paired with provenance.
    assert "mechanical.density" not in after


def test_write_round_trip_preserves_grade_level_comments(enricher, monkeypatch, tmp_path):
    """Comments at the family + grade level both survive `--write`."""
    src = dedent(
        """\
        # category-level comment
        [aluminum]
        name = "Aluminum"

        [aluminum.a6061]
        # grade-level comment — the survival flag for tomlkit round-trips
        name = "Aluminum 6061"

        [aluminum.a6061.thermal]
        thermal_conductivity_value = 167
        thermal_conductivity_unit = "W/(m*K)"
        """
    )
    toml_path = tmp_path / "metals.toml"
    toml_path.write_text(src)

    _patch_data_dir(monkeypatch, enricher, tmp_path)
    # Make `a6061` resolvable via the curator-fallback dict (Q663).
    monkeypatch.setitem(enricher.WIKIDATA_QIDS, "aluminum.a6061", "Q663")
    _stub_load_all(
        enricher,
        monkeypatch,
        {
            "aluminum.a6061": _StubMaterial(
                mechanical={"density": None},
                thermal={"melting_point": None, "thermal_conductivity": 167},
            )
        },
    )

    rc = enricher.compare(key_filter="aluminum.a6061", dry_run=True, write=True)
    assert rc == 0

    out = toml_path.read_text()
    assert "# category-level comment" in out
    assert "# grade-level comment" in out
    # New `_sources` table lives at the grade level, not the family.
    assert "[aluminum.a6061._sources]" in out


# --------------------------------------------------------------------------- #
# Comparison-only mode never mutates files                                    #
# --------------------------------------------------------------------------- #


def test_comparison_only_never_writes(enricher, monkeypatch, tmp_path):
    """Default mode (no `--write`) must be a pure read."""
    toml_path = tmp_path / "metals.toml"
    toml_path.write_text(_SYNTHETIC_TOML_WITH_GAP)
    before = toml_path.read_text()

    _patch_data_dir(monkeypatch, enricher, tmp_path)
    _stub_load_all(
        enricher,
        monkeypatch,
        {
            "aluminum": _StubMaterial(
                mechanical={"density": 2.7},
                thermal={"melting_point": None, "thermal_conductivity": 235},
            )
        },
    )

    rc = enricher.compare(key_filter="aluminum", dry_run=True, write=False)
    assert rc == 0
    assert toml_path.read_text() == before


# --------------------------------------------------------------------------- #
# --report writes to a markdown file                                          #
# --------------------------------------------------------------------------- #


def test_report_writes_markdown_file(enricher, tmp_path, capsys):
    out_path = tmp_path / "wd-report.md"
    rc = enricher.compare(key_filter="copper", dry_run=True, report_path=out_path)
    assert rc == 0
    assert out_path.exists()
    content = out_path.read_text()
    assert "# Wikidata enrichment report" in content
    assert "copper" in content
    # When --report is set, stdout stays quiet (only the "Report
    # written to ..." note goes to stderr).
    captured = capsys.readouterr()
    assert "# Wikidata enrichment report" not in captured.out
