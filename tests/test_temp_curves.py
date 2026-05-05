"""Tests for #148 — `<prop>_curve` temperature-dependent property curves.

Per ADR-0003:
- New `TempCurve` dataclass on `pymat.curves`.
- New `<prop>_curve: Optional[TempCurve]` sibling fields on the dataclasses
  for: thermal_conductivity, specific_heat, thermal_expansion,
  youngs_modulus, yield_strength, resistivity, refractive_index,
  light_yield, decay_time.
- Loader parses `<prop>_curve = {temps_K=[...], values=[...]}`.
- `_at(T)` evaluators on each dataclass: curve > legacy ref_temp+coeff > scalar.
- Edge cases pinned: clamp out-of-range, raise on unsorted/mismatched at load.
"""

from __future__ import annotations

from textwrap import dedent

import pytest

from pymat.curves import TempCurve
from pymat.loader import load_toml
from pymat.units import ureg


class TestTempCurveInterpolation:
    def test_exact_knot_returns_knot_value(self):
        c = TempCurve(temps_K=[100, 200, 300], values=[1.0, 2.0, 3.0])
        assert c.interpolate(200.0) == pytest.approx(2.0)

    def test_between_knots_linear_interp(self):
        c = TempCurve(temps_K=[100, 200], values=[1.0, 2.0])
        assert c.interpolate(150.0) == pytest.approx(1.5)

    def test_below_min_clamps(self):
        c = TempCurve(temps_K=[100, 200], values=[5.0, 10.0])
        assert c.interpolate(50.0) == 5.0  # clamped to min knot value

    def test_above_max_clamps(self):
        c = TempCurve(temps_K=[100, 200], values=[5.0, 10.0])
        assert c.interpolate(500.0) == 10.0  # clamped to max knot value

    def test_single_point_curve_returns_constant(self):
        c = TempCurve(temps_K=[293.15], values=[7.5])
        assert c.interpolate(77.0) == 7.5
        assert c.interpolate(293.15) == 7.5
        assert c.interpolate(500.0) == 7.5

    def test_unsorted_temps_raises_at_construction(self):
        with pytest.raises(ValueError, match="sorted"):
            TempCurve(temps_K=[200, 100, 300], values=[1.0, 2.0, 3.0])

    def test_mismatched_lengths_raises_at_construction(self):
        with pytest.raises(ValueError, match="length"):
            TempCurve(temps_K=[100, 200, 300], values=[1.0, 2.0])

    def test_empty_curve_raises_at_construction(self):
        with pytest.raises(ValueError, match="at least one"):
            TempCurve(temps_K=[], values=[])


class TestLoaderParsesCurves:
    def test_loads_thermal_conductivity_curve(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [aluminum]
            name = "Aluminum"
            [aluminum.thermal]
            thermal_conductivity_value = 167
            thermal_conductivity_unit = "W/(m*K)"
            thermal_conductivity_curve = { temps_K = [77, 200, 293, 400], values = [105, 150, 167, 180] }
            """)
        )
        al = load_toml(p)["aluminum"]
        c = al.properties.thermal.thermal_conductivity_curve
        assert isinstance(c, TempCurve)
        assert c.temps_K == [77, 200, 293, 400]
        assert c.values == [105, 150, 167, 180]
        # Scalar still set, untouched.
        assert al.properties.thermal.thermal_conductivity == 167

    def test_curve_without_scalar_loads(self, tmp_path):
        """A curve alone is valid — the scalar field stays None."""
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [lyso]
            name = "LYSO"
            [lyso.optical]
            light_yield_curve = { temps_K = [233, 293, 313], values = [38000, 33000, 32000] }
            """)
        )
        lyso = load_toml(p)["lyso"]
        c = lyso.properties.optical.light_yield_curve
        assert isinstance(c, TempCurve)
        assert lyso.properties.optical.light_yield is None

    def test_invalid_curve_raises_at_load(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [bad]
            name = "Bad"
            [bad.thermal]
            thermal_conductivity_curve = { temps_K = [200, 100, 300], values = [1.0, 2.0, 3.0] }
            """)
        )
        with pytest.raises(ValueError, match="sorted"):
            load_toml(p)

    def test_curve_field_on_unknown_prop_silently_ignored(self, tmp_path):
        """A curve for a non-existent property is silently ignored
        (consistent with hasattr-based assignment)."""
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [m]
            name = "M"
            [m.thermal]
            no_such_property_curve = { temps_K = [100, 200], values = [1.0, 2.0] }
            """)
        )
        # Must not raise
        load_toml(p)


class TestEvaluatorsCurveFirst:
    def test_thermal_conductivity_at_uses_curve_when_present(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [al]
            name = "Aluminum"
            [al.thermal]
            thermal_conductivity_value = 167
            thermal_conductivity_unit = "W/(m*K)"
            thermal_conductivity_curve = { temps_K = [77, 293], values = [105, 167] }
            """)
        )
        al = load_toml(p)["al"]
        # At 77 K, curve says 105.
        k77 = al.properties.thermal.thermal_conductivity_at(77 * ureg.kelvin)
        assert k77.to("W/(m*K)").magnitude == pytest.approx(105)
        # At midpoint, linear interp.
        k185 = al.properties.thermal.thermal_conductivity_at(185 * ureg.kelvin)
        # midpoint of [77,293] is 185, midpoint of [105,167] is 136
        assert k185.to("W/(m*K)").magnitude == pytest.approx(136, rel=0.01)

    def test_thermal_conductivity_at_falls_back_to_scalar(self, tmp_path):
        """Regression — when no curve and no coeff, return the scalar value
        regardless of T (existing behavior preserved)."""
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [steel]
            name = "Steel"
            [steel.thermal]
            thermal_conductivity_value = 15.1
            thermal_conductivity_unit = "W/(m*K)"
            """)
        )
        steel = load_toml(p)["steel"]
        k = steel.properties.thermal.thermal_conductivity_at(373.15 * ureg.kelvin)
        # No curve, no coeff → return scalar (legacy behavior, coeff=0)
        assert k.to("W/(m*K)").magnitude == pytest.approx(15.1)

    def test_legacy_ref_temp_coeff_still_works(self, tmp_path):
        """Regression — existing TOMLs using ref_temp + coeff continue to work."""
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [m]
            name = "M"
            [m.thermal]
            thermal_conductivity_value = 100
            thermal_conductivity_unit = "W/(m*K)"
            thermal_conductivity_ref_temp = 20
            thermal_conductivity_coeff = 0.001
            """)
        )
        m = load_toml(p)["m"]
        k_ref = m.properties.thermal.thermal_conductivity_at(293.15 * ureg.kelvin)
        # T_ref = 20°C = 293.15 K, delta_T = 0 → k = 100
        assert k_ref.to("W/(m*K)").magnitude == pytest.approx(100)


class TestNewAtMethods:
    """The other 8 properties should also support `_at(T)` lookups."""

    @pytest.mark.parametrize(
        "group,prop,unit_str",
        [
            ("thermal", "specific_heat", "J/(kg*K)"),
            ("thermal", "thermal_expansion", "1/K"),
            ("mechanical", "youngs_modulus", "GPa"),
            ("mechanical", "yield_strength", "MPa"),
            ("electrical", "resistivity", "ohm*m"),
            ("optical", "light_yield", None),  # dimensionless / no _unit field
            ("optical", "decay_time", None),
            ("optical", "refractive_index", None),
        ],
    )
    def test_each_property_has_at_method(self, tmp_path, group, prop, unit_str):
        unit_line = f'{prop}_unit = "{unit_str}"' if unit_str else ""
        p = tmp_path / "m.toml"
        p.write_text(
            dedent(f"""
            [m]
            name = "M"
            [m.{group}]
            {prop}_value = 100.0
            {unit_line}
            {prop}_curve = {{ temps_K = [100, 200, 300], values = [80.0, 100.0, 120.0] }}
            """)
        )
        m = load_toml(p)["m"]
        getter = getattr(getattr(m.properties, group), f"{prop}_at")
        v = getter(150.0 * ureg.kelvin)
        # Linear midpoint of [80,100] at midpoint of [100,200] is 90.
        magnitude = v.to(unit_str).magnitude if unit_str else v
        assert magnitude == pytest.approx(90.0)


class TestRegressionCurveAbsent:
    """When no _curve is present, behavior is identical to today."""

    def test_full_corpus_loads_without_curves(self, tmp_path):
        """No TOML in src/pymat/data/ has _curve fields yet; the loader
        must not regress on the full corpus."""
        from pymat import _CATEGORY_BASES
        from pymat.loader import load_category

        for cat in _CATEGORY_BASES:
            mats = load_category(cat)
            assert mats, f"category {cat} loaded empty"
