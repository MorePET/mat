"""Tests for #149 — `<prop>_stddev` sibling sugar + boundary helpers.

Per ADR-0003, `_stddev` is loader sugar that folds sibling stddev into the
existing ufloat mechanism — NOT a parallel set of dataclass fields. Both
forms work; double-specification is a hard error.

Also covers: ufloat → float coercion at the build123d / JSON boundary
(`Material.density_g_mm3`).
"""

from __future__ import annotations

from textwrap import dedent

import pytest
from uncertainties import UFloat

from pymat.loader import load_toml


class TestStddevSiblingSugar:
    def test_value_form_with_sibling_stddev_produces_ufloat(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [steel]
            name = "Steel"
            [steel.mechanical]
            density_value = 7.85
            density_unit = "g/cm^3"
            density_stddev = 0.05
            """)
        )
        steel = load_toml(p)["steel"]
        d = steel.properties.mechanical.density
        assert isinstance(d, UFloat), f"expected ufloat, got {type(d).__name__}"
        assert d.nominal_value == pytest.approx(7.85)
        assert d.std_dev == pytest.approx(0.05)

    def test_legacy_bare_form_with_sibling_stddev_produces_ufloat(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [steel]
            name = "Steel"
            [steel.mechanical]
            density = 7.85
            density_stddev = 0.05
            """)
        )
        steel = load_toml(p)["steel"]
        d = steel.properties.mechanical.density
        assert isinstance(d, UFloat)
        assert d.nominal_value == pytest.approx(7.85)
        assert d.std_dev == pytest.approx(0.05)

    def test_in_value_form_still_works(self, tmp_path):
        """Regression — the existing {nominal, stddev} form must keep working."""
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [steel]
            name = "Steel"
            [steel.mechanical]
            density = { nominal = 7.85, stddev = 0.05 }
            """)
        )
        steel = load_toml(p)["steel"]
        d = steel.properties.mechanical.density
        assert isinstance(d, UFloat)
        assert d.nominal_value == pytest.approx(7.85)
        assert d.std_dev == pytest.approx(0.05)

    def test_double_specification_raises(self, tmp_path):
        """Both in-value `stddev` AND sibling `_stddev` is a hard error."""
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [steel]
            name = "Steel"
            [steel.mechanical]
            density = { nominal = 7.85, stddev = 0.05 }
            density_stddev = 0.10
            """)
        )
        with pytest.raises(ValueError, match="double-specification"):
            load_toml(p)

    def test_stddev_without_base_value_raises(self, tmp_path):
        """A `_stddev` sibling with no matching base value is a typo signal."""
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [steel]
            name = "Steel"
            [steel.mechanical]
            density_stddev = 0.05
            """)
        )
        with pytest.raises(ValueError, match="density_stddev"):
            load_toml(p)

    def test_stddev_zero_still_produces_ufloat(self, tmp_path):
        """Explicit stddev=0 is a valid declaration of certainty."""
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [steel]
            name = "Steel"
            [steel.mechanical]
            density_value = 7.85
            density_unit = "g/cm^3"
            density_stddev = 0.0
            """)
        )
        steel = load_toml(p)["steel"]
        d = steel.properties.mechanical.density
        assert isinstance(d, UFloat)
        assert d.std_dev == 0.0


class TestBoundaryCoercion:
    """ufloat → float at build123d / JSON boundaries (Material.density_g_mm3)."""

    def test_density_g_mm3_returns_float_when_density_is_ufloat(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [steel]
            name = "Steel"
            [steel.mechanical]
            density_value = 7.85
            density_unit = "g/cm^3"
            density_stddev = 0.05
            """)
        )
        steel = load_toml(p)["steel"]
        # density is a ufloat (#149 sugar), but density_g_mm3 must
        # return a plain float — build123d can't accept ufloats.
        result = steel.density_g_mm3
        assert isinstance(result, float), f"expected float, got {type(result).__name__}"
        assert result == pytest.approx(0.00785)

    def test_density_g_mm3_unchanged_for_plain_float(self, tmp_path):
        """Regression — no behavior change for materials without uncertainty."""
        p = tmp_path / "m.toml"
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
        assert isinstance(steel.density_g_mm3, float)
        assert steel.density_g_mm3 == pytest.approx(0.00785)

    def test_density_g_mm3_zero_when_density_missing(self, tmp_path):
        """Existing contract — no density yields 0.0, not raises."""
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [steel]
            name = "Steel"
            """)
        )
        steel = load_toml(p)["steel"]
        assert steel.density_g_mm3 == 0.0

    def test_mass_from_volume_mm3_returns_float_for_ufloat_density(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [steel]
            name = "Steel"
            [steel.mechanical]
            density_value = 7.85
            density_unit = "g/cm^3"
            density_stddev = 0.05
            """)
        )
        steel = load_toml(p)["steel"]
        m = steel.mass_from_volume_mm3(1000.0)
        assert isinstance(m, float)
        assert m == pytest.approx(7.85)


class TestMultipleStddevFields:
    """A material can declare uncertainty on multiple properties."""

    def test_multiple_stddev_siblings_in_one_group(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [steel]
            name = "Steel"
            [steel.mechanical]
            density_value = 7.85
            density_unit = "g/cm^3"
            density_stddev = 0.05
            yield_strength_value = 250
            yield_strength_unit = "MPa"
            yield_strength_stddev = 15
            """)
        )
        steel = load_toml(p)["steel"]
        assert isinstance(steel.properties.mechanical.density, UFloat)
        assert steel.properties.mechanical.density.std_dev == pytest.approx(0.05)
        assert isinstance(steel.properties.mechanical.yield_strength, UFloat)
        assert steel.properties.mechanical.yield_strength.std_dev == pytest.approx(15)
