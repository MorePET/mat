"""Tests for #154 — electrical sub-table additions.

Pure additive: 2 new optional fields on `ElectricalProperties`.
- `surface_resistivity` (Ω/sq) — distinct from volume_resistivity
- `arc_resistance` (s) — HV detector feedthroughs
"""

from __future__ import annotations

from textwrap import dedent

from pymat.loader import load_toml


class TestNewElectricalFields:
    def test_surface_resistivity_loads(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [m]
            name = "M"
            [m.electrical]
            surface_resistivity_value = 1e12
            surface_resistivity_unit = "ohm"
            """)
        )
        m = load_toml(p)["m"]
        assert m.properties.electrical.surface_resistivity == 1e12

    def test_arc_resistance_loads(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [m]
            name = "M"
            [m.electrical]
            arc_resistance_value = 180
            arc_resistance_unit = "s"
            """)
        )
        m = load_toml(p)["m"]
        assert m.properties.electrical.arc_resistance == 180

    def test_pint_qty(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [m]
            name = "M"
            [m.electrical]
            surface_resistivity_value = 1e12
            surface_resistivity_unit = "ohm"
            arc_resistance_value = 180
            arc_resistance_unit = "s"
            """)
        )
        m = load_toml(p)["m"]
        assert m.properties.electrical.surface_resistivity_qty.to("ohm").magnitude == 1e12
        assert m.properties.electrical.arc_resistance_qty.to("s").magnitude == 180

    def test_full_corpus_loads(self):
        from pymat import _CATEGORY_BASES
        from pymat.loader import load_category

        for cat in _CATEGORY_BASES:
            mats = load_category(cat)
            assert mats, f"category {cat} loaded empty"
