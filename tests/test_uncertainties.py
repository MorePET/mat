"""Tests for uncertainty/range support in composition and scalar values."""

from __future__ import annotations

from uncertainties import UFloat, ufloat

from pymat.loader import _parse_composition, _parse_value


class TestParseValue:
    def test_plain_float(self):
        assert _parse_value(0.5) == 0.5
        assert isinstance(_parse_value(0.5), float)

    def test_plain_int(self):
        assert _parse_value(1) == 1.0

    def test_dict_with_stddev(self):
        v = _parse_value({"nominal": 0.4, "stddev": 0.1})
        assert isinstance(v, UFloat)
        assert v.nominal_value == 0.4
        assert v.std_dev == 0.1

    def test_dict_with_range(self):
        v = _parse_value({"min": 0.2, "max": 0.6})
        assert isinstance(v, UFloat)
        assert v.nominal_value == 0.4  # midpoint
        assert abs(v.std_dev - 0.2) < 1e-10  # half-range

    def test_dict_with_nominal_and_range(self):
        v = _parse_value({"nominal": 0.35, "min": 0.2, "max": 0.6})
        assert isinstance(v, UFloat)
        assert v.nominal_value == 0.35  # explicit nominal, not midpoint
        assert abs(v.std_dev - 0.2) < 1e-10

    def test_dict_nominal_only(self):
        v = _parse_value({"nominal": 0.5})
        assert v == 0.5
        assert isinstance(v, float)  # no uncertainty info → plain float

    def test_dict_max_only(self):
        # {nominal = 0.05, max = 0.1} — common for trace elements
        v = _parse_value({"nominal": 0.05, "max": 0.1})
        assert v == 0.05  # no min → no range → plain float


class TestParseComposition:
    def test_none(self):
        assert _parse_composition(None) is None

    def test_plain_dict(self):
        comp = _parse_composition({"Fe": 0.68, "Cr": 0.18})
        assert comp["Fe"] == 0.68
        assert isinstance(comp["Fe"], float)

    def test_mixed_dict(self):
        comp = _parse_composition(
            {
                "Fe": 0.68,
                "Si": {"min": 0.2, "max": 0.6},
                "Cr": {"nominal": 0.18, "stddev": 0.02},
            }
        )
        assert isinstance(comp["Fe"], float)
        assert isinstance(comp["Si"], UFloat)
        assert isinstance(comp["Cr"], UFloat)
        assert comp["Si"].nominal_value == 0.4
        assert comp["Cr"].std_dev == 0.02


class TestUncertaintyPropagation:
    def test_ufloat_sum(self):
        """Summing ufloats propagates uncertainty correctly."""
        a = ufloat(0.4, 0.1)
        b = ufloat(0.6, 0.2)
        total = a + b
        assert total.nominal_value == 1.0
        # Uncertainty adds in quadrature
        assert abs(total.std_dev - (0.1**2 + 0.2**2) ** 0.5) < 1e-10

    def test_ufloat_mixed_with_float(self):
        """ufloat + plain float works."""
        a = ufloat(0.4, 0.1)
        b = 0.5
        total = a + b
        assert total.nominal_value == 0.9
        assert total.std_dev == 0.1  # float adds zero uncertainty


class TestMaterialWithRanges:
    def test_a6063_has_ufloat_composition(self):
        from pymat import aluminum

        a6063 = aluminum.a6063
        assert a6063.composition is not None

        # Si has a range
        si = a6063.composition["Si"]
        assert isinstance(si, UFloat)
        assert si.nominal_value > 0

        # Al is plain float (balance)
        al = a6063.composition["Al"]
        assert isinstance(al, float)

    def test_a6061_still_plain_floats(self):
        """Existing plain-float compositions are unaffected."""
        from pymat import aluminum

        a6061 = aluminum.a6061
        for el, val in a6061.composition.items():
            assert isinstance(val, float), f"{el} should be float, got {type(val)}"
