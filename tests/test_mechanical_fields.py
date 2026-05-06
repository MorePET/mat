"""Tests for #151 — mechanical sub-table additions.

Pure additive: 5 new scalar/list fields on `MechanicalProperties`.
- `flexural_modulus` / `flexural_strength` (MPa)
- `fatigue_limit` (MPa)
- `cte_anisotropic = [a, b, c]` (ppm/K, list-of-3 for non-cubic crystals)
- `creep_rate = [{temp_K, stress_MPa, strain_per_hr}, ...]` (sparse points)
- `cti` (V)

No build123d-visible behavior change. No backwards-compat concern (additive).
"""

from __future__ import annotations

from textwrap import dedent

from pymat.loader import load_toml


class TestNewMechanicalFields:
    def test_flexural_modulus_loads(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [m]
            name = "M"
            [m.mechanical]
            flexural_modulus_value = 3500
            flexural_modulus_unit = "MPa"
            flexural_strength_value = 95
            flexural_strength_unit = "MPa"
            """)
        )
        m = load_toml(p)["m"]
        assert m.properties.mechanical.flexural_modulus == 3500
        assert m.properties.mechanical.flexural_modulus_unit == "MPa"
        assert m.properties.mechanical.flexural_strength == 95

    def test_fatigue_limit_loads(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [m]
            name = "M"
            [m.mechanical]
            fatigue_limit_value = 200
            fatigue_limit_unit = "MPa"
            """)
        )
        m = load_toml(p)["m"]
        assert m.properties.mechanical.fatigue_limit == 200

    def test_cte_anisotropic_loads_as_list(self, tmp_path):
        """Sapphire / quartz have direction-dependent CTE."""
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [sapphire]
            name = "Sapphire"
            [sapphire.mechanical]
            cte_anisotropic = [5.3, 5.3, 6.2]
            """)
        )
        sap = load_toml(p)["sapphire"]
        assert sap.properties.mechanical.cte_anisotropic == [5.3, 5.3, 6.2]

    def test_creep_rate_sparse_points(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [m]
            name = "M"
            [m.mechanical]
            creep_rate = [
              { temp_K = 77, stress_MPa = 100, strain_per_hr = 1e-9 },
              { temp_K = 293, stress_MPa = 100, strain_per_hr = 5e-7 },
              { temp_K = 293, stress_MPa = 200, strain_per_hr = 8e-6 },
            ]
            """)
        )
        m = load_toml(p)["m"]
        cr = m.properties.mechanical.creep_rate
        assert isinstance(cr, list)
        assert len(cr) == 3
        assert cr[0] == {"temp_K": 77, "stress_MPa": 100, "strain_per_hr": 1e-9}

    def test_cti_loads(self, tmp_path):
        """CTI for PCB substrate selection (V)."""
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [fr4]
            name = "FR4"
            [fr4.mechanical]
            cti_value = 175
            cti_unit = "V"
            """)
        )
        fr4 = load_toml(p)["fr4"]
        assert fr4.properties.mechanical.cti == 175

    def test_pint_qty_for_new_scalars(self, tmp_path):
        """The `*_qty` accessors should also work for the new scalar fields."""
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [m]
            name = "M"
            [m.mechanical]
            flexural_modulus_value = 3500
            flexural_modulus_unit = "MPa"
            fatigue_limit_value = 200
            fatigue_limit_unit = "MPa"
            cti_value = 175
            cti_unit = "V"
            """)
        )
        m = load_toml(p)["m"]
        assert m.properties.mechanical.flexural_modulus_qty.to("MPa").magnitude == 3500
        assert m.properties.mechanical.fatigue_limit_qty.to("MPa").magnitude == 200
        assert m.properties.mechanical.cti_qty.to("V").magnitude == 175


class TestRegression:
    def test_full_corpus_loads(self):
        """Adding new fields must not break loading any shipped TOML."""
        from pymat import _CATEGORY_BASES
        from pymat.loader import load_category

        for cat in _CATEGORY_BASES:
            mats = load_category(cat)
            assert mats, f"category {cat} loaded empty"

    def test_existing_density_unchanged(self, tmp_path):
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
        assert steel.properties.mechanical.density == 7.85
