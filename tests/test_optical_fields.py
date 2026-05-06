"""Tests for #153 — optical sub-table additions (scintillator-heavy).

Mostly additive scalars + 3 structured fields:
- decay_components — list[{tau_ns, fraction}] for multi-component decay
- emission_spectrum — {wavelengths_nm, intensities} for SiPM PDE matching
- refractive_index_dispersion — {wavelengths_nm, n} Sellmeier-style

Geant4 ray-tracing currently has zero data here; this PR makes the schema
ready to ingest it (data populates in Phase 4 via refractiveindex.info etc.).
"""

from __future__ import annotations

from textwrap import dedent

from pymat.loader import load_toml


class TestOpticalScalars:
    def test_scattering_and_rayleigh_lengths(self, tmp_path):
        """Geant4 scintillator block needs both."""
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [lyso]
            name = "LYSO"
            [lyso.optical]
            scattering_length_value = 50
            scattering_length_unit = "cm"
            rayleigh_length_value = 100
            rayleigh_length_unit = "cm"
            """)
        )
        m = load_toml(p)["lyso"]
        assert m.properties.optical.scattering_length == 50
        assert m.properties.optical.rayleigh_length == 100

    def test_afterglow_loads(self, tmp_path):
        """Count-rate ceiling — fraction of light still emitted at 3ms / 100ms."""
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [csi_tl]
            name = "CsI:Tl"
            [csi_tl.optical]
            afterglow_pct_at_3ms = 0.5
            afterglow_pct_at_100ms = 0.05
            """)
        )
        m = load_toml(p)["csi_tl"]
        assert m.properties.optical.afterglow_pct_at_3ms == 0.5
        assert m.properties.optical.afterglow_pct_at_100ms == 0.05

    def test_non_proportionality_and_resolution(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [m]
            name = "M"
            [m.optical]
            non_proportionality = 4.5
            intrinsic_resolution_pct_at_662keV = 3.5
            """)
        )
        m = load_toml(p)["m"]
        assert m.properties.optical.non_proportionality == 4.5
        assert m.properties.optical.intrinsic_resolution_pct_at_662keV == 3.5

    def test_temperature_coefficient_light_yield(self, tmp_path):
        """LYSO ~+0.4%/K downward from 20°C (so cryo gives ~+15% by -40°C)."""
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [lyso]
            name = "LYSO"
            [lyso.optical]
            temperature_coefficient_light_yield = -0.4
            """)
        )
        m = load_toml(p)["lyso"]
        assert m.properties.optical.temperature_coefficient_light_yield == -0.4

    def test_hygroscopic_bool(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [nai_tl]
            name = "NaI:Tl"
            [nai_tl.optical]
            hygroscopic = true

            [bgo]
            name = "BGO"
            [bgo.optical]
            hygroscopic = false
            """)
        )
        mats = load_toml(p)
        assert mats["nai_tl"].properties.optical.hygroscopic is True
        assert mats["bgo"].properties.optical.hygroscopic is False


class TestOpticalStructured:
    def test_decay_components_list(self, tmp_path):
        """LYSO has fast (~36 ns) + slow (~600 ns) decay components."""
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [lyso]
            name = "LYSO"
            [lyso.optical]
            decay_components = [
              { tau_ns = 36, fraction = 0.85 },
              { tau_ns = 600, fraction = 0.15 },
            ]
            """)
        )
        m = load_toml(p)["lyso"]
        comps = m.properties.optical.decay_components
        assert isinstance(comps, list)
        assert len(comps) == 2
        assert comps[0] == {"tau_ns": 36, "fraction": 0.85}

    def test_emission_spectrum_dict(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [lyso]
            name = "LYSO"
            [lyso.optical.emission_spectrum]
            wavelengths_nm = [380, 400, 420, 440, 460]
            intensities = [0.1, 0.6, 1.0, 0.7, 0.3]
            """)
        )
        m = load_toml(p)["lyso"]
        s = m.properties.optical.emission_spectrum
        assert s == {
            "wavelengths_nm": [380, 400, 420, 440, 460],
            "intensities": [0.1, 0.6, 1.0, 0.7, 0.3],
        }

    def test_refractive_index_dispersion_dict(self, tmp_path):
        """Sellmeier-style dispersion for Geant4 ray tracing."""
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [sapphire]
            name = "Sapphire"
            [sapphire.optical.refractive_index_dispersion]
            wavelengths_nm = [400, 500, 600, 700]
            n = [1.79, 1.77, 1.76, 1.75]
            """)
        )
        m = load_toml(p)["sapphire"]
        d = m.properties.optical.refractive_index_dispersion
        assert d == {
            "wavelengths_nm": [400, 500, 600, 700],
            "n": [1.79, 1.77, 1.76, 1.75],
        }


class TestPintQty:
    def test_scattering_length_qty(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [m]
            name = "M"
            [m.optical]
            scattering_length_value = 50
            scattering_length_unit = "cm"
            rayleigh_length_value = 100
            rayleigh_length_unit = "cm"
            """)
        )
        m = load_toml(p)["m"]
        assert m.properties.optical.scattering_length_qty.to("cm").magnitude == 50
        assert m.properties.optical.rayleigh_length_qty.to("cm").magnitude == 100


class TestRegression:
    def test_full_corpus_loads(self):
        from pymat import _CATEGORY_BASES
        from pymat.loader import load_category

        for cat in _CATEGORY_BASES:
            mats = load_category(cat)
            assert mats, f"category {cat} loaded empty"

    def test_existing_optical_fields_unchanged(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [lyso]
            name = "LYSO"
            [lyso.optical]
            light_yield = 33000
            decay_time = 36
            refractive_index = 1.82
            """)
        )
        lyso = load_toml(p)["lyso"]
        assert lyso.properties.optical.light_yield == 33000
        assert lyso.properties.optical.decay_time == 36
        assert lyso.properties.optical.refractive_index == 1.82
