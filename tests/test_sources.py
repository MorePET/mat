"""Tests for #150 — `[<material>._sources]` provenance table.

Covers:
- Loader picks up `[<material>._sources]` and attaches to Material._sources
- `_default` fallback when no per-property entry exists
- Per-property override wins over `_default`
- Underscore keys never leak into AllProperties
- `mat.source_of("mechanical.density")` returns Source | None
- `mat.cite("mechanical.density")` emits a BibTeX entry for DOI / Wikidata QID
- `mat.cite()` (no args) emits all entries used by the material, deduplicated
- Empty / missing sources are graceful (no crash)
- Inheritance: child sources overlay parent sources
"""

from __future__ import annotations

from textwrap import dedent

import pytest

from pymat.loader import load_toml
from pymat.sources import Source


@pytest.fixture
def aluminum_toml(tmp_path):
    """Aluminum 6061 material with a full `_sources` block."""
    p = tmp_path / "al.toml"
    p.write_text(
        dedent("""
        [aluminum]
        name = "Aluminum"

        [aluminum.al6061]
        name = "Aluminum 6061-T6"
        grade = "6061-T6"

        [aluminum.al6061.mechanical]
        density_value = 2.70
        density_unit = "g/cm^3"
        yield_strength_value = 276
        yield_strength_unit = "MPa"

        [aluminum.al6061.thermal]
        thermal_conductivity_value = 167
        thermal_conductivity_unit = "W/(m*K)"

        [aluminum.al6061._sources._default]
        citation = "asm_handbook_v2"
        kind = "handbook"
        ref = "ASM Handbook vol.2 p.62"
        license = "proprietary-reference-only"

        [aluminum.al6061._sources."mechanical.density"]
        citation = "matweb_al6061"
        kind = "vendor"
        ref = "https://matweb.com/al6061"
        license = "proprietary-reference-only"

        [aluminum.al6061._sources."mechanical.yield_strength"]
        citation = "kaufman_2000"
        kind = "doi"
        ref = "10.31399/9781615032426"
        license = "proprietary-reference-only"

        [aluminum.al6061._sources."thermal.thermal_conductivity"]
        citation = "nist_cryo_al6061"
        kind = "doi"
        ref = "10.6028/NIST.MONO.177"
        license = "PD-USGov"
        note = "cryogenic NIST data"
        """)
    )
    return p


@pytest.fixture
def aluminum(aluminum_toml):
    mats = load_toml(aluminum_toml)
    return mats["aluminum"].al6061


class TestSourcesParsing:
    def test_sources_attached_to_material(self, aluminum):
        assert aluminum._sources, "expected _sources dict to be populated"

    def test_default_source_present(self, aluminum):
        assert "_default" in aluminum._sources
        s = aluminum._sources["_default"]
        assert isinstance(s, Source)
        assert s.citation == "asm_handbook_v2"
        assert s.kind == "handbook"
        assert s.license == "proprietary-reference-only"

    def test_per_property_source_present(self, aluminum):
        assert "mechanical.density" in aluminum._sources
        s = aluminum._sources["mechanical.density"]
        assert s.citation == "matweb_al6061"
        assert s.kind == "vendor"

    def test_sources_dont_leak_into_properties(self, aluminum):
        """The _sources dict must never end up on AllProperties or any sub-dataclass."""
        assert not hasattr(aluminum.properties, "_sources")
        assert not hasattr(aluminum.properties.mechanical, "_sources")
        assert not hasattr(aluminum.properties.thermal, "_sources")

    def test_density_value_unchanged_by_sources_block(self, aluminum):
        """Adding _sources must not perturb the actual property value."""
        assert aluminum.properties.mechanical.density == 2.70


class TestSourceOf:
    def test_returns_per_property_source_when_present(self, aluminum):
        s = aluminum.source_of("mechanical.density")
        assert s is not None
        assert s.citation == "matweb_al6061"

    def test_falls_back_to_default(self, aluminum):
        # Aluminum has no per-property source for `mechanical.youngs_modulus`,
        # but _default is defined.
        s = aluminum.source_of("mechanical.youngs_modulus")
        assert s is not None
        assert s.citation == "asm_handbook_v2", "should fall back to _default"

    def test_short_alias_density(self, aluminum):
        """`source_of("density")` should resolve to `mechanical.density`."""
        s = aluminum.source_of("density")
        assert s is not None
        assert s.citation == "matweb_al6061"

    def test_returns_none_when_no_sources_at_all(self, tmp_path):
        p = tmp_path / "bare.toml"
        p.write_text(
            dedent("""
            [steel]
            name = "Steel"
            [steel.mechanical]
            density_value = 7.85
            density_unit = "g/cm^3"
            """)
        )
        steel = load_toml(p)["steel"]
        assert steel.source_of("mechanical.density") is None


class TestCite:
    def test_cite_doi_emits_bibtex(self, aluminum):
        bib = aluminum.cite("mechanical.yield_strength")
        assert "@" in bib, "expected a BibTeX entry"
        assert "kaufman_2000" in bib
        assert "10.31399/9781615032426" in bib

    def test_cite_short_alias(self, aluminum):
        bib_short = aluminum.cite("density")
        bib_full = aluminum.cite("mechanical.density")
        assert bib_short == bib_full

    def test_cite_all_dedupes(self, aluminum):
        all_bib = aluminum.cite()
        # 4 sources defined (_default + 3 per-property). Each entry header
        # `@misc{<citation>,` appears at most once even though _default may
        # apply to many props.
        for citation in ("asm_handbook_v2", "matweb_al6061", "kaufman_2000", "nist_cryo_al6061"):
            header = f"@misc{{{citation},"
            assert all_bib.count(header) == 1, f"{citation} should appear exactly once"

    def test_cite_empty_when_no_sources(self, tmp_path):
        p = tmp_path / "bare.toml"
        p.write_text(
            dedent("""
            [steel]
            name = "Steel"
            [steel.mechanical]
            density_value = 7.85
            density_unit = "g/cm^3"
            """)
        )
        steel = load_toml(p)["steel"]
        assert steel.cite() == ""
        assert steel.cite("density") == ""

    def test_cite_wikidata_qid(self, tmp_path):
        p = tmp_path / "wd.toml"
        p.write_text(
            dedent("""
            [iron]
            name = "Iron"
            [iron.mechanical]
            density_value = 7.874
            density_unit = "g/cm^3"
            [iron._sources."mechanical.density"]
            citation = "wikidata_iron"
            kind = "qid"
            ref = "Q677"
            license = "CC0"
            """)
        )
        iron = load_toml(p)["iron"]
        bib = iron.cite("density")
        assert "wikidata_iron" in bib
        assert "Q677" in bib


class TestSourcesInheritance:
    def test_child_overlays_parent(self, tmp_path):
        p = tmp_path / "inheritance.toml"
        p.write_text(
            dedent("""
            [stainless]
            name = "Stainless"

            [stainless.mechanical]
            density_value = 8.0
            density_unit = "g/cm^3"

            [stainless._sources._default]
            citation = "asm_v1"
            kind = "handbook"
            ref = "ASM v1"
            license = "proprietary-reference-only"

            [stainless.s316L]
            name = "Stainless 316L"

            [stainless.s316L._sources."mechanical.density"]
            citation = "vendor_316L"
            kind = "vendor"
            ref = "https://x"
            license = "proprietary-reference-only"
            """)
        )
        mats = load_toml(p)
        s316L = mats["stainless"].s316L
        # Per-property override wins
        assert s316L.source_of("mechanical.density").citation == "vendor_316L"
        # _default inherited from parent
        assert s316L.source_of("mechanical.youngs_modulus").citation == "asm_v1"


class TestSourcesAreNotPropertyGroups:
    """Regression: `_sources` must never be treated as an unknown property group."""

    def test_underscore_key_skipped_in_update_properties(self, tmp_path):
        """A misplaced `_sources` inside `[mechanical]` should not crash and not setattr."""
        p = tmp_path / "misplaced.toml"
        p.write_text(
            dedent("""
            [steel]
            name = "Steel"
            [steel.mechanical]
            density_value = 7.85
            density_unit = "g/cm^3"
            _comment = "this should be silently ignored, not setattr'd"
            """)
        )
        # Must not raise
        mats = load_toml(p)
        assert mats["steel"].properties.mechanical.density == 7.85
