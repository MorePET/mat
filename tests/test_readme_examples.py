"""
Integration tests for README documentation - examples that will be extracted into README.

These tests serve dual purpose:
1. Verify functionality through comprehensive examples
2. Generate documentation through docstring extraction (doc-as-tested-code paradigm)

Docstrings in test functions are extracted by generate_readme.py to create the README.
Use markdown in docstrings for formatting.
"""

import pytest


class TestBasicUsage:
    """Examples for the Quick Start section."""

    def test_creating_materials_basic(self):
        """
        ## Creating Materials

        Create materials with convenient parameters:
        """
        from pymat import Material

        # Using convenience parameters
        steel = Material(name="Steel", density=7.85)
        assert steel.density == 7.85

        # With visualization color
        aluminum = Material(name="Aluminum", density=2.7, color=(0.88, 0.88, 0.88))
        assert aluminum.vis.base_color[:3] == (0.88, 0.88, 0.88)

        # With formula
        lyso = Material(name="LYSO", formula="Lu1.8Y0.2SiO5", density=7.1)
        assert lyso.formula == "Lu1.8Y0.2SiO5"

    def test_property_groups(self):
        """
        ## Using Property Groups

        Define multiple properties at once using property group dictionaries:
        """
        from pymat import Material

        # Define steel with multiple property groups
        steel = Material(
            name="Stainless Steel 304",
            mechanical={"density": 8.0, "youngs_modulus": 193, "yield_strength": 170},
            thermal={"melting_point": 1450, "thermal_conductivity": 15.1},
            vis={"base_color": (0.75, 0.75, 0.77, 1.0), "metallic": 1.0},
        )

        assert steel.properties.mechanical.density == 8.0
        assert steel.properties.mechanical.youngs_modulus == 193
        assert steel.properties.thermal.melting_point == 1450
        assert steel.vis.metallic == 1.0

    def test_applying_to_shapes(self):
        """
        ## Applying Materials to Shapes

        Apply materials to build123d shapes for visualization and mass calculation:
        """
        pytest.importorskip("build123d")
        from build123d import Box

        from pymat import Material

        # Create material
        steel = Material(name="Steel", density=7.85, color=(0.7, 0.7, 0.7))

        # Create shape and apply material
        box = Box(10, 10, 10)
        steel.apply_to(box)

        assert box.material.name == "Steel"
        assert box.mass > 0
        assert box.color is not None

    def test_molar_mass_from_formula(self):
        """
        ## Computing Molar Mass

        `Material.molar_mass` is a computed property that parses the
        chemical formula and looks up each element's atomic weight.
        It supports fractional stoichiometry and strips dopant
        notation like `LYSO:Ce` so doped-crystal aliases work
        unchanged.

        Nothing is stored — it recomputes on each access. That's
        intentional: molar mass is definitionally derived from
        `formula` and should never drift. Missing or unknown-element
        formulas return `None`. See
        `docs/decisions/0001-derived-chemistry-properties-live-on-material.md`.
        """
        from pymat import Material

        # Pure element
        iron = Material(name="Iron", formula="Fe")
        assert iron.molar_mass == 55.85

        # Simple compound
        alumina = Material(name="Alumina", formula="Al2O3")
        assert abs(alumina.molar_mass - 101.96) < 0.01

        # Fractional stoichiometry (a PET-scanner scintillator)
        lyso = Material(name="LYSO", formula="Lu1.8Y0.2SiO5")
        assert abs(lyso.molar_mass - 440.87) < 0.1

        # Dopant suffix is stripped
        lyso_ce = Material(name="LYSO:Ce", formula="Lu1.8Y0.2SiO5:Ce")
        assert lyso_ce.molar_mass == lyso.molar_mass

        # Unit-aware companion accessor (Pint Quantity)
        qty = iron.molar_mass_qty
        assert qty.to("kg/mol").magnitude == pytest.approx(0.05585, abs=1e-4)

        # Gracefully returns None when no formula is set
        unknown = Material(name="Unknown Alloy")
        assert unknown.molar_mass is None

    def test_elements_low_level_api(self):
        """
        ## Low-level: `pymat.elements`

        For callers that don't need a full `Material` object —
        e.g. quick stoichiometry calculations inside a Monte Carlo
        transport loop — the low-level `pymat.elements` module
        exposes the same machinery directly.

        The `ATOMIC_WEIGHT` table is a line-for-line mirror of the
        Rust `rs-materials` crate, so Python and Rust Monte Carlo
        engines get identical molar masses byte-for-byte.
        """
        from pymat.elements import (
            ATOMIC_WEIGHT,
            compute_molar_mass,
            parse_formula,
        )

        # Atomic weight lookup
        assert ATOMIC_WEIGHT["Fe"] == 55.85
        assert ATOMIC_WEIGHT["Lu"] == 175.0

        # Formula parser: fractional stoichiometry + repeat handling
        counts = parse_formula("Lu1.8Y0.2SiO5")
        assert counts == {"Lu": 1.8, "Y": 0.2, "Si": 1.0, "O": 5.0}

        # Molar mass directly from a formula string
        assert abs(compute_molar_mass("Al2O3") - 101.96) < 0.01


class TestHierarchicalMaterials:
    """Examples for hierarchical material definitions."""

    def test_grade_chaining(self):
        """
        ## Chainable Material Hierarchy

        Build hierarchies with grades, tempers, and treatments:
        """
        from pymat import Material

        # Create base stainless steel
        stainless = Material(name="Stainless Steel", density=8.0, thermal={"melting_point": 1450})

        # Add grade
        s304 = stainless.grade_("304", name="SS 304", mechanical={"yield_strength": 170})
        assert s304.density == 8.0  # Inherited
        assert s304.properties.mechanical.yield_strength == 170

        # Add treatment
        passivated = s304.treatment_("passivated", name="SS 304 Passivated")
        assert (
            passivated.path == "stainless_steel.304.passivated"
        )  # name -> lowercase with underscores
        assert passivated.density == 8.0  # Inherited through chain

    def test_direct_access(self):
        """
        ## Direct Material Access

        Load materials and access them directly from the library:
        """
        from pymat import aluminum, lyso, stainless

        # Direct access to materials
        s316L = stainless.s316L
        assert s316L.grade == "316L"

        al6061 = aluminum.a6061
        assert al6061.density == 2.7  # Inherited from aluminum

        lyso_crystal = lyso
        assert "LYSO" in lyso_crystal.name


class TestCustomizingAppearance:
    """Examples for the safe pattern of customizing appearance without
    corrupting the registry singleton."""

    def test_safe_appearance_customization(self):
        """
        ## Customizing Appearance Safely

        Materials reached via `pymat["..."]` or category imports
        (`from pymat import stainless`) are *shared instances* — the
        same object every caller in the process sees. Mutating
        `m.vis.roughness = 0.6` or flipping `m.vis.finish` on those
        leaks into every other consumer.

        The safe pattern uses two methods that pair cleanly:
        """
        import pymat
        from pymat.vis import to_threejs

        steel = pymat["Stainless Steel 304"]  # registry singleton — DON'T mutate

        # Derive an independent variant (1) and attach it to a fresh Material (2)
        polished_vis = steel.vis.override(roughness=0.05, finish="polished")
        shiny = steel.with_vis(polished_vis)

        three = to_threejs(shiny)  # uses the polished values
        assert three["roughness"] == 0.05
        assert steel.vis.material_id == "Metal012"  # registry untouched

        # ``Vis.override(**deltas) -> Vis``  → deep-copied Vis with deltas
        #   (finishes deep-copied; identity changes invalidate the texture
        #   cache atomically; unknown kwargs raise TypeError).
        # ``Material.with_vis(vis) -> Material`` → registry-detached Material
        #   with the supplied Vis attached. Equivalent to ``Material.copy()``
        #   followed by slotting the new vis in.
        # ``Material.copy() -> Material`` → generic detach if you need to
        #   tweak more than just the Vis.

        # Materials *you* construct directly (Material(name="custom",
        # vis={...})) are not shared and can be mutated freely.


class TestOpticalVsVisualization:
    """Examples showing separation of optical properties and visualization."""

    def test_physics_vs_visualization(self):
        """
        ## Physics Properties vs Visualization

        Understand the difference between measured optical properties (physics)
        and rendering properties (visualization):
        """
        from pymat import Material

        # Create transparent material
        glass = Material(
            name="Optical Glass",
            color=(0.9, 0.9, 0.9, 0.8),  # Visual: 80% opaque white
            optical={"transparency": 95, "refractive_index": 1.517},  # Physics: 95% transmission
            vis={"transmission": 0.8},  # Rendering: how transparent it looks
        )

        # Physics properties (measured)
        assert glass.properties.optical.transparency == 95
        assert glass.properties.optical.refractive_index == 1.517

        # Visualization properties (rendering)
        assert glass.vis.base_color[3] == 0.8  # Alpha
        assert glass.vis.transmission == 0.8

    def test_scintillator_properties(self):
        """
        ## Scintillator-Specific Properties

        Define detector crystals with optical physics properties:
        """
        from pymat import Material

        lyso_crystal = Material(
            name="LYSO:Ce Crystal",
            density=7.1,
            optical={
                "refractive_index": 1.82,
                "transparency": 92,
                "light_yield": 32000,  # photons/MeV
                "decay_time": 41,  # ns
                "emission_peak": 420,  # nm
            },
            vis={"base_color": (0.0, 1.0, 1.0, 0.85), "transmission": 0.85},
        )

        assert lyso_crystal.properties.optical.light_yield == 32000
        assert lyso_crystal.properties.optical.decay_time == 41
        assert lyso_crystal.vis.transmission == 0.85


class TestFactoryFunctions:
    """Examples using factory functions for dynamic properties."""

    def test_temperature_dependent_water(self):
        """
        ## Temperature-Dependent Materials

        Use factory functions for materials with properties that depend on external parameters:
        """
        from pymat.factories import water

        # Water at different temperatures
        cold_water = water(4)  # Max density
        room_water = water(20)  # Room temperature
        hot_water = water(80)  # Heated

        assert cold_water.density > room_water.density
        assert room_water.density > hot_water.density

        # Verify realistic values
        assert 0.99 < cold_water.density < 1.01
        assert 0.95 < hot_water.density < 0.98

    def test_air_at_altitude(self):
        """
        ## Air at Different Conditions

        Create air material at specific temperature and pressure:
        """
        from pymat.factories import air

        sea_level = air(15, 1.0)  # 15°C, 1 atm
        high_altitude = air(15, 0.5)  # 15°C, 0.5 atm (5500m)

        assert sea_level.density > high_altitude.density

    def test_saline_solution(self):
        """
        ## Saline Solutions

        Create solutions with specific concentration and temperature:
        """
        from pymat.factories import saline, water

        # Physiological saline at body temperature
        phantom = saline(0.9, temperature_c=37)
        # Saline is slightly denser than pure water at same temperature
        pure_water_37 = water(37)
        assert phantom.density > pure_water_37.density

        # Seawater (3.5% NaCl) at 20°C
        seawater = saline(3.5, temperature_c=20)
        # Higher concentration = higher density
        assert seawater.density > phantom.density


class TestMaterialCategories:
    """Examples with different material categories."""

    def test_load_metals(self):
        """
        ## Loading Metal Materials

        Access various metal materials from the metals category:
        """
        from pymat import aluminum, copper, stainless

        # Stainless steel variants
        s304 = stainless.s304
        s316L = stainless.s316L
        assert s304.density == s316L.density  # Same base density

        # Aluminum alloys
        al6061 = aluminum.a6061
        _ = aluminum.a7075
        assert al6061.density == 2.7

        # Copper
        copper_material = copper
        assert copper_material.density == 8.96

    def test_load_plastics(self):
        """
        ## Plastic Materials

        Access plastic materials for 3D printing and engineering:
        """
        from pymat import pc, peek, pla, pmma

        # Engineering plastics
        assert peek.properties.manufacturing.print_nozzle_temp == 360

        # 3D printing plastics
        assert pla.properties.manufacturing.printable_fdm is True

        # Transparent plastics
        assert pmma.properties.optical.transparency == 92
        assert pc.properties.optical.transparency == 89

    def test_load_scintillators(self):
        """
        ## Scintillator Crystals

        Access scintillator materials for radiation detectors:
        """
        from pymat import bgo, lyso, nai

        # LYSO crystal
        assert lyso.properties.optical.light_yield == 32000
        assert lyso.properties.optical.refractive_index == 1.82

        # BGO crystal
        assert bgo.properties.optical.light_yield == 8500

        # NaI crystal
        assert nai.properties.optical.light_yield == 38000

    def test_load_gases(self):
        """
        ## Gas Materials

        Access gases for simulation and detector design:
        """
        from pymat import air, argon, helium, nitrogen, xenon

        # Common gases at STP
        assert 0.0012 < air.density < 0.0013  # g/cm³
        assert nitrogen.density > helium.density  # Helium is lightest
        assert xenon.density > argon.density  # Heavier noble gases

        # Detector gases
        assert argon.properties.compliance.radiation_resistant is True


class TestPropertyInheritance:
    """Examples showing property inheritance in hierarchies."""

    def test_inheritance_through_hierarchy(self):
        """
        ## Property Inheritance

        Child materials inherit properties from parents unless overridden:
        """
        from pymat import Material

        # Create material hierarchy
        root = Material(
            name="Base", density=7.8, thermal={"melting_point": 1500, "thermal_conductivity": 50}
        )

        grade1 = root.grade_("G1", mechanical={"yield_strength": 400})
        assert grade1.density == 7.8  # Inherited
        assert grade1.properties.mechanical.yield_strength == 400  # New property
        assert grade1.properties.thermal.melting_point == 1500  # Inherited

        # Override inherited property
        grade2 = root.grade_("G2", thermal={"melting_point": 1600})
        assert grade2.properties.thermal.melting_point == 1600  # Overridden


class TestBuild123dIntegration:
    """Examples with build123d CAD integration."""

    def test_mass_calculation(self):
        """
        ## Automatic Mass Calculation

        Materials with density automatically calculate shape mass:
        """
        pytest.importorskip("build123d")
        from build123d import Box

        from pymat import aluminum, stainless

        # 10x10x10 mm³ box = 1000 mm³ = 1 cm³
        steel_box = Box(10, 10, 10)
        stainless.apply_to(steel_box)

        # Density = 8.0 g/cm³, Volume = 1 cm³ → Mass = 8.0 g
        assert 7.9 < steel_box.mass < 8.1

        # Aluminum box
        al_box = Box(10, 10, 10)
        aluminum.apply_to(al_box)

        # Density = 2.7 g/cm³ → Mass = 2.7 g
        assert 2.6 < al_box.mass < 2.8

    def test_material_visualization_colors(self):
        """
        ## Material Visualization

        Materials render with appropriate colors for visualization:
        """
        pytest.importorskip("build123d")
        from build123d import Box

        from pymat import aluminum, lyso, stainless

        # Create shapes
        steel_part = Box(10, 10, 10)
        al_part = Box(10, 10, 10)
        crystal = Box(10, 10, 10)

        # Apply materials
        stainless.apply_to(steel_part)
        aluminum.apply_to(al_part)
        lyso.apply_to(crystal)

        # Verify colors are set
        assert steel_part.color is not None
        assert al_part.color is not None
        assert crystal.color is not None

        # Colors should differ
        assert steel_part.color != al_part.color
        assert crystal.color != steel_part.color


class TestProvenance:
    """Examples for the `_sources` provenance API (3.11+)."""

    def test_source_of_resolves_to_primary_paper(self):
        """
        ## Provenance — where every value comes from

        Every curated value carries a `_sources` entry pointing at a
        primary paper or handbook. `Material.source_of(path)` returns
        the `Source` for a property; short aliases (`"density"`) and
        fully-qualified paths (`"optical.light_yield"`) both resolve.
        """
        from pymat import bgo, inconel625

        # BGO's light yield comes from Weber & Monchamp's 1973 discovery paper.
        src = bgo.source_of("optical.light_yield")
        assert src.kind == "doi"
        assert src.ref == "10.1063/1.1662183"
        assert src.license == "proprietary-reference-only"

        # Inconel 625's density traces to MIL-HDBK-5J Table 6.3.3.0(b).
        ms = inconel625.source_of("mechanical.density")
        assert ms.kind == "handbook"
        assert ms.ref == "mil-hdbk-5j:p6-35"
        assert ms.license == "PD-USGov"

    def test_cite_emits_bibtex(self):
        """
        ## Citing values in publications

        `Material.cite(path)` returns a BibTeX entry for one property;
        `Material.cite()` (no arg) returns every source the material
        uses, deduplicated.
        """
        from pymat import bgo

        bib = bgo.cite("optical.light_yield")
        assert "@" in bib  # BibTeX entry type marker
        assert "10.1063/1.1662183" in bib  # the DOI is embedded


class TestUncertainty:
    """Examples for `_stddev` sugar and composition ranges (3.11+)."""

    def test_property_with_stddev_sibling(self, tmp_path):
        """
        ## Property values with uncertainty

        Add a `<prop>_stddev` sibling key to a property and the loader
        folds it into a `ufloat` (from the `uncertainties` package) at
        load time. The build123d boundary still receives a plain float
        (the nominal value) — `Material.density_g_mm3` strips the
        uncertainty so CAD math doesn't surprise downstream consumers.
        """
        from pymat import load_toml

        p = tmp_path / "steel.toml"
        p.write_text(
            "[steel]\n"
            'name = "Steel"\n'
            "[steel.mechanical]\n"
            "density_value = 7.85\n"
            'density_unit = "g/cm^3"\n'
            "density_stddev = 0.05\n"
        )
        steel = load_toml(p)["steel"]

        d = steel.properties.mechanical.density
        # `d` is a ufloat — arithmetic on it propagates uncertainty
        assert d.nominal_value == 7.85
        assert d.std_dev == 0.05

        # Plain-float view for build123d-style consumers
        assert steel.density_g_mm3 == 0.00785  # 7.85 g/cm³ → g/mm³

    def test_composition_with_grade_spec_ranges(self):
        """
        ## Composition with grade-spec ranges

        Alloy specs (AMS, ASTM, EN AW) typically give a tolerance window
        per element. The loader accepts `{nominal, min, max}` per element
        and folds it into a `ufloat` whose ±σ spans the spec window.
        """
        from pymat import aluminum

        # 6063 has min/max windows from the AZoM/ASM spec sheet
        a6063 = aluminum.a6063

        # Si is 0.2-0.6 wt% (nominal 0.4); the loader stores it as a ufloat
        si = a6063.composition["Si"]
        assert si.nominal_value == 0.004
        # ±σ is half the spec window
        assert si.std_dev == 0.002


class TestTemperatureCurves:
    """Examples for `<prop>_curve` T-dependent properties (3.11+)."""

    def test_property_curve_at_temperature(self, tmp_path):
        """
        ## Temperature-dependent properties

        For values that vary with T, attach a `<prop>_curve` sibling
        with `temps_K` knots and `values`. Then call `<prop>_at(T)` on
        the property group with a Pint temperature `Quantity`. Linear
        interpolation between knots; values clamp at the boundaries.
        """
        from pymat import load_toml
        from pymat.units import ureg

        p = tmp_path / "ofhc.toml"
        p.write_text(
            "[copper]\n"
            'name = "Copper"\n'
            "[copper.thermal]\n"
            "thermal_conductivity_value = 391\n"
            'thermal_conductivity_unit = "W/(m*K)"\n'
            "thermal_conductivity_curve = { "
            "temps_K = [77, 295, 500], "
            "values = [600, 391, 350] "
            "}\n"
        )
        copper = load_toml(p)["copper"]

        # Scalar still reads as the RT value
        assert copper.properties.thermal.thermal_conductivity == 391

        # _at(T) follows the curve
        k77 = copper.properties.thermal.thermal_conductivity_at(77 * ureg.kelvin)
        assert k77.to("W/(m*K)").magnitude == 600

        # Linear interp between 77 K and 295 K
        k186 = copper.properties.thermal.thermal_conductivity_at(186 * ureg.kelvin)
        assert 495 < k186.to("W/(m*K)").magnitude < 496


class TestCuratedCatalog:
    """Smoke tests for Phase 5 catalog additions (3.11)."""

    def test_modern_scintillators(self):
        """
        ## Modern scintillators

        The 3.11 release added GAGG:Ce, LSO:Ce, LaBr3:Ce, CeBr3, and
        SrI2:Eu, each cited to its primary measurement paper.
        """
        from pymat import cebr3, gagg, sri2

        # GAGG:Ce — the dotted child carries the doped scalars
        assert gagg.Ce.properties.optical.light_yield == 40000
        assert gagg.Ce.properties.optical.decay_time == 53

        # CeBr3 — fast, bright, intrinsic 4% resolution at 662 keV
        assert cebr3.density == 5.2
        assert cebr3.properties.optical.light_yield == 68000

        # SrI2:Eu — highest light yield in the catalog
        assert sri2.Eu.properties.optical.light_yield == 115000

    def test_aerospace_alloys(self):
        """
        ## Aerospace nickel-base superalloys

        Inconel 625 and 718 ship with MIL-HDBK-5J A-basis design
        allowables and Special Metals technical-bulletin thermal data.
        """
        from pymat import inconel625, inconel718

        assert inconel625.density == 8.44
        assert inconel625.properties.mechanical.tensile_strength == 820  # MPa, A-basis

        assert inconel718.density == 8.22
        # Inconel 718 STA — much higher Ftu than 625 annealed
        assert inconel718.properties.mechanical.tensile_strength == 1241
