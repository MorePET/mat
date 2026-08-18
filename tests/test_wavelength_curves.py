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

import math
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
        """Regression net for the whole bug class, via the same script the
        pre-commit hook runs — one implementation, so the hook and the suite
        cannot disagree about the invariant."""
        import subprocess
        import sys
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        proc = subprocess.run(
            [sys.executable, str(root / "scripts" / "check_data_shape.py"), "--drop"],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr


class TestWavelengthSlotsAllHaveFields:
    """Structural guard for the silent-drop bug class, in the direction the
    corpus scan cannot see.

    `test_no_data_file_key_is_silently_dropped` only checks keys that appear in
    a shipped TOML. A slot registered for validation in the loader but never
    given a dataclass field would pass that scan (no file uses it yet) and then
    silently drop the first time someone wrote it. That happened during #243
    with `reflectivity_spectrum`.
    """

    def test_every_validated_slot_has_a_field_to_land_in(self):
        from pymat.loader import _WAVELENGTH_SLOTS

        opt = OpticalProperties()
        missing = [slot for slot in _WAVELENGTH_SLOTS if not hasattr(opt, slot)]
        assert not missing, (
            "these slots are validated by the loader but have no dataclass "
            f"field, so the value is dropped after validation: {missing}"
        )

    def test_reflectivity_spectrum_round_trips(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent(
                """
                [x]
                name = "X"
                [x.optical]
                reflectivity = 97.0
                reflectivity_spectrum = { wavelengths_nm = [400, 500], values = [99.5, 99.8] }
                """
            )
        )
        opt = load_toml(p)["x"].properties.optical
        assert opt.reflectivity_spectrum is not None
        assert opt.reflectivity_at(450) == pytest.approx(99.65)
        assert opt.reflectivity_at(200) == pytest.approx(99.5)  # clamped

    def test_reflectivity_at_falls_back_to_the_scalar(self):
        assert OpticalProperties(reflectivity=98.5).reflectivity_at(420) == 98.5
        assert OpticalProperties().reflectivity_at(420) is None


class TestKubelkaMunk:
    """K-M two-flux coefficients for diffusing media (#243).

    Added when a downstream crosstalk measurement showed a 0.2 mm BaSO4 septum
    transmits, refuting an "optically thick" conclusion that had been drawn
    from a reflectance argument.
    """

    KM = {"wavelengths_nm": [300, 500, 700], "k": [0.455, 0.100, 0.062], "s": [619.0, 572.0, 517.0]}

    def test_reproduces_pattersons_published_reflectance(self):
        """The strongest available check: these coefficients and this formula
        must reproduce the R_inf the same paper publishes. 0.9624 / 0.9815 /
        0.9846 at 300 / 500 / 700 nm."""
        opt = OpticalProperties(kubelka_munk=self.KM)
        for wl, published in ((300, 96.24), (500, 98.15), (700, 98.46)):
            assert opt.km_reflectance_infinite_at(wl) == pytest.approx(published, abs=0.01)

    def test_both_columns_are_readable(self):
        opt = OpticalProperties(kubelka_munk=self.KM)
        assert opt.km_k_at(500) == pytest.approx(0.100)
        assert opt.km_s_at(500) == pytest.approx(572.0)

    def test_absent_table_yields_none_everywhere(self):
        opt = OpticalProperties()
        assert opt.km_k_at(420) is None
        assert opt.km_reflectance_infinite_at(420) is None
        assert opt.km_transmittance_at(420, 0.02) is None

    def test_transmittance_falls_with_thickness(self):
        opt = OpticalProperties(kubelka_munk=self.KM)
        ts = [opt.km_transmittance_at(420, d) for d in (0.01, 0.02, 0.03, 0.05, 0.06)]
        assert ts == sorted(ts, reverse=True)
        assert all(0.0 < t < 100.0 for t in ts)

    def test_a_thin_layer_transmits_even_when_reflectance_has_converged(self):
        """The finding that mattered. Reflectance converging to its thick-layer
        limit does NOT mean transmission is negligible — they are different
        questions, and in a segmented detector the difference is the
        inter-crystal crosstalk channel."""
        opt = OpticalProperties(kubelka_munk=self.KM)
        t = opt.km_transmittance_at(420, 0.02)  # 0.2 mm
        assert t > 5.0, "a 0.2 mm septum is not opaque"
        # Even the vendor-recommended coating thickness still transmits.
        assert opt.km_transmittance_at(420, 0.06) > 1.0

    def test_both_columns_validate_at_load(self, tmp_path):
        """k and s are one model's parameters — a malformed `s` must raise even
        though `k` is fine, which a single-column validator would miss."""
        p = tmp_path / "m.toml"
        p.write_text(
            dedent(
                """
                [x]
                name = "X"
                [x.optical]
                kubelka_munk = { wavelengths_nm = [300, 500], k = [0.4, 0.1], s = [619.0] }
                """
            )
        )
        with pytest.raises(ValueError, match="length"):
            load_toml(p)


class TestBaSO4TwoSourceDisagreement:
    """py-mat carries two cited primaries for BaSO4 reflectance that disagree
    by 1.3-2.3 points. Both are right for their own sample; the gap is the
    packing-density sensitivity, and it is why this number ships as a bracket.
    """

    def test_the_two_routes_really_do_disagree(self):
        import pymat

        opt = pymat.baso4.properties.optical
        grum = opt.reflectivity_at(420)
        patterson = opt.km_reflectance_infinite_at(420)
        assert grum == pytest.approx(99.90, abs=0.01)
        assert patterson == pytest.approx(97.18, abs=0.05)
        assert grum > patterson

    def test_the_disagreement_is_documented_not_silent(self):
        """Carrying two inconsistent numbers is defensible. Carrying them
        without saying so is not."""
        import pymat

        note = pymat.baso4.source_of("optical.kubelka_munk").note
        assert "TWO-SOURCE DISAGREEMENT" in note
        assert "bracket" in note

    def test_patterson_sits_near_the_bottom_of_the_shipped_bracket(self):
        """The bracket published to consumers is 0.98-0.999. An independent
        primary landing at 0.9718 is evidence the bracket was not overdrawn."""
        import pymat

        patterson = pymat.baso4.properties.optical.km_reflectance_infinite_at(420) / 100.0
        assert 0.96 < patterson < 0.98


class TestKubelkaMunkFiniteLayer:
    """R(d), T(d), A(d) — the fates of a photon meeting a real reflector.

    Added when a downstream reframing showed that a high semi-infinite
    reflectance and a leaking septum are the same finite-thickness solution,
    not two competing facts.
    """

    KM = {"wavelengths_nm": [300, 500, 700], "k": [0.455, 0.100, 0.062], "s": [619.0, 572.0, 517.0]}

    def _opt(self):
        return OpticalProperties(kubelka_munk=self.KM)

    def test_split_closes_to_one_hundred_percent(self):
        """R + T + A = 100 by construction, at every thickness. If this drifts,
        photons are being created or destroyed."""
        opt = self._opt()
        for mm in (0.05, 0.1, 0.2, 0.5, 1.0, 5.0):
            r, t, a = opt.km_split_at(420, mm / 10)
            assert r + t + a == pytest.approx(100.0, abs=1e-9)
            assert r >= 0 and t >= 0 and a >= 0

    def test_finite_reflectance_is_below_the_thick_layer_limit(self):
        opt = self._opt()
        r_finite = opt.km_reflectance_at(420, 0.02)
        r_inf = opt.km_reflectance_infinite_at(420)
        assert r_finite < r_inf
        assert r_finite == pytest.approx(91.9, abs=0.1)
        assert r_inf == pytest.approx(97.18, abs=0.05)

    def test_reflectance_rises_and_transmission_falls_with_thickness(self):
        opt = self._opt()
        rs = [opt.km_reflectance_at(420, d) for d in (0.01, 0.02, 0.03, 0.05, 0.1)]
        ts = [opt.km_transmittance_at(420, d) for d in (0.01, 0.02, 0.03, 0.05, 0.1)]
        assert rs == sorted(rs)
        assert ts == sorted(ts, reverse=True)

    def test_reflectance_converges_to_the_thick_layer_limit(self):
        opt = self._opt()
        assert opt.km_reflectance_at(420, 5.0) == pytest.approx(
            opt.km_reflectance_infinite_at(420), abs=0.01
        )

    def test_split_agrees_with_the_standalone_transmittance_accessor(self):
        opt = self._opt()
        _, t, _ = opt.km_split_at(420, 0.02)
        assert t == pytest.approx(opt.km_transmittance_at(420, 0.02))

    def test_zero_absorption_gives_a_perfect_thick_reflector(self):
        """The limit that is easy to get backwards: with k = 0 the thick-layer
        reflectance is exactly 1, not 0.999. Absorption is the ONLY thing that
        puts R_inf below unity — it is not a small correction to a
        non-absorbing model, it is the whole reason the asymptote exists."""
        opt = OpticalProperties(
            kubelka_munk={"wavelengths_nm": [400, 500], "k": [0.0, 0.0], "s": [572.0, 572.0]}
        )
        assert opt.km_reflectance_infinite_at(450) == pytest.approx(100.0)
        r, t, a = opt.km_split_at(450, 0.02)
        assert a == pytest.approx(0.0)
        # ...and the non-absorbing layer still leaks: R = sd/(1+sd).
        sd = 572.0 * 0.02
        assert r == pytest.approx(100.0 * sd / (1 + sd), abs=1e-9)
        assert t == pytest.approx(100.0 / (1 + sd), abs=1e-9)

    def test_absorbed_fraction_is_never_negative(self):
        """The defect that blocked this branch at review.

        `km_split_at` once took a `backing_reflectance`, and with it above zero
        returned NEGATIVE absorption — because K-M's `R` with a backing is the
        reflectance of the composite (layer plus backing, including light that
        crossed and came back), while `T` stays the layer's own transmittance.
        They are not two parts of one photon budget, so `A := 100 - R - T`
        stopped meaning "absorbed".

        The only test then exercising it asserted `bright > black`, which
        passed throughout. A conservation property has to be checked as a
        conservation property; an ordering assertion cannot see this.
        """
        opt = self._opt()
        for wl in (350, 420, 500, 700):
            for d in (0.001, 0.01, 0.02, 0.1, 1.0, 10.0):
                r, t, a = opt.km_split_at(wl, d)
                assert a >= 0.0, f"negative absorption at {wl} nm, {d} cm: {a}"
                assert r >= 0.0 and t >= 0.0
                assert r + t + a == pytest.approx(100.0, abs=1e-9)

    def test_no_backing_parameter_is_exposed(self):
        """Pins the removal. Re-adding it needs a physical definition of the
        decomposition, not a default argument."""
        import inspect

        params = inspect.signature(OpticalProperties.km_split_at).parameters
        assert "backing_reflectance" not in params
        assert list(params) == ["self", "wavelength", "thickness_cm", "incidence_deg"]

    def test_baso4_header_numbers_are_what_the_code_computes(self):
        """The R/T/A table written into the TOML header is a claim about this
        code's output. Pin it, so prose and behaviour cannot diverge."""
        import pymat

        opt = pymat.baso4.properties.optical
        for mm, exp_r, exp_t in ((0.1, 85.4, 14.4), (0.2, 91.9, 7.6), (0.6, 96.4, 2.3)):
            r, t, _ = opt.km_split_at(420, mm / 10)
            assert r == pytest.approx(exp_r, abs=0.05), mm
            assert t == pytest.approx(exp_t, abs=0.05), mm


class TestObliqueIncidence:
    """`incidence_deg` on the K-M accessors (#243).

    The accessor is for COLLIMATED light at a known angle. These tests pin the
    mathematics of `1/cos(theta)`; they deliberately do NOT assert any physical
    angle for a real detector, because two successive attempts to do that were
    both wrong — see `TestDiffuseReflectorErasesAngle` below for why the
    reflector, not the geometry, sets the angle.
    """

    KM = {"wavelengths_nm": [300, 500, 700], "k": [0.455, 0.100, 0.062], "s": [619.0, 572.0, 517.0]}

    def _opt(self):
        return OpticalProperties(kubelka_munk=self.KM)

    def test_obliquity_factor_is_one_over_cos(self):
        f = OpticalProperties.obliquity_factor
        assert f(0) == pytest.approx(1.0)
        assert f(60) == pytest.approx(2.0)
        assert f(76.7) == pytest.approx(4.34, abs=0.02)

    def test_obliquity_factor_is_capped_at_grazing(self):
        """1/cos diverges at 90 degrees; a plane-parallel slab model has stopped
        describing anything real well before that, so it caps rather than
        returning infinity."""
        f = OpticalProperties.obliquity_factor
        assert f(89.99) == 40.0
        assert f(90) == 40.0
        assert f(120) == 40.0  # |theta| folded
        assert f(-60) == pytest.approx(2.0)

    def test_default_is_normal_incidence(self):
        opt = self._opt()
        assert opt.km_split_at(420, 0.02) == opt.km_split_at(420, 0.02, 0.0)

    def test_a_long_enough_path_recovers_the_semi_infinite_limit(self):
        """Pure mathematics of the accessor: enough path in any guise reaches
        the thick-layer limit. 76.7 degrees is used as an ARBITRARY long-path
        example — it is not a claim about any real geometry. An earlier version
        of this test asserted it was the physical angle in a wrapped crystal;
        that was retracted twice over."""
        opt = self._opt()
        r_normal = opt.km_reflectance_at(420, 0.02, incidence_deg=0)
        r_grazing = opt.km_reflectance_at(420, 0.02, incidence_deg=76.7)
        r_inf = opt.km_reflectance_infinite_at(420)
        assert r_normal == pytest.approx(91.9, abs=0.1)
        assert r_grazing == pytest.approx(96.9, abs=0.1)
        assert r_inf - r_grazing < 0.5, "grazing should nearly reach the thick-layer limit"
        assert r_inf - r_normal > 5.0, "normal incidence is nowhere near it"

    def test_transmission_collapses_with_angle(self):
        """Transmission collapses with path length. Both figures are outputs of
        the model at the stated angle, not assertions about a detector."""
        opt = self._opt()
        assert opt.km_transmittance_at(420, 0.02, 0) == pytest.approx(7.63, abs=0.05)
        assert opt.km_transmittance_at(420, 0.02, 76.7) == pytest.approx(1.35, abs=0.05)

    def test_split_still_closes_at_every_angle(self):
        opt = self._opt()
        for th in (0, 30, 60, 76.7, 85, 89):
            r, t, a = opt.km_split_at(420, 0.02, incidence_deg=th)
            assert r + t + a == pytest.approx(100.0, abs=1e-9), th

    def test_reflectance_rises_monotonically_with_angle(self):
        opt = self._opt()
        rs = [
            opt.km_reflectance_at(420, 0.02, incidence_deg=t) for t in (0, 15, 30, 45, 60, 75, 85)
        ]
        assert rs == sorted(rs)

    def test_oblique_thin_matches_normal_thick(self):
        """A consistency check on the mechanism: doubling the path by angle
        must equal doubling it by thickness."""
        opt = self._opt()
        by_angle = opt.km_split_at(420, 0.02, incidence_deg=60)  # 1/cos(60) = 2
        by_thickness = opt.km_split_at(420, 0.04, incidence_deg=0)
        for a, b in zip(by_angle, by_thickness):
            assert a == pytest.approx(b, abs=1e-9)


class TestDiffuseReflectorErasesAngle:
    """A Lambertian reflector destroys the angular distribution it is given.

    Recorded as executable physics because two independent, plausible,
    peer-reviewed-by-both-sides attempts to reason about septum incidence angle
    were wrong in the same way: both treated the angle as a property of the
    crystal geometry when the reflector sets it.
    """

    KM = {"wavelengths_nm": [300, 500, 700], "k": [0.455, 0.100, 0.062], "s": [619.0, 572.0, 517.0]}

    def test_lambertian_mean_cosine_is_two_thirds(self):
        """<|cos|> over a cosine-weighted hemisphere is exactly 2/3, i.e. 48.19
        degrees. No aspect ratio appears anywhere in that statement."""
        n = 400_000
        mean_cos = sum(math.sqrt((i + 0.5) / n) for i in range(n)) / n
        assert mean_cos == pytest.approx(2 / 3, abs=1e-3)
        assert math.degrees(math.acos(2 / 3)) == pytest.approx(48.19, abs=0.01)

    def test_mean_path_multiplier_is_not_one_over_mean_cosine(self):
        """Jensen: <1/cos> = 2 for a Lambertian distribution, while 1/<cos> is
        1.5. Reaching for the second is a natural mistake and gives the wrong
        path length."""
        n = 400_000
        mean_inv_cos = sum(1.0 / math.sqrt((i + 0.5) / n) for i in range(n)) / n
        assert mean_inv_cos == pytest.approx(2.0, rel=2e-3)
        assert 1.0 / (2 / 3) == pytest.approx(1.5)

    def test_evaluating_at_the_mean_angle_is_close_but_not_equal(self):
        """T is nonlinear in path, so <T(theta)> != T(<theta>). Here the gap is
        ~0.1 points — small, but it is a real approximation and not an
        identity."""
        opt = OpticalProperties(kubelka_munk=self.KM)
        n = 20_000
        t_avg = (
            sum(
                opt.km_transmittance_at(
                    420, 0.02, incidence_deg=math.degrees(math.acos(math.sqrt((i + 0.5) / n)))
                )
                for i in range(n)
            )
            / n
        )
        t_at_mean = opt.km_transmittance_at(420, 0.02, 48.19)
        assert t_avg == pytest.approx(t_at_mean, abs=0.25)
        assert t_avg != t_at_mean

    def test_a_thin_septum_is_not_optically_thick_at_realistic_angles(self):
        """The claim that died twice. At the Lambertian mean angle a 0.2 mm
        septum still transmits ~5%, and at normal incidence ~7.6%. Only an
        unphysical ~77 degrees would make it behave semi-infinite, and a
        diffuse reflector cannot deliver that."""
        opt = OpticalProperties(kubelka_munk=self.KM)
        assert opt.km_transmittance_at(420, 0.02, 48.19) == pytest.approx(5.1, abs=0.1)
        assert opt.km_transmittance_at(420, 0.02, 0) == pytest.approx(7.6, abs=0.1)
        r_inf = opt.km_reflectance_infinite_at(420)
        r_real = opt.km_reflectance_at(420, 0.02, incidence_deg=48.19)
        r_unphysical = opt.km_reflectance_at(420, 0.02, incidence_deg=76.7)
        # ~3 points short of the limit at the realistic angle...
        assert r_inf - r_real > 2.5
        # ...and roughly an order of magnitude closer at the angle that was
        # claimed and then retracted. The difference between the two is the
        # whole of the dead argument.
        assert (r_inf - r_unphysical) < (r_inf - r_real) / 5


class TestOpticalThicknessDegeneracy:
    """`thickness_cm` and `incidence_deg` enter only as a product (#243).

    This degeneracy is why a falsified mechanism kept producing correct
    numbers: "77 degrees at 0.2 mm" and "0.87 mm at normal incidence" are the
    same optical thickness, so no check on the OUTPUT can separate them.
    Recorded as a test because it is a property of the model that a fitter
    needs to know before fitting.
    """

    KM = {"wavelengths_nm": [300, 500, 700], "k": [0.455, 0.100, 0.062], "s": [619.0, 572.0, 517.0]}

    def test_angle_and_thickness_are_indistinguishable(self):
        opt = OpticalProperties(kubelka_munk=self.KM)
        by_angle = opt.km_split_at(420, 0.02, incidence_deg=76.7)
        by_thickness = opt.km_split_at(420, 0.02 * OpticalProperties.obliquity_factor(76.7))
        for a, b in zip(by_angle, by_thickness):
            assert a == pytest.approx(b, abs=1e-9)

    def test_thick_layer_reflectance_cannot_validate_a_thickness(self):
        """A proposed falsification test that turned out to be blind, kept as
        an executable statement of WHY.

        `R_inf` depends only on `k/s`; `d` cancels. So checking a thick layer
        against the published `R_inf` passes identically for any thickness
        multiplier, and cannot detect one that is wrong. A test that a wrong
        model passes is not a weak test, it is a non-test."""
        opt = OpticalProperties(kubelka_munk=self.KM)
        r_inf = opt.km_reflectance_infinite_at(420)
        for multiplier in (1.0, 1.49, 2.0, 4.34, 10.0):
            assert opt.km_reflectance_at(420, 5.0 * multiplier) == pytest.approx(r_inf, abs=1e-6)


class TestThickLayerNumerics:
    """The hyperbolic form overflows for large optical thickness; the thick
    limit is branched before it can. Found by running the degeneracy check
    above at a 50 cm layer."""

    KM = {"wavelengths_nm": [300, 500, 700], "k": [0.455, 0.100, 0.062], "s": [619.0, 572.0, 517.0]}

    @pytest.mark.parametrize("thickness_cm", [1.0, 5.0, 50.0, 1e4, 1e6])
    def test_no_overflow_and_split_still_closes(self, thickness_cm):
        opt = OpticalProperties(kubelka_munk=self.KM)
        r, t, a = opt.km_split_at(420, thickness_cm)
        assert r + t + a == pytest.approx(100.0, abs=1e-9)
        assert t >= 0.0

    def test_thick_branch_is_exact_not_approximate(self):
        """`coth -> 1` gives `R = 1/(a+b)`, and `(1+x+sqrt(x^2+2x))` times
        `(1+x-sqrt(x^2+2x))` is identically 1 — so the branch returns exactly
        `R_inf`, not a value near it."""
        opt = OpticalProperties(kubelka_munk=self.KM)
        assert opt.km_reflectance_at(420, 1e6) == pytest.approx(
            opt.km_reflectance_infinite_at(420), abs=1e-12
        )

    def test_the_branch_boundary_is_continuous(self):
        """No step at the bsd > 20 cutover."""
        opt = OpticalProperties(kubelka_munk=self.KM)
        below = opt.km_reflectance_at(420, 0.9)
        above = opt.km_reflectance_at(420, 1.1)
        assert abs(above - below) < 0.01
