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
        assert aluminum.properties.pbr.base_color[:3] == (0.88, 0.88, 0.88)

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
            pbr={"base_color": (0.75, 0.75, 0.77, 1.0), "metallic": 1.0},
        )

        assert steel.properties.mechanical.density == 8.0
        assert steel.properties.mechanical.youngs_modulus == 193
        assert steel.properties.thermal.melting_point == 1450
        assert steel.properties.pbr.metallic == 1.0

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
            pbr={"transmission": 0.8},  # Rendering: how transparent it looks
        )

        # Physics properties (measured)
        assert glass.properties.optical.transparency == 95
        assert glass.properties.optical.refractive_index == 1.517

        # Visualization properties (rendering)
        assert glass.properties.pbr.base_color[3] == 0.8  # Alpha
        assert glass.properties.pbr.transmission == 0.8

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
            pbr={"base_color": (0.0, 1.0, 1.0, 0.85), "transmission": 0.85},
        )

        assert lyso_crystal.properties.optical.light_yield == 32000
        assert lyso_crystal.properties.optical.decay_time == 41
        assert lyso_crystal.properties.pbr.transmission == 0.85


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
