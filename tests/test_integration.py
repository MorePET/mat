"""
Integration tests for pymat.

Tests interactions between components.
"""

import pytest

from pymat import load_category


class TestLoadAndAccess:
    """Test loading materials and accessing them."""

    def test_load_metals_and_access_hierarchy(self):
        """Test loading metals and navigating hierarchy."""
        materials = load_category("metals")

        stainless = materials["stainless"]
        assert stainless.name == "Stainless Steel"

        # Access through hierarchy
        s316L = stainless.s316L
        assert s316L.name == "Stainless Steel 316L"
        assert s316L.grade == "316L"

    def test_load_scintillators_and_access_vendors(self):
        """Test loading scintillators and vendor hierarchy."""
        materials = load_category("scintillators")

        lyso = materials["lyso"]
        lyso_ce = lyso.Ce
        vendor = lyso_ce.saint_gobain
        prelude = vendor.prelude420

        assert prelude.name == "Saint-Gobain PreLude 420 LYSO:Ce"


class TestApplyToShape:
    """Test applying materials to shapes."""

    def test_apply_material_to_box(self):
        """Test applying material to a build123d shape."""
        pytest.importorskip("build123d")

        from build123d import Box

        from pymat import stainless

        shape = Box(10, 20, 30)
        stainless.s304.apply_to(shape)

        assert shape.material.name == "Stainless Steel 304"
        assert shape.mass > 0

    def test_apply_scintillator_to_shape(self):
        """Test applying scintillator material to shape."""
        pytest.importorskip("build123d")

        from build123d import Box

        from pymat import lyso

        shape = Box(10, 10, 30)
        lyso.Ce.saint_gobain.prelude420.apply_to(shape)

        material = shape.material
        assert "LYSO" in material.name
        assert material.properties.optical.light_yield == 34000


class TestPropertyAccess:
    """Test accessing various properties through loaded materials."""

    def test_access_mechanical_properties(self):
        """Test accessing mechanical properties."""
        materials = load_category("metals")
        al = materials["aluminum"]

        assert al.properties.mechanical.density == 2.7
        assert al.properties.mechanical.youngs_modulus == 69

    def test_access_optical_properties(self):
        """Test accessing optical properties."""
        materials = load_category("scintillators")
        bgo = materials["bgo"]

        assert bgo.properties.optical.refractive_index == 2.15
        assert bgo.properties.optical.light_yield == 8500
        assert bgo.properties.optical.decay_time == 300

    def test_access_pbr_properties(self):
        """Test accessing PBR rendering properties."""
        materials = load_category("metals")
        copper = materials.get("copper")

        if copper:
            pbr = copper.properties.pbr
            assert pbr.base_color is not None
            assert pbr.metallic == 1.0


class TestCategoryLoading:
    """Test loading different material categories."""

    def test_all_categories_load(self):
        """Test that all material categories can be loaded."""
        categories = ["metals", "scintillators", "plastics", "ceramics", "electronics"]

        for category in categories:
            materials = load_category(category)
            assert len(materials) > 0

    def test_materials_have_density(self):
        """Test that most materials have density defined."""
        materials = load_category("metals")

        loaded_materials = [m for m in materials.values()]
        assert len(loaded_materials) > 0

        # Most should have density
        with_density = [m for m in loaded_materials if m.density and m.density > 0]
        assert len(with_density) > len(loaded_materials) * 0.7  # At least 70%


class TestChainedHierarchy:
    """Test complex chained hierarchies."""

    def test_aluminum_full_hierarchy(self):
        """Test complete aluminum hierarchy."""
        materials = load_category("metals")

        al = materials["aluminum"]
        a6061 = al.a6061
        t6 = a6061.T6
        anodized = t6.anodized

        # Verify chain
        assert al.name == "Aluminum"
        assert a6061.grade == "6061"
        assert t6.temper == "T6"
        assert anodized.treatment == "anodized"

        # Verify inheritance
        assert anodized.density == al.density

    def test_stainless_treatments(self):
        """Test stainless steel with treatments."""
        materials = load_category("metals")

        ss = materials["stainless"]
        s316L = ss.s316L

        # Check treatments
        passivated = s316L.passivated
        electropolished = s316L.electropolished

        assert passivated.treatment == "passivated"
        assert electropolished.treatment == "electropolished"


class TestMassCalculation:
    """Test mass calculations with real materials."""

    def test_mass_aluminum_box(self):
        """Test calculating mass of aluminum box."""
        pytest.importorskip("build123d")

        from build123d import Box

        from pymat import aluminum

        # 10x10x10 mm³ box = 1000 mm³ = 1 cm³
        shape = Box(10, 10, 10)
        aluminum.apply_to(shape)

        # Density is 2.7 g/cm³, volume is 1 cm³
        expected_mass = 2.7
        assert abs(shape.mass - expected_mass) < 0.1

    def test_mass_steel_box(self):
        """Test calculating mass of steel box."""
        pytest.importorskip("build123d")

        from build123d import Box

        from pymat import stainless

        # 10x10x10 mm³ box = 1000 mm³ = 1 cm³
        shape = Box(10, 10, 10)
        stainless.apply_to(shape)

        # Density is 8.0 g/cm³, volume is 1 cm³
        expected_mass = 8.0
        assert abs(shape.mass - expected_mass) < 0.1


@pytest.mark.skip(reason="Category namespace feature not implemented in v2.0.0")
class TestCategoryNamespaces:
    """Test category namespace imports (plastics, gases, metals, etc.)."""

    def test_plastics_namespace_access(self):
        """Test accessing materials via plastics namespace."""
        from pymat import plastics

        pmma = plastics.pmma
        assert pmma.name == "PMMA (Acrylic)"
        assert pmma.density > 0

    def test_gases_namespace_access(self):
        """Test accessing materials via gases namespace."""
        from pymat import gases

        air = gases.air
        assert air is not None
        assert "air" in air.name.lower() or "Air" in air.name

    def test_metals_namespace_access(self):
        """Test accessing materials via metals namespace."""
        from pymat import metals

        stainless = metals.stainless
        assert stainless.name == "Stainless Steel"

    def test_liquids_namespace_access(self):
        """Test accessing materials via liquids namespace."""
        from pymat import liquids

        water = liquids.water
        assert water is not None

    def test_ceramics_namespace_access(self):
        """Test accessing materials via ceramics namespace."""
        from pymat import ceramics

        alumina = ceramics.alumina
        assert alumina is not None

    def test_scintillators_namespace_access(self):
        """Test accessing materials via scintillators namespace."""
        from pymat import scintillators

        lyso = scintillators.lyso
        assert "LYSO" in lyso.name

    def test_electronics_namespace_access(self):
        """Test accessing materials via electronics namespace."""
        from pymat import electronics

        fr4 = electronics.fr4
        assert fr4 is not None

    def test_namespace_error_on_wrong_category(self):
        """Test error when accessing material from wrong category."""
        from pymat import plastics

        with pytest.raises(AttributeError) as exc_info:
            _ = plastics.stainless  # stainless is in metals, not plastics

        assert "plastics" in str(exc_info.value)
        assert "stainless" in str(exc_info.value)

    def test_namespace_dir(self):
        """Test IDE autocompletion support via __dir__."""
        from pymat import plastics

        available = dir(plastics)
        assert "pmma" in available
        assert "peek" in available
        assert "ptfe" in available

    def test_namespace_repr(self):
        """Test namespace string representation."""
        from pymat import gases, plastics

        assert "plastics" in repr(plastics)
        assert "gases" in repr(gases)

    def test_namespace_hierarchy_access(self):
        """Test accessing material hierarchy through namespace."""
        from pymat import metals

        stainless = metals.stainless
        s316L = stainless.s316L

        assert s316L.grade == "316L"
        assert s316L.name == "Stainless Steel 316L"
