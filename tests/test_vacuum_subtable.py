"""Tests for #156 — new `[<material>.vacuum]` sub-table.

UHV detector enclosures + Geant4 vacuum modeling. Particularly relevant
for PEEK, Delrin, Viton, Kapton, all elastomers, epoxies.
"""

from __future__ import annotations

from textwrap import dedent

from pymat.loader import load_toml


class TestVacuumSubtable:
    def test_outgassing_rates_load(self, tmp_path):
        """Two named fields for the 1h/10h pumping snapshots — sparse, named beats list."""
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [peek]
            name = "PEEK"
            [peek.vacuum]
            outgassing_rate_1h = 5e-6
            outgassing_rate_10h = 8e-7
            """)
        )
        m = load_toml(p)["peek"]
        assert m.properties.vacuum.outgassing_rate_1h == 5e-6
        assert m.properties.vacuum.outgassing_rate_10h == 8e-7

    def test_astm_e595_fields(self, tmp_path):
        """TML and CVCM per ASTM E595 / NASA spec."""
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [delrin]
            name = "Delrin"
            [delrin.vacuum]
            tml_pct = 1.5
            cvcm_pct = 0.05
            """)
        )
        m = load_toml(p)["delrin"]
        assert m.properties.vacuum.tml_pct == 1.5
        assert m.properties.vacuum.cvcm_pct == 0.05

    def test_bakeout_and_permeation(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [kapton]
            name = "Kapton"
            [kapton.vacuum]
            bakeout_temp_max_C = 200
            permeation_he = 1.2e-9
            """)
        )
        m = load_toml(p)["kapton"]
        assert m.properties.vacuum.bakeout_temp_max_C == 200
        assert m.properties.vacuum.permeation_he == 1.2e-9

    def test_vacuum_class_string(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [m]
            name = "M"
            [m.vacuum]
            vacuum_class = "UHV"
            """)
        )
        m = load_toml(p)["m"]
        assert m.properties.vacuum.vacuum_class == "UHV"

    def test_inheritance(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [base]
            name = "Base"
            [base.vacuum]
            vacuum_class = "HV"
            tml_pct = 0.5

            [base.aged]
            name = "Aged"
            [base.aged.vacuum]
            tml_pct = 1.2
            """)
        )
        mats = load_toml(p)
        # Inherits vacuum_class, overrides tml_pct
        assert mats["base"].aged.properties.vacuum.vacuum_class == "HV"
        assert mats["base"].aged.properties.vacuum.tml_pct == 1.2

    def test_full_corpus_loads(self):
        from pymat import _CATEGORY_BASES
        from pymat.loader import load_category

        for cat in _CATEGORY_BASES:
            mats = load_category(cat)
            assert mats, f"category {cat} loaded empty"
