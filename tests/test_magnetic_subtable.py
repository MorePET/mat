"""Tests for #155 — new `[<material>.magnetic]` sub-table.

Required for MR-PET hybrid systems (need χ < ~10 ppm for null artifacts).
3 fields: susceptibility_volumetric (χ_v, SI, dimensionless),
permeability_relative (μr), saturation_field (T, ferromagnetics only).
"""

from __future__ import annotations

from textwrap import dedent

from pymat.loader import load_toml


class TestMagneticSubtable:
    def test_diamagnetic_copper(self, tmp_path):
        """Cu: χ_v ≈ -9.6e-6 (diamagnetic). Required for MR-PET cryostats."""
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [copper]
            name = "Copper"
            [copper.magnetic]
            susceptibility_volumetric = -9.6e-6
            permeability_relative = 0.999990
            """)
        )
        cu = load_toml(p)["copper"]
        assert cu.properties.magnetic.susceptibility_volumetric == -9.6e-6
        assert cu.properties.magnetic.permeability_relative == 0.999990

    def test_ferromagnetic_mu_metal(self, tmp_path):
        """Mu-metal: μr ≈ 20000, saturation around 0.8 T."""
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [mumetal]
            name = "Mu-metal"
            [mumetal.magnetic]
            permeability_relative = 20000
            saturation_field_value = 0.8
            saturation_field_unit = "T"
            """)
        )
        mu = load_toml(p)["mumetal"]
        assert mu.properties.magnetic.permeability_relative == 20000
        assert mu.properties.magnetic.saturation_field == 0.8

    def test_pint_qty_for_saturation(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [m]
            name = "M"
            [m.magnetic]
            saturation_field_value = 1.6
            saturation_field_unit = "T"
            """)
        )
        m = load_toml(p)["m"]
        assert m.properties.magnetic.saturation_field_qty.to("T").magnitude == 1.6

    def test_inheritance_through_magnetic(self, tmp_path):
        """Children inherit parent magnetic block, can override."""
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [iron]
            name = "Iron"
            [iron.magnetic]
            permeability_relative = 5000

            [iron.cold_rolled]
            name = "Iron — cold rolled"
            [iron.cold_rolled.magnetic]
            permeability_relative = 1500
            """)
        )
        mats = load_toml(p)
        assert mats["iron"].properties.magnetic.permeability_relative == 5000
        assert mats["iron"].cold_rolled.properties.magnetic.permeability_relative == 1500

    def test_full_corpus_loads(self):
        from pymat import _CATEGORY_BASES
        from pymat.loader import load_category

        for cat in _CATEGORY_BASES:
            mats = load_category(cat)
            assert mats, f"category {cat} loaded empty"

    def test_default_magnetic_is_empty(self, tmp_path):
        """A material with no [magnetic] block still gets a MagneticProperties()."""
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
        assert steel.properties.magnetic.susceptibility_volumetric is None
        assert steel.properties.magnetic.permeability_relative is None
        assert steel.properties.magnetic.saturation_field is None
