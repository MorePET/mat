"""Tests for #152 — thermal sub-table additions.

Pure additive: 7 new optional fields on `ThermalProperties` for
cryogenic + coolant work.
"""

from __future__ import annotations

from textwrap import dedent

from pymat.loader import load_toml


class TestNewThermalFields:
    def test_emissivity_loads(self, tmp_path):
        """Critical for cryogenic radiation shielding budgets."""
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [polished_al]
            name = "Polished Al"
            [polished_al.thermal]
            emissivity = 0.04
            """)
        )
        m = load_toml(p)["polished_al"]
        assert m.properties.thermal.emissivity == 0.04

    def test_thermal_diffusivity_loads(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [m]
            name = "M"
            [m.thermal]
            thermal_diffusivity_value = 97
            thermal_diffusivity_unit = "mm^2/s"
            """)
        )
        m = load_toml(p)["m"]
        assert m.properties.thermal.thermal_diffusivity == 97

    def test_min_use_temp_K_and_cryogenic_compat(self, tmp_path):
        """Delrin/PEEK get brittle below ~-50 °C; track that explicitly."""
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [delrin]
            name = "Delrin"
            [delrin.thermal]
            min_use_temp_K = 223
            cryogenic_compatible = false

            [peek]
            name = "PEEK"
            [peek.thermal]
            min_use_temp_K = 4
            cryogenic_compatible = true
            """)
        )
        mats = load_toml(p)
        assert mats["delrin"].properties.thermal.min_use_temp_K == 223
        assert mats["delrin"].properties.thermal.cryogenic_compatible is False
        assert mats["peek"].properties.thermal.cryogenic_compatible is True

    def test_integrated_thermal_conductivity_loads(self, tmp_path):
        """NIST-style ∫k dT for cryogenic heat-leak calculations."""
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [m]
            name = "M"
            [m.thermal]
            integrated_thermal_conductivity_value = 1430
            integrated_thermal_conductivity_unit = "W/m"
            """)
        )
        m = load_toml(p)["m"]
        assert m.properties.thermal.integrated_thermal_conductivity == 1430

    def test_latent_heats_load(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [ln2]
            name = "Liquid N2"
            [ln2.thermal]
            latent_heat_fusion_value = 25.7
            latent_heat_fusion_unit = "kJ/kg"
            latent_heat_vaporization_value = 199
            latent_heat_vaporization_unit = "kJ/kg"
            """)
        )
        m = load_toml(p)["ln2"]
        assert m.properties.thermal.latent_heat_fusion == 25.7
        assert m.properties.thermal.latent_heat_vaporization == 199

    def test_pint_qty_for_new_dimensional_fields(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [m]
            name = "M"
            [m.thermal]
            thermal_diffusivity_value = 97
            thermal_diffusivity_unit = "mm^2/s"
            integrated_thermal_conductivity_value = 1430
            integrated_thermal_conductivity_unit = "W/m"
            latent_heat_fusion_value = 25.7
            latent_heat_fusion_unit = "kJ/kg"
            latent_heat_vaporization_value = 199
            latent_heat_vaporization_unit = "kJ/kg"
            """)
        )
        m = load_toml(p)["m"]
        t = m.properties.thermal
        assert t.thermal_diffusivity_qty.to("mm^2/s").magnitude == 97
        assert t.integrated_thermal_conductivity_qty.to("W/m").magnitude == 1430
        assert t.latent_heat_fusion_qty.to("kJ/kg").magnitude == 25.7
        assert t.latent_heat_vaporization_qty.to("kJ/kg").magnitude == 199


class TestRegression:
    def test_full_corpus_loads(self):
        from pymat import _CATEGORY_BASES
        from pymat.loader import load_category

        for cat in _CATEGORY_BASES:
            mats = load_category(cat)
            assert mats, f"category {cat} loaded empty"
