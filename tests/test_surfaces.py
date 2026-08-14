"""Tests for #243 — the measured surface-finish catalogue.

Per ADR-0004 §2/§3:
- `Surface` is its own type, not a `Material`, with its own registry.
- The catalogue holds exactly the 30 MEASURED interfaces in Geant4
  `G4RealSurface` 2.2: 21 LBNL + 9 DAVIS. Analytic UNIFIED finishes are
  model selections and are deliberately absent.
- Air-gap and optical-contact coupling are distinguishable, which is the
  thing the consuming engine could not previously express.
- Every entry carries provenance.
- The `[lyso.Ce.polished]` inherited-variant shape works end to end.
"""

from __future__ import annotations

from textwrap import dedent

import pytest

import pymat
from pymat.surfaces import COUPLINGS, LUT_FAMILIES, MODELS, Surface, load_surfaces, surfaces

# The exact G4OpticalSurfaceFinish spellings, transcribed from
# source/materials/include/G4OpticalSurface.hh. If the catalogue ever drifts
# from these, downstream LUT lookups break silently — so they are pinned here
# rather than derived from the data file the test is supposed to be checking.
LBNL_EXPECTED = {
    f"{treatment}{wrap}"
    for treatment in ("polished", "etched", "ground")
    for wrap in (
        "lumirrorair",
        "lumirrorglue",
        "teflonair",
        "tioair",
        "tyvekair",
        "vm2000air",
        "vm2000glue",
    )
}
DAVIS_EXPECTED = {
    "Rough_LUT",
    "RoughTeflon_LUT",
    "RoughESR_LUT",
    "RoughESRGrease_LUT",
    "Polished_LUT",
    "PolishedTeflon_LUT",
    "PolishedESR_LUT",
    "PolishedESRGrease_LUT",
    "Detector_LUT",
}

# Enum members of dielectric_LUT that ship NO measured .dat file. They must not
# appear in the catalogue — an entry with no measurement behind it is exactly
# the uncited value this repo exists to prevent (ADR-0004 §3).
LBNL_UNMEASURED = {"polishedair", "etchedair", "groundair"}

# Analytic UNIFIED/GLISUR finishes — model selections, not measurements.
ANALYTIC_FINISHES = {
    "polished",
    "polishedfrontpainted",
    "polishedbackpainted",
    "ground",
    "groundfrontpainted",
    "groundbackpainted",
}


class TestCatalogueCompleteness:
    def test_has_exactly_thirty_entries(self):
        assert len(surfaces) == 30

    def test_all_21_lbnl_lut_names_present(self):
        got = {s.lut_surface for s in surfaces(lut_family="lbnl")}
        assert got == LBNL_EXPECTED
        assert len(got) == 21

    def test_all_9_davis_lut_names_present(self):
        got = {s.lut_surface for s in surfaces(lut_family="davis")}
        assert got == DAVIS_EXPECTED
        assert len(got) == 9

    def test_unmeasured_lbnl_enum_members_are_excluded(self):
        got = {s.lut_surface for s in surfaces.values()}
        assert not (got & LBNL_UNMEASURED)

    def test_analytic_finishes_are_excluded(self):
        """These are strata's, not ours — see ADR-0004 §3."""
        got = {s.lut_surface for s in surfaces.values()}
        assert not (got & ANALYTIC_FINISHES)

    def test_lut_surface_names_are_unique(self):
        names = [s.lut_surface for s in surfaces.values()]
        assert len(names) == len(set(names))

    def test_every_entry_declares_its_dataset(self):
        for s in surfaces.values():
            assert s.lut_dataset == "G4RealSurface-2.2", s.key

    def test_g4_surface_types_match_family(self):
        for s in surfaces.values():
            expected = "dielectric_LUT" if s.lut_family == "lbnl" else "dielectric_LUTDAVIS"
            assert s.g4_surface_type == expected, s.key


class TestProvenance:
    def test_every_entry_cites_its_lut_name(self):
        for s in surfaces.values():
            assert s.source_of("lut_surface") is not None, s.key

    def test_every_entry_cites_its_family(self):
        for s in surfaces.values():
            assert s.source_of("lut_family") is not None, s.key

    def test_every_entry_produces_bibtex(self):
        for s in surfaces.values():
            assert s.cite().startswith("@misc{"), s.key

    def test_coupling_index_is_cited_wherever_set(self):
        """The index of the filling medium is the whole physical difference
        between air-gap and optical contact — it does not get to be uncited."""
        for s in surfaces.values():
            if s.coupling_index is not None:
                assert s.source_of("coupling_index") is not None, s.key

    def test_licenses_are_in_the_allowed_set(self):
        allowed = {
            "CC0",
            "PD-USGov",
            "CC-BY-3.0",
            "CC-BY-4.0",
            "CC-BY-SA-4.0",
            "Geant4-SL",
            "proprietary-reference-only",
        }
        for s in surfaces.values():
            for src in s._sources.values():
                assert src.license in allowed, f"{s.key}: {src.license}"

    def test_family_citations_are_the_real_papers(self):
        lbnl = surfaces["lbnl.polished.vm2000_air"]
        assert lbnl.source_of("lut_family").ref == "10.1109/TNS.2010.2042731"
        davis = surfaces["davis.polished_esr_grease"]
        assert davis.source_of("lut_family").ref == "10.1088/0031-9155/58/7/2185"


class TestCouplingDistinction:
    """The brief's load-bearing ask: air gap and optical contact are
    physically different and must be distinguishable."""

    def test_air_gap_and_contact_are_both_represented(self):
        assert len(surfaces(coupling="air_gap")) == 19
        assert len(surfaces(coupling="optical_contact")) == 8
        assert len(surfaces(coupling="none")) == 2

    def test_same_reflector_differs_only_by_coupling(self):
        air = surfaces["lbnl.polished.vm2000_air"]
        glue = surfaces["lbnl.polished.vm2000_glue"]
        assert air.reflector_material == glue.reflector_material == "esr"
        assert air.treatment == glue.treatment == "polished"
        assert air.lut_surface != glue.lut_surface
        assert air.coupling == "air_gap"
        assert glue.coupling == "optical_contact"
        assert air.is_optical_contact is False
        assert glue.is_optical_contact is True

    def test_contact_entries_carry_the_filler_index(self):
        for s in surfaces(coupling="optical_contact"):
            assert s.coupling_index is not None, s.key
            assert 1.3 < s.coupling_index < 1.7, s.key

    def test_air_gap_entries_have_no_filler_index(self):
        for s in surfaces(coupling="air_gap"):
            assert s.coupling_index is None, s.key

    def test_davis_grease_is_bc630_and_resolves_to_a_material(self):
        s = surfaces["davis.polished_esr_grease"]
        assert s.coupling_material == "bc630"
        assert s.coupling_index == 1.465
        # The coupling medium is a real material in this same database.
        assert pymat.bc630 is not None

    def test_lbnl_glue_is_meltmount(self):
        s = surfaces["lbnl.ground.lumirror_glue"]
        assert s.coupling_index == 1.582
        assert "meltmount" in s.source_of("coupling_index").note.lower()

    def test_reflector_material_refs_resolve(self):
        for s in surfaces.values():
            if s.reflector_material:
                assert pymat.materials[s.reflector_material] is not None, s.key


class TestInheritance:
    def test_family_fields_flow_down(self):
        s = surfaces["lbnl.etched.tyvek_air"]
        assert s.lut_family == "lbnl"  # from surface.lbnl
        assert s.treatment == "etched"  # from surface.lbnl.etched
        assert s.lut_surface == "etchedtyvekair"  # own

    def test_abstract_nodes_are_not_registered(self):
        assert "lbnl" not in surfaces
        assert "lbnl.polished" not in surfaces
        assert "davis" not in surfaces

    def test_identity_fields_do_not_leak_to_children(self):
        """A child must never inherit a parent's `lut_surface` or `name` —
        that is what makes each entry a distinct measurement."""
        parents = {s.lut_surface for s in surfaces.values()}
        assert len(parents) == len(surfaces)

    def test_parent_is_recorded(self):
        assert surfaces["lbnl.polished.teflon_air"]._parent == "lbnl.polished"

    def test_sources_inherit_and_can_be_overridden(self):
        # Family default inherited from surface.lbnl ...
        s = surfaces["lbnl.polished.lumirror_glue"]
        assert s.source_of("lut_family").citation == "janecek_moses_2010"
        # ... and a leaf-level row wins for its own path.
        assert s.source_of("coupling_index").citation == "cargille_meltmount_1582"


class TestRegistryAPI:
    def test_mapping_protocol(self):
        assert "davis.rough" in surfaces
        assert isinstance(surfaces["davis.rough"], Surface)
        assert len(list(surfaces)) == len(surfaces)

    def test_prefixed_key_also_resolves(self):
        """`surface.davis.rough` is how the key is spelled on disk and how it
        travels in downstream files."""
        assert surfaces["surface.davis.rough"] is surfaces["davis.rough"]
        assert "surface.davis.rough" in surfaces

    def test_callable_lookup(self):
        assert surfaces("davis.rough").lut_surface == "Rough_LUT"

    def test_callable_filter(self):
        polished_lbnl = surfaces(lut_family="lbnl", treatment="polished")
        assert len(polished_lbnl) == 7

    def test_filter_by_reflector(self):
        esr = surfaces(reflector_material="esr")
        assert len(esr) == 10  # 6 LBNL vm2000 + 4 DAVIS ESR

    def test_unknown_key_error_explains_the_scope(self):
        with pytest.raises(KeyError, match="measured interfaces only"):
            surfaces["polished"]  # analytic finish — deliberately not here

    def test_exported_from_package_root(self):
        assert pymat.surfaces is surfaces
        assert pymat.Surface is Surface

    def test_surface_is_not_in_the_material_registry(self):
        """The two namespaces stay separate — a Surface has no density."""
        assert "davis.rough" not in pymat.materials


class TestSurfaceValidation:
    def test_unknown_model_raises(self):
        with pytest.raises(ValueError, match="model="):
            Surface(key="x", name="X", model="glossy")

    def test_unknown_coupling_raises(self):
        with pytest.raises(ValueError, match="coupling="):
            Surface(key="x", name="X", coupling="damp")

    def test_lut_model_requires_a_lut_surface(self):
        with pytest.raises(ValueError, match="requires 'lut_surface'"):
            Surface(key="x", name="X", model="lut")

    def test_lut_surface_without_lut_model_raises(self):
        with pytest.raises(ValueError, match="not 'lut'"):
            Surface(key="x", name="X", model="specular", lut_surface="Rough_LUT")

    def test_optical_contact_requires_an_index(self):
        with pytest.raises(ValueError, match="requires 'coupling_index'"):
            Surface(key="x", name="X", coupling="optical_contact")

    def test_air_gap_with_a_polymer_index_raises(self):
        """Guards the exact confusion the catalogue exists to prevent."""
        with pytest.raises(ValueError, match="use coupling='optical_contact'"):
            Surface(key="x", name="X", coupling="air_gap", coupling_index=1.465)

    def test_air_gap_may_state_unity_index(self):
        s = Surface(key="x", name="X", coupling="air_gap", coupling_index=1.0)
        assert s.coupling_index == 1.0

    def test_reflectivity_out_of_range_raises(self):
        with pytest.raises(ValueError, match="percent"):
            Surface(key="x", name="X", reflectivity=101.0)
        assert Surface(key="x", name="X", reflectivity=98.5).reflectivity == 98.5

    def test_fraction_shaped_reflectivity_warns_but_is_not_rewritten(self, caplog):
        """0.985 is legal (a very dark surface) but is usually a fraction typed
        where a percent was meant. Warn — never silently multiply by 100."""
        with caplog.at_level("WARNING", logger="pymat.surfaces"):
            s = Surface(key="x", name="X", reflectivity=0.985)
        assert s.reflectivity == 0.985  # untouched
        assert "PERCENT" in caplog.text

    def test_malformed_spectrum_raises(self):
        with pytest.raises(ValueError, match="length"):
            Surface(
                key="x",
                name="X",
                reflectivity_spectrum={"wavelengths_nm": [400, 500], "values": [0.9]},
            )

    def test_vocabularies_are_closed(self):
        assert MODELS == {"lut", "specular", "diffuse"}
        assert LUT_FAMILIES == {"lbnl", "davis"}
        assert COUPLINGS == {"air_gap", "optical_contact", "none"}


class TestSurfaceAccessors:
    def test_reflectivity_at_falls_back_to_scalar(self):
        s = Surface(key="x", name="X", reflectivity=98.5)
        assert s.reflectivity_at(420) == 98.5

    def test_reflectivity_at_interpolates_spectrum(self):
        s = Surface(
            key="x",
            name="X",
            reflectivity_spectrum={"wavelengths_nm": [400, 500], "values": [98.0, 99.0]},
        )
        assert s.reflectivity_at(450) == pytest.approx(98.5)
        assert s.reflectivity_at(200) == 98.0  # clamped

    def test_lut_entries_declare_reflectivity_absent(self):
        """A LUT IS the angular reflectance; a scalar would discard it."""
        s = surfaces["davis.polished_esr"]
        assert s.reflectivity is None
        assert s.absent("reflectivity").reason == "not-applicable"

    def test_detector_lut_declares_its_coupling_unknown(self):
        s = surfaces["davis.detector"]
        assert s.coupling is None
        assert s.absent("coupling").reason == "not-measured"

    def test_repr_is_informative(self):
        assert "PolishedESRGrease_LUT" in repr(surfaces["davis.polished_esr_grease"])


class TestLoaderErrors:
    def _load(self, tmp_path, body):
        p = tmp_path / "s.toml"
        p.write_text(dedent(body))
        return load_surfaces(p)

    def test_bad_sources_table_raises(self, tmp_path):
        with pytest.raises(ValueError, match="_sources must be a table"):
            self._load(
                tmp_path,
                """
                [surface.x]
                name = "X"
                _sources = "nope"
                """,
            )

    def test_unknown_absent_reason_raises(self, tmp_path):
        with pytest.raises(ValueError, match="unknown reason"):
            self._load(
                tmp_path,
                """
                [surface.x]
                name = "X"
                [surface.x._absent]
                reflectivity = { reason = "dunno" }
                """,
            )

    def test_abstract_parent_yields_only_children(self, tmp_path):
        cat = self._load(
            tmp_path,
            """
            [surface.fam]
            abstract = true
            model = "specular"
            [surface.fam.a]
            name = "A"
            reflectivity = 90.0
            """,
        )
        assert set(cat) == {"fam.a"}
        assert cat["fam.a"].model == "specular"


class TestInheritedVariant:
    """The `[lyso.Ce.polished]` shape the brief asks us to confirm end to end.

    Accepted as a substance-with-treatment variant. NOT carrying a
    `default_surface` — see ADR-0004 §9.
    """

    def test_variant_exists_with_its_treatment(self):
        p = pymat.lyso.Ce.polished
        assert p.name == "LYSO:Ce, polished"
        assert p.treatment == "polished"
        assert p.path == "lyso.Ce.polished"

    def test_variant_inherits_parent_optical_scalars(self):
        opt = pymat.lyso.Ce.polished.properties.optical
        assert opt.light_yield == 33000  # from lyso.Ce
        assert opt.refractive_index == 1.82  # from lyso
        assert opt.emission_peak == 420  # from lyso
        assert opt.dopant == "Ce"  # from lyso.Ce
        assert opt.rise_time == 0.072  # from lyso.Ce

    def test_variant_inherits_the_self_absorption_channel(self):
        opt = pymat.lyso.Ce.polished.properties.optical
        assert opt.absorption_length_reabs_at(420).magnitude == 588.0

    def test_variant_inherits_provenance(self):
        p = pymat.lyso.Ce.polished
        assert p.source_of("optical.absorption_length_reabs").citation == "bosca_lopez_2023"
        assert p.cite("optical.absorption_length_reabs").startswith("@misc{")

    def test_variant_inherits_declared_absences(self):
        p = pymat.lyso.Ce.polished
        assert p.is_absent("optical.emission_spectrum")
        assert p.is_absent("optical.reemit_qe")

    def test_variant_does_not_carry_an_assembly_default(self):
        """ADR-0004 §9: which finish a polished crystal is wrapped in is a
        fact about a built detector, not about the crystal."""
        opt = pymat.lyso.Ce.polished.properties.optical
        assert not hasattr(opt, "default_surface")
        assert getattr(opt, "default_surface", None) is None

    def test_pairing_a_material_with_a_finish_is_a_two_key_lookup(self):
        """What a consumer actually does instead — and both halves resolve."""
        crystal = pymat.lyso.Ce.polished
        finish = surfaces["davis.polished_esr_grease"]
        assert crystal.properties.optical.n_at(420) == 1.82
        assert finish.treatment == crystal.treatment == "polished"
        assert finish.is_optical_contact
