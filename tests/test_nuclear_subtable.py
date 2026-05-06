"""Tests for #157 — new `[<material>.nuclear]` sub-table.

Moves `radiation_length`, `interaction_length`, `moliere_radius` from
`[optical]` to `[nuclear]` (semantic recategorization). Adds:
- Z_eff
- mean_excitation_energy_eV (Geant4 SetMeanExcitationEnergy)
- intrinsic_activity_Bq_per_g (LYSO 176Lu ≈ 39)

`mu_rho(energy_keV=...)` is a lazy accessor that imports `nucl-parquet`
on first call — wired via `pip install py-mat[nuclear]` optional extra.

Backwards compat per ADR-0003 §1 + the user's "build123d-only consumer"
clarification: clean move, no shim. radiation_length etc. removed from
OpticalProperties; existing TOMLs migrated to [nuclear] in the same PR.
"""

from __future__ import annotations

from textwrap import dedent

import pytest

from pymat.loader import load_toml


class TestNuclearSubtable:
    def test_radiation_length_now_under_nuclear(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [lyso]
            name = "LYSO"
            [lyso.nuclear]
            radiation_length_value = 1.14
            radiation_length_unit = "cm"
            interaction_length_value = 25
            interaction_length_unit = "cm"
            moliere_radius_value = 2.07
            moliere_radius_unit = "cm"
            """)
        )
        m = load_toml(p)["lyso"]
        assert m.properties.nuclear.radiation_length == 1.14
        assert m.properties.nuclear.interaction_length == 25
        assert m.properties.nuclear.moliere_radius == 2.07

    def test_optical_no_longer_has_radiation_fields(self):
        """The dataclass surface no longer exposes these on optical."""
        from pymat.properties import OpticalProperties

        op = OpticalProperties()
        assert not hasattr(op, "radiation_length")
        assert not hasattr(op, "interaction_length")
        assert not hasattr(op, "moliere_radius")

    def test_new_nuclear_scalars(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [lyso]
            name = "LYSO"
            [lyso.nuclear]
            Z_eff = 66
            mean_excitation_energy_eV = 396
            intrinsic_activity_Bq_per_g = 39
            """)
        )
        m = load_toml(p)["lyso"]
        assert m.properties.nuclear.Z_eff == 66
        assert m.properties.nuclear.mean_excitation_energy_eV == 396
        assert m.properties.nuclear.intrinsic_activity_Bq_per_g == 39

    def test_pint_qty_for_lengths(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [m]
            name = "M"
            [m.nuclear]
            radiation_length_value = 1.14
            radiation_length_unit = "cm"
            """)
        )
        m = load_toml(p)["m"]
        assert m.properties.nuclear.radiation_length_qty.to("cm").magnitude == 1.14

    def test_default_nuclear_is_empty(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [m]
            name = "M"
            """)
        )
        m = load_toml(p)["m"]
        assert m.properties.nuclear.radiation_length is None
        assert m.properties.nuclear.Z_eff is None

    def test_inheritance(self, tmp_path):
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [base]
            name = "Base"
            [base.nuclear]
            Z_eff = 50

            [base.variant]
            name = "Variant"
            [base.variant.nuclear]
            Z_eff = 60
            """)
        )
        mats = load_toml(p)
        assert mats["base"].variant.properties.nuclear.Z_eff == 60


class TestMuRhoLazyAccessor:
    def test_mu_rho_raises_helpful_message_when_extra_missing(self, tmp_path):
        """Without nucl-parquet installed, mu_rho() raises ImportError with hint."""
        p = tmp_path / "m.toml"
        p.write_text(
            dedent("""
            [m]
            name = "M"
            [m.nuclear]
            Z_eff = 66
            """)
        )
        m = load_toml(p)["m"]
        # If nucl-parquet IS installed, this test would skip; for now we
        # don't ship it as a hard dep, so the optional-extra path must
        # surface a usable error.
        try:
            import nucl_parquet  # noqa: F401

            pytest.skip("nucl-parquet installed; lazy-import path not exercised")
        except ImportError:
            pass
        with pytest.raises(ImportError, match="py-mat\\[nuclear\\]"):
            m.properties.nuclear.mu_rho(energy_keV=511)


class TestRegression:
    def test_full_corpus_loads(self):
        """Migrated TOMLs (scintillators) must still load cleanly."""
        from pymat import _CATEGORY_BASES
        from pymat.loader import load_category

        for cat in _CATEGORY_BASES:
            mats = load_category(cat)
            assert mats, f"category {cat} loaded empty"

    def test_lyso_radiation_length_after_migration(self):
        """Smoke test: the LYSO entry's radiation_length value preserved through
        the migration from [optical] to [nuclear]."""
        from pymat.loader import load_category

        mats = load_category("scintillators")
        # LYSO base radiation length was 1.14 cm before the move
        assert mats["lyso"].properties.nuclear.radiation_length == 1.14
