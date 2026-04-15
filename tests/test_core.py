"""
Test suite for pymat core functionality.

Tests the Material class, property inheritance, and chaining API.
"""

import pytest

from pymat import Material
from pymat.properties import AllProperties


class TestMaterialBasics:
    """Test basic Material instantiation and properties."""

    def test_material_creation(self):
        """Test creating a material."""
        mat = Material(name="Test Material", density=2.5)
        assert mat.name == "Test Material"
        assert mat.density == 2.5

    def test_material_with_properties(self):
        """Test material with detailed properties."""
        props = AllProperties()
        props.mechanical.density = 8.0
        props.mechanical.yield_strength = 250

        mat = Material(name="Steel", properties=props)
        assert mat.density == 8.0
        assert mat.properties.mechanical.yield_strength == 250

    def test_material_path(self):
        """Test material hierarchy path."""
        mat = Material(name="Base", _key="base")
        assert mat.path == "base"


class TestMaterialChaining:
    """Test the chainable API for material hierarchy."""

    def test_grade_chaining(self):
        """Test adding grades."""
        parent = Material(name="Stainless Steel", density=8.0)
        child = parent.grade_("s304", name="SS 304")

        assert child.grade == "s304"
        assert child.parent == parent
        assert child in parent._children.values()

    def test_temper_chaining(self):
        """Test adding tempers."""
        parent = Material(name="Aluminum", density=2.7)
        child = parent.temper_("T6", name="Aluminum T6")

        assert child.temper == "T6"
        assert child.parent == parent

    def test_treatment_chaining(self):
        """Test adding treatments."""
        parent = Material(name="Stainless 316L", density=8.0)
        child = parent.treatment_("passivated", name="316L Passivated")

        assert child.treatment == "passivated"

    def test_vendor_chaining(self):
        """Test adding vendors."""
        parent = Material(name="LYSO")
        child = parent.vendor_("saint_gobain", name="Saint-Gobain LYSO")

        assert child.vendor == "saint_gobain"

    def test_variant_chaining(self):
        """Test generic variants."""
        parent = Material(name="LYSO")
        child = parent.variant_("Ce", name="LYSO:Ce")

        assert child._key == "Ce"
        assert "Ce" in parent._children


class TestPropertyInheritance:
    """Test that properties inherit correctly through hierarchy."""

    def test_inherit_density(self):
        """Test density inheritance."""
        parent = Material(name="Parent", density=8.0)
        child = parent.grade_("child", name="Child Grade")

        assert parent.density == 8.0
        assert child.density == 8.0  # Inherited

    def test_inherit_and_override(self):
        """Test inheriting and overriding properties."""
        props = AllProperties()
        props.mechanical.density = 8.0
        props.mechanical.yield_strength = 200

        parent = Material(name="Parent", properties=props)

        # Use mechanical= dict to override properties
        child = parent.grade_("child", name="Child", mechanical={"yield_strength": 300})

        assert child.density == 8.0  # Inherited
        assert child.properties.mechanical.yield_strength == 300  # Overridden

    def test_deep_hierarchy_inheritance(self):
        """Test inheritance through multiple levels."""
        root = Material(name="Root", density=7.8)
        level1 = root.grade_("grade1", name="Grade 1")
        level2 = level1.temper_("T6", name="Grade1 T6")

        assert root.density == 7.8
        assert level1.density == 7.8  # Inherited
        assert level2.density == 7.8  # Inherited through two levels


class TestMaterialAccess:
    """Test accessing materials through hierarchy."""

    def test_getattr_access(self):
        """Test accessing child materials via attribute."""
        parent = Material(name="Parent")
        child = parent.grade_("child", name="Child")

        assert parent.child == child

    def test_getattr_error_on_missing(self):
        """Test error when accessing non-existent child."""
        parent = Material(name="Parent")

        with pytest.raises(AttributeError):
            _ = parent.nonexistent

    def test_nested_access(self):
        """Test accessing deeply nested materials."""
        root = Material(name="Root")
        # Use keys that don't conflict with field names
        mid = root.grade_("s304", name="Grade 304")
        leaf = mid.temper_("T6", name="T6")

        # Access by key through __getattr__
        assert root.s304.T6 == leaf


class TestMaterialInfo:
    """Test material information and inspection methods."""

    def test_path_generation(self):
        """Test hierarchical path generation."""
        root = Material(name="Root", _key="root")
        mid = root.grade_("s316L", name="316L")
        leaf = mid.treatment_("passivated", name="Passivated")

        assert root.path == "root"
        assert mid.path == "root.s316L"  # Preserves case from _key
        assert leaf.path == "root.s316L.passivated"

    def test_str_representation(self):
        """Test string representation."""
        mat = Material(name="Test Material", _key="test")
        assert "test" in str(mat)
        assert "Test Material" in str(mat)

    def test_repr(self):
        """Test repr."""
        mat = Material(name="Test", density=2.5, _key="test")
        repr_str = repr(mat)
        assert "test" in repr_str
        assert "2.5" in repr_str


class TestFormulas:
    """Test material formulas and composition."""

    def test_formula_storage(self):
        """Test storing chemical formula."""
        mat = Material(name="LYSO", formula="Lu1.8Y0.2SiO5")
        assert mat.formula == "Lu1.8Y0.2SiO5"

    def test_composition_storage(self):
        """Test storing composition."""
        comp = {"Lu": 1.8, "Y": 0.2, "Si": 1, "O": 5}
        mat = Material(name="LYSO", composition=comp)
        assert mat.composition == comp


class TestDensityCalculations:
    """Test density-related calculations."""

    def test_density_g_mm3(self):
        """Test density conversion to g/mm³."""
        mat = Material(name="Test", density=1000)  # 1000 g/cm³
        assert mat.density_g_mm3 == 1.0  # 1 g/mm³

    def test_mass_calculation(self):
        """Test mass calculation from volume."""
        mat = Material(name="Test", density=8.0)  # 8 g/cm³
        volume_mm3 = 1000  # 1 cm³ in mm³

        mass = mat.mass_from_volume_mm3(volume_mm3)
        assert mass == 8.0  # 8 grams
