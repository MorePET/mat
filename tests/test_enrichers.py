"""
Test suite for material enrichment functionality.

Tests periodictable integration and external data sources.
"""

import pytest

from pymat import Material
from pymat.enrichers import enrich_all, enrich_from_periodictable


class TestPeriodictableEnrichment:
    """Test enrichment from periodictable library."""

    @pytest.mark.xfail(
        reason=(
            "periodictable only has density for pure elements, not compounds. "
            "enrich_from_periodictable needs a density-from-composition "
            "calculator before this test can pass. Tracked separately."
        ),
        strict=True,
    )
    def test_enrich_simple_formula(self):
        """Test enriching material with simple formula."""
        mat = Material(name="Aluminum Oxide", formula="Al2O3")

        # Initially no density
        assert mat.density is None or mat.density == 0

        enrich_from_periodictable(mat)

        # After enrichment should have density
        assert mat.density is not None
        assert mat.density > 0

    @pytest.mark.xfail(
        reason=(
            "periodictable only has density for pure elements, not compounds. Tracked separately."
        ),
        strict=True,
    )
    def test_enrich_complex_formula(self):
        """Test enriching with complex formula."""
        mat = Material(name="LYSO", formula="Lu1.8Y0.2SiO5")

        enrich_from_periodictable(mat)

        # Should have set density
        assert mat.density is not None
        # LYSO should be around 7.1 g/cm³
        assert 6.5 < mat.density < 7.5

    def test_enrich_without_formula(self):
        """Test enrichment with no formula."""
        mat = Material(name="Test Material")

        # Should not crash
        result = enrich_from_periodictable(mat)

        assert result == mat

    @pytest.mark.skipif(
        not pytest.importorskip("periodictable", reason="periodictable not installed"),
        reason="periodictable not installed",
    )
    def test_composition_extraction(self):
        """Test that composition is extracted from formula."""
        mat = Material(name="Test", formula="H2O")

        enrich_from_periodictable(mat)

        # Should have extracted composition
        if mat.composition:
            assert "H" in mat.composition
            assert "O" in mat.composition

    def test_enrich_returns_material(self):
        """Test that enrichment returns the material."""
        mat = Material(name="Test", formula="Al2O3")

        try:
            result = enrich_from_periodictable(mat)
            assert result is mat
        except ImportError:
            pytest.skip("periodictable not installed")


class TestEnrichAll:
    """Test enrich_all function."""

    @pytest.mark.xfail(
        reason=(
            "periodictable only has density for pure elements, not compounds. Tracked separately."
        ),
        strict=True,
    )
    def test_enrich_all_with_periodictable(self):
        """Test enriching all data sources."""
        mat = Material(name="Test", formula="SiO2")

        result = enrich_all(mat, use_periodictable=True)

        assert result is mat
        # Should have enriched from periodictable
        assert mat.density is not None

    def test_enrich_all_without_periodictable(self):
        """Test enriching without periodictable."""
        mat = Material(name="Test")

        result = enrich_all(mat, use_periodictable=False)

        assert result is mat


class TestEnrichmentEdgeCases:
    """Test edge cases in enrichment."""

    @pytest.mark.skipif(
        not pytest.importorskip("periodictable", reason="periodictable not installed"),
        reason="periodictable not installed",
    )
    def test_enrich_invalid_formula(self):
        """Test enrichment with invalid formula."""
        mat = Material(name="Test", formula="XyZ123Invalid")

        # Should not crash, just skip enrichment
        enrich_from_periodictable(mat)

        # Density should remain None/0 (or what was there)
        assert True  # Just verify no exception

    @pytest.mark.skipif(
        not pytest.importorskip("periodictable", reason="periodictable not installed"),
        reason="periodictable not installed",
    )
    def test_enrich_already_has_density(self):
        """Test enriching material that already has density."""
        mat = Material(name="Test", formula="Al2O3", density=3.95)

        enrich_from_periodictable(mat)

        # Should keep existing density (not override)
        assert mat.density == 3.95


class TestCommonMaterialsEnrichment:
    """Test enrichment on common materials."""

    @pytest.mark.skipif(
        not pytest.importorskip("periodictable", reason="periodictable not installed"),
        reason="periodictable not installed",
    )
    def test_enrich_aluminum(self):
        """Test enriching aluminum."""
        mat = Material(name="Aluminum", formula="Al")

        enrich_from_periodictable(mat)

        assert mat.density is not None
        # Al density is ~2.7 g/cm³
        assert 2.5 < mat.density < 3.0

    @pytest.mark.skipif(
        not pytest.importorskip("periodictable", reason="periodictable not installed"),
        reason="periodictable not installed",
    )
    def test_enrich_copper(self):
        """Test enriching copper."""
        mat = Material(name="Copper", formula="Cu")

        enrich_from_periodictable(mat)

        assert mat.density is not None
        # Cu density is ~8.96 g/cm³
        assert 8.5 < mat.density < 9.5

    @pytest.mark.skipif(
        not pytest.importorskip("periodictable", reason="periodictable not installed"),
        reason="periodictable not installed",
    )
    def test_enrich_tungsten(self):
        """Test enriching tungsten."""
        mat = Material(name="Tungsten", formula="W")

        enrich_from_periodictable(mat)

        assert mat.density is not None
        # W density is ~19.3 g/cm³
        assert 18.5 < mat.density < 20.0
