"""Tests for #243 — `WavelengthCurve` and the wavelength accessors.

Per ADR-0004 §4:
- New `WavelengthCurve` in `pymat.curves`, mirroring `TempCurve`: piecewise
  linear, clamp-outside-range, validated at construction and therefore at load.
- New structured optical slots: `absorption_length_spectrum`, the
  `_matrix`/`_reabs` self-absorption split, `reemit_qe`, `reflectivity`.
- New accessors `n_at`, `absorption_length_at`, `emission_at`,
  `absorption_length_matrix_at`, `absorption_length_reabs_at` — spectrum
  beats scalar, and they take a Pint Quantity or bare nm.
- `refractive_index_at(T)` keeps meaning temperature. That is the whole
  reason the wavelength accessors got different names.
"""

from __future__ import annotations

from textwrap import dedent

import pytest

from pymat.curves import TempCurve, WavelengthCurve
from pymat.loader import load_toml
from pymat.properties import OpticalProperties
from pymat.units import ureg


class TestWavelengthCurveInterpolation:
    def test_exact_knot_returns_knot_value(self):
        c = WavelengthCurve(wavelengths_nm=[400, 500, 600], values=[1.0, 2.0, 3.0])
        assert c.interpolate(500.0) == pytest.approx(2.0)

    def test_between_knots_linear_interp(self):
        c = WavelengthCurve(wavelengths_nm=[400, 500], values=[1.0, 2.0])
        assert c.interpolate(450.0) == pytest.approx(1.5)

    def test_below_min_clamps(self):
        c = WavelengthCurve(wavelengths_nm=[400, 500], values=[1.8, 1.7])
        assert c.interpolate(250.0) == 1.8

    def test_above_max_clamps(self):
        c = WavelengthCurve(wavelengths_nm=[400, 500], values=[1.8, 1.7])
        assert c.interpolate(900.0) == 1.7

    def test_single_point_curve_returns_constant(self):
        c = WavelengthCurve(wavelengths_nm=[420.0], values=[1.82])
        assert c.interpolate(300.0) == 1.82
        assert c.interpolate(420.0) == 1.82
        assert c.interpolate(800.0) == 1.82

    def test_range_nm_reports_measured_span(self):
        c = WavelengthCurve(wavelengths_nm=[400, 500, 600], values=[1, 2, 3])
        assert c.range_nm == (400, 600)

    def test_clamping_is_visible_via_range(self):
        """A consumer must be able to tell it got a clamped value.

        The curve never raises out-of-range — it clamps, per ADR-0003 §2 — so
        `range_nm` is the only way a resampler can know where the data stops.
        """
        c = WavelengthCurve(wavelengths_nm=[400, 600], values=[1.0, 2.0])
        lo, hi = c.range_nm
        assert c.interpolate(300) == c.interpolate(lo)
        assert c.interpolate(900) == c.interpolate(hi)


class TestWavelengthCurveValidation:
    def test_unsorted_raises_at_construction(self):
        with pytest.raises(ValueError, match="sorted"):
            WavelengthCurve(wavelengths_nm=[500, 400, 600], values=[1.0, 2.0, 3.0])

    def test_equal_adjacent_knots_raise(self):
        with pytest.raises(ValueError, match="sorted"):
            WavelengthCurve(wavelengths_nm=[400, 400], values=[1.0, 2.0])

    def test_mismatched_lengths_raise(self):
        with pytest.raises(ValueError, match="length"):
            WavelengthCurve(wavelengths_nm=[400, 500, 600], values=[1.0, 2.0])

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="at least one"):
            WavelengthCurve(wavelengths_nm=[], values=[])


class TestWavelengthCurveFromToml:
    """The on-disk shapes predate this primitive, so `from_toml` has to accept
    all three value-column spellings that #153 / #164 already wrote."""

    def test_canonical_values_column(self):
        c = WavelengthCurve.from_toml({"wavelengths_nm": [400, 500], "values": [1.0, 2.0]})
        assert c.interpolate(450) == pytest.approx(1.5)

    def test_dispersion_n_column(self):
        c = WavelengthCurve.from_toml({"wavelengths_nm": [400, 500], "n": [1.9, 1.8]})
        assert c.interpolate(400) == 1.9

    def test_emission_intensities_column(self):
        c = WavelengthCurve.from_toml({"wavelengths_nm": [400, 500], "intensities": [0.5, 1.0]})
        assert c.interpolate(500) == 1.0

    def test_explicit_value_key_wins(self):
        raw = {"wavelengths_nm": [400, 500], "n": [1.9, 1.8], "k": [0.1, 0.2]}
        c = WavelengthCurve.from_toml(raw, value_key="k")
        assert c.interpolate(400) == 0.1

    def test_ambiguous_columns_raise(self):
        """Two value columns must not be silently disambiguated — the file's
        meaning would then depend on this function's internal ordering."""
        raw = {"wavelengths_nm": [400, 500], "values": [1, 2], "n": [3, 4]}
        with pytest.raises(ValueError, match="ambiguous"):
            WavelengthCurve.from_toml(raw)

    def test_missing_value_column_raises(self):
        with pytest.raises(ValueError, match="no value column"):
            WavelengthCurve.from_toml({"wavelengths_nm": [400, 500]})

    def test_missing_wavelengths_raises(self):
        with pytest.raises(ValueError, match="wavelengths_nm"):
            WavelengthCurve.from_toml({"values": [1, 2]})

    def test_non_table_raises(self):
        with pytest.raises(ValueError, match="must be a table"):
            WavelengthCurve.from_toml([1, 2, 3])

    def test_missing_explicit_value_key_raises(self):
        with pytest.raises(ValueError, match="'k'"):
            WavelengthCurve.from_toml({"wavelengths_nm": [400], "n": [1.8]}, value_key="k")


class TestTempCurveUnchanged:
    """The shared-helper refactor must not have moved TempCurve's behaviour."""

    def test_interpolation_still_works(self):
        c = TempCurve(temps_K=[100, 200, 300], values=[1.0, 2.0, 3.0])
        assert c.interpolate(150) == pytest.approx(1.5)
        assert c.interpolate(50) == 1.0
        assert c.interpolate(400) == 3.0

    def test_validation_messages_unchanged(self):
        with pytest.raises(ValueError, match="sorted"):
            TempCurve(temps_K=[300, 100], values=[1.0, 2.0])
        with pytest.raises(ValueError, match="length"):
            TempCurve(temps_K=[100, 200], values=[1.0])
        with pytest.raises(ValueError, match="at least one"):
            TempCurve(temps_K=[], values=[])


class TestWavelengthUnits:
    def test_bare_float_is_nanometres(self):
        opt = OpticalProperties(
            refractive_index_dispersion={"wavelengths_nm": [400, 500], "n": [1.9, 1.8]}
        )
        assert opt.n_at(400) == 1.9

    def test_pint_quantity_accepted(self):
        opt = OpticalProperties(
            refractive_index_dispersion={"wavelengths_nm": [400, 500], "n": [1.9, 1.8]}
        )
        assert opt.n_at(400 * ureg.nm) == 1.9

    def test_quantity_is_converted_not_stripped(self):
        """0.4 um is 400 nm. If the magnitude were taken bare it would clamp low."""
        opt = OpticalProperties(
            refractive_index_dispersion={"wavelengths_nm": [400, 500], "n": [1.9, 1.8]}
        )
        assert opt.n_at(0.4 * ureg.micrometer) == pytest.approx(1.9)
        assert opt.n_at(0.5 * ureg.micrometer) == pytest.approx(1.8)

    def test_non_length_quantity_raises(self):
        opt = OpticalProperties(refractive_index=1.8)
        with pytest.raises(ValueError, match="must be a length"):
            opt.n_at(300 * ureg.kelvin)


class TestOpticalWavelengthAccessors:
    def test_n_at_prefers_dispersion_over_scalar(self):
        opt = OpticalProperties(
            refractive_index=1.5,
            refractive_index_dispersion={"wavelengths_nm": [400, 500], "n": [1.9, 1.8]},
        )
        assert opt.n_at(400) == 1.9

    def test_n_at_falls_back_to_scalar(self):
        assert OpticalProperties(refractive_index=1.82).n_at(420) == 1.82

    def test_n_at_returns_none_when_nothing_set(self):
        assert OpticalProperties().n_at(420) is None

    def test_absorption_length_at_carries_units(self):
        opt = OpticalProperties(absorption_length=200.0)
        q = opt.absorption_length_at(420)
        assert q.magnitude == 200.0
        assert q.units == ureg.mm

    def test_absorption_length_spectrum_beats_scalar(self):
        opt = OpticalProperties(
            absorption_length=200.0,
            absorption_length_spectrum={"wavelengths_nm": [400, 500], "values": [50.0, 150.0]},
        )
        assert opt.absorption_length_at(450).magnitude == pytest.approx(100.0)

    def test_self_absorption_channels_are_independent(self):
        opt = OpticalProperties(
            absorption_length_matrix=1200.0,
            absorption_length_reabs=588.0,
            reemit_qe=0.75,
        )
        assert opt.absorption_length_matrix_at(420).magnitude == 1200.0
        assert opt.absorption_length_reabs_at(420).magnitude == 588.0
        assert opt.reemit_qe == 0.75

    def test_absent_channel_returns_none_not_zero(self):
        """A missing channel must be None. Zero would read as 'absorbs
        instantly', which is the opposite of 'we have no measurement'."""
        opt = OpticalProperties(absorption_length_reabs=588.0)
        assert opt.absorption_length_matrix_at(420) is None

    def test_emission_at_has_no_scalar_fallback(self):
        """`emission_peak` is one point on a band, not its shape (ADR-0004 §4)."""
        opt = OpticalProperties(emission_peak=420)
        assert opt.emission_at(420) is None

    def test_emission_at_uses_spectrum(self):
        opt = OpticalProperties(
            emission_spectrum={"wavelengths_nm": [400, 420, 500], "intensities": [0.2, 1.0, 0.3]}
        )
        assert opt.emission_at(420) == 1.0
        assert opt.emission_at(410) == pytest.approx(0.6)

    def test_curve_properties_expose_wavelength_curves(self):
        opt = OpticalProperties(
            refractive_index_dispersion={"wavelengths_nm": [400, 500], "n": [1.9, 1.8]},
            emission_spectrum={"wavelengths_nm": [400, 500], "intensities": [0.5, 1.0]},
            absorption_length_spectrum={"wavelengths_nm": [400, 500], "values": [10, 20]},
        )
        assert isinstance(opt.refractive_index_dispersion_curve, WavelengthCurve)
        assert isinstance(opt.emission_spectrum_curve, WavelengthCurve)
        assert isinstance(opt.absorption_length_curve, WavelengthCurve)
        assert opt.refractive_index_dispersion_curve.range_nm == (400, 500)

    def test_curve_properties_are_none_when_slot_empty(self):
        opt = OpticalProperties()
        assert opt.refractive_index_dispersion_curve is None
        assert opt.emission_spectrum_curve is None
        assert opt.absorption_length_curve is None


class TestTemperatureAccessorNotBroken:
    """The reason the wavelength accessors are named `n_at` and not
    `refractive_index_at` overloaded on type."""

    def test_refractive_index_at_still_means_temperature(self):
        opt = OpticalProperties(
            refractive_index=1.82,
            refractive_index_curve=TempCurve(temps_K=[250, 350], values=[1.83, 1.81]),
        )
        assert opt.refractive_index_at(300 * ureg.kelvin) == pytest.approx(1.82)

    def test_the_two_axes_do_not_interfere(self):
        opt = OpticalProperties(
            refractive_index=1.82,
            refractive_index_curve=TempCurve(temps_K=[250, 350], values=[1.83, 1.81]),
            refractive_index_dispersion={"wavelengths_nm": [400, 500], "n": [1.90, 1.80]},
        )
        assert opt.refractive_index_at(250 * ureg.kelvin) == pytest.approx(1.83)
        assert opt.n_at(400) == pytest.approx(1.90)


class TestLoadTimeValidation:
    """ADR-0004 §4: a malformed spectrum raises at load, not at first query."""

    def _write(self, tmp_path, body):
        p = tmp_path / "m.toml"
        p.write_text(dedent(body))
        return p

    def test_mismatched_spectrum_raises_at_load(self, tmp_path):
        p = self._write(
            tmp_path,
            """
            [x]
            name = "X"
            [x.optical]
            emission_spectrum = { wavelengths_nm = [400, 500, 600], intensities = [1.0, 2.0] }
            """,
        )
        with pytest.raises(ValueError, match="emission_spectrum"):
            load_toml(p)

    def test_unsorted_dispersion_raises_at_load(self, tmp_path):
        p = self._write(
            tmp_path,
            """
            [x]
            name = "X"
            [x.optical]
            refractive_index_dispersion = { wavelengths_nm = [500, 400], n = [1.8, 1.9] }
            """,
        )
        with pytest.raises(ValueError, match="sorted"):
            load_toml(p)

    def test_valid_spectrum_round_trips_and_stays_a_dict(self, tmp_path):
        """Storage is unchanged — the dataclass field stays a plain dict so the
        JSON round-trip in the MCP client keeps working (ADR-0004 §4)."""
        p = self._write(
            tmp_path,
            """
            [x]
            name = "X"
            [x.optical]
            absorption_length_spectrum = { wavelengths_nm = [400, 500], values = [10.0, 20.0] }
            """,
        )
        mats = load_toml(p)
        opt = mats["x"].properties.optical
        assert isinstance(opt.absorption_length_spectrum, dict)
        assert opt.absorption_length_at(450).magnitude == pytest.approx(15.0)


class TestRecoveredSilentDrops:
    """Fields that existed on disk with no dataclass slot to land in, so the
    loader's `hasattr` guard dropped them on every load (ADR-0004 §8)."""

    def test_esr_reflectivity_now_loads(self):
        import pymat

        assert pymat.esr.properties.optical.reflectivity == 98.5

    def test_scintillator_dopant_now_loads(self):
        import pymat

        assert pymat.lyso.Ce.properties.optical.dopant == "Ce"
        assert pymat.lyso.Ce.properties.optical.dopant_pct == 0.1
        assert pymat.nai.Tl.properties.optical.dopant == "Tl"

    def test_compliance_hazards_now_load(self):
        import pymat

        assert pymat.hydrogen.properties.compliance.flammable is True
        assert pymat.beryllia.properties.compliance.toxic is True

    def test_ferrite_permeability_moved_to_magnetic(self):
        import pymat

        assert pymat.materials["ferrite"].properties.magnetic.permeability_relative == 100

    def test_no_data_file_key_is_silently_dropped(self):
        """Regression net for the whole bug class: every key in every material
        TOML must have a field to land in."""
        import pathlib
        import sys

        if sys.version_info >= (3, 11):
            import tomllib
        else:  # pragma: no cover
            import tomli as tomllib

        from pymat.properties import AllProperties

        groups = {
            "mechanical",
            "thermal",
            "electrical",
            "optical",
            "magnetic",
            "vacuum",
            "nuclear",
            "manufacturing",
            "compliance",
            "sourcing",
        }
        props = AllProperties()
        dropped: dict[str, list[str]] = {}

        def walk(node, path):
            if not isinstance(node, dict):
                return
            for k, v in node.items():
                if k.startswith("_"):
                    continue
                if k in groups and isinstance(v, dict):
                    obj = getattr(props, k)
                    for pk in v:
                        if pk.startswith("_") or pk.endswith(("_stddev", "_unit")):
                            continue
                        base = pk[:-6] if pk.endswith("_value") else pk
                        if not hasattr(obj, base):
                            dropped.setdefault(f"{k}.{base}", []).append(path)
                elif isinstance(v, dict) and k not in ("vis", "custom"):
                    walk(v, f"{path}.{k}")

        data_dir = pathlib.Path(__file__).resolve().parent.parent / "src" / "pymat" / "data"
        for toml_path in sorted(data_dir.glob("*.toml")):
            if toml_path.name == "surfaces.toml":  # not a material catalogue
                continue
            with open(toml_path, "rb") as f:
                doc = tomllib.load(f)
            for k, v in doc.items():
                walk(v, f"{toml_path.stem}:{k}")

        assert not dropped, (
            "TOML keys with no dataclass field to receive them — the loader "
            f"drops these silently on every load: {dropped}"
        )


class TestMalformedSlotRaisesAtLoad:
    """A scalar written where a spectrum belongs must fail at load.

    Guarding validation on `isinstance(value, dict)` let a scalar skip the
    check entirely and land in a dict-typed field, deferring the failure to the
    first `_at(lambda)` call — far from the file that caused it. Found in
    review of #243.
    """

    def test_scalar_in_a_spectrum_slot_raises(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent(
                """
                [x]
                name = "X"
                [x.optical]
                emission_spectrum = 420.0
                """
            )
        )
        with pytest.raises(ValueError, match="must be a table"):
            load_toml(p)

    def test_list_in_a_spectrum_slot_raises(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent(
                """
                [x]
                name = "X"
                [x.optical]
                refractive_index_dispersion = [400, 500]
                """
            )
        )
        with pytest.raises(ValueError, match="must be a table"):
            load_toml(p)


class TestEmissionAtIsSymmetricOnBadInput:
    """`emission_at` validated its argument only when a spectrum existed, so
    the same bad call returned None on one material and raised on the next."""

    def test_raises_without_a_spectrum(self):
        opt = OpticalProperties(emission_peak=420)
        with pytest.raises(ValueError, match="must be a length"):
            opt.emission_at(300 * ureg.kelvin)

    def test_raises_with_a_spectrum(self):
        opt = OpticalProperties(
            emission_spectrum={"wavelengths_nm": [400, 500], "intensities": [0.5, 1.0]}
        )
        with pytest.raises(ValueError, match="must be a length"):
            opt.emission_at(300 * ureg.kelvin)
