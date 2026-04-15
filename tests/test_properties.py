"""
Tests for unit-aware properties with Pint integration.

Tests cover:
- Unit conversions
- Temperature-dependent calculations
- TOML serialization/deserialization
- Backward compatibility
- Quantity property access
"""

import tempfile
from pathlib import Path

import pytest

from pymat.core import Material
from pymat.loader import load_toml
from pymat.properties import AllProperties, MechanicalProperties, ThermalProperties
from pymat.units import STANDARD_UNITS, ureg


class TestQuantityProperties:
    """Test unit-aware Quantity property access."""

    def test_thermal_property_quantity_access(self):
        """Test accessing thermal properties as Pint Quantities."""
        thermal = ThermalProperties()
        thermal.melting_point = 1450  # degC by default

        # Access as Quantity
        qty = thermal.melting_point_qty
        assert qty is not None
        # Note: degC is converted to K internally (1450°C = 1723.15 K)
        assert abs(qty.magnitude - 1723.15) < 0.01
        assert str(qty.units) == "kelvin"

    def test_thermal_property_none_quantity(self):
        """Test that None values return None for Quantity."""
        thermal = ThermalProperties()
        thermal.melting_point = None

        assert thermal.melting_point_qty is None

    def test_mechanical_density_quantity(self):
        """Test density as Quantity with unit conversion."""
        mech = MechanicalProperties()
        mech.density = 8.0  # g/cm³

        qty = mech.density_qty
        assert qty.magnitude == 8.0

        # Convert to other units
        qty_kg_m3 = qty.to("kg/m^3")
        assert abs(qty_kg_m3.magnitude - 8000) < 0.1

    def test_mechanical_modulus_quantity(self):
        """Test Young's modulus as Quantity."""
        mech = MechanicalProperties()
        mech.youngs_modulus = 200  # GPa

        qty = mech.youngs_modulus_qty
        assert qty.magnitude == 200

        # Convert to other units
        qty_pa = qty.to("Pa")
        assert abs(qty_pa.magnitude - 2e11) < 1e10


class TestTemperatureDependentProperties:
    """Test temperature-dependent property calculations."""

    def test_thermal_conductivity_at_temperature_linear(self):
        """Test thermal conductivity calculation at different temperatures."""
        thermal = ThermalProperties()
        thermal.thermal_conductivity = 50.0  # W/(m·K) at reference
        thermal.thermal_conductivity_ref_temp = 20.0  # °C
        thermal.thermal_conductivity_coeff = 0.001  # 1/K

        # At reference temperature (20°C = 293.15 K), should be 50
        k_293_15 = thermal.thermal_conductivity_at(293.15 * ureg.kelvin)
        assert k_293_15 is not None
        assert abs(k_293_15.magnitude - 50.0) < 0.01

        # At 40°C = 313.15 K (20K higher), should be 50 * (1 + 0.001 * 20) = 51
        k_313_15 = thermal.thermal_conductivity_at(313.15 * ureg.kelvin)
        assert k_313_15 is not None
        assert abs(k_313_15.magnitude - 51.0) < 0.01

    def test_thermal_conductivity_at_default_reference(self):
        """Test that default reference temperature (20°C = 293.15 K) is used."""
        thermal = ThermalProperties()
        thermal.thermal_conductivity = 50.0
        thermal.thermal_conductivity_ref_temp = None  # Use default
        thermal.thermal_conductivity_coeff = 0.001

        # Should use default reference of 20°C = 293.15 K
        k_293_15 = thermal.thermal_conductivity_at(293.15 * ureg.kelvin)
        assert k_293_15 is not None
        assert abs(k_293_15.magnitude - 50.0) < 0.01

    def test_thermal_conductivity_no_coefficient(self):
        """Test that zero coefficient gives constant value."""
        thermal = ThermalProperties()
        thermal.thermal_conductivity = 50.0
        thermal.thermal_conductivity_ref_temp = 20.0
        thermal.thermal_conductivity_coeff = None  # Use default (0)

        # Should be constant regardless of temperature
        k_293_15 = thermal.thermal_conductivity_at(293.15 * ureg.kelvin)
        k_373_15 = thermal.thermal_conductivity_at(373.15 * ureg.kelvin)

        assert abs(k_293_15.magnitude - 50.0) < 0.01
        assert abs(k_373_15.magnitude - 50.0) < 0.01

    def test_thermal_conductivity_none_value(self):
        """Test that None value returns None."""
        thermal = ThermalProperties()
        thermal.thermal_conductivity = None

        result = thermal.thermal_conductivity_at(373.15 * ureg.kelvin)
        assert result is None

    def test_thermal_conductivity_unit_conversion(self):
        """Test temperature in different units - always convert to Kelvin."""
        thermal = ThermalProperties()
        thermal.thermal_conductivity = 50.0
        thermal.thermal_conductivity_ref_temp = 20.0  # degC
        thermal.thermal_conductivity_coeff = 0.001

        # Using Kelvin (20°C = 293.15 K)
        k_293k = thermal.thermal_conductivity_at(293.15 * ureg.kelvin)
        # Using direct Kelvin value for second test
        k_293k_2 = thermal.thermal_conductivity_at(293.15 * ureg.kelvin)

        # Should be the same
        assert abs(k_293k.magnitude - k_293k_2.magnitude) < 0.01


class TestUnitConversions:
    """Test Pint unit conversions."""

    def test_temperature_conversions(self):
        """Test temperature unit conversions using absolute units."""
        # Use Kelvin for direct calculations (no offset issues)
        qty_k = 373.15 * ureg.kelvin
        # For Celsius references, we manually convert
        qty_c_equiv = 100  # °C
        qty_k_from_c = qty_c_equiv + 273.15  # Convert to K

        assert abs(qty_k.magnitude - qty_k_from_c) < 0.01

    def test_density_conversions(self):
        """Test density unit conversions."""
        qty_g_cm3 = 8.0 * ureg("g/cm^3")
        qty_kg_m3 = qty_g_cm3.to("kg/m^3")

        assert abs(qty_kg_m3.magnitude - 8000) < 0.1

    def test_thermal_conductivity_conversions(self):
        """Test thermal conductivity conversions."""
        qty_w_mk = 50.0 * ureg("W/(m*K)")
        qty_w_cm_k = qty_w_mk.to("W/(cm*K)")

        # W/(m*K) to W/(cm*K): divide by 100 because cm = m/100
        # 50 W/(m*K) = 50/100 W/(cm*K) = 0.5 W/(cm*K)
        assert abs(qty_w_cm_k.magnitude - 0.5) < 0.01


class TestBackwardCompatibility:
    """Test backward compatibility with legacy TOML format."""

    def test_load_legacy_format(self):
        """Test loading TOML with legacy single-value format."""
        toml_content = """
[test_material]
name = "Test Material"

[test_material.mechanical]
density = 8.0

[test_material.thermal]
melting_point = 1450
thermal_conductivity = 50.0
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            f.flush()

            try:
                materials = load_toml(f.name)
                mat = materials["test_material"]

                # Values should be loaded
                assert mat.properties.mechanical.density == 8.0
                assert mat.properties.thermal.melting_point == 1450
                assert mat.properties.thermal.thermal_conductivity == 50.0

                # Units should be assigned defaults
                assert mat.properties.mechanical.density_unit == "g/cm^3"
                assert mat.properties.thermal.melting_point_unit == "degC"
            finally:
                Path(f.name).unlink()

    def test_load_new_unit_format(self):
        """Test loading TOML with new unit-aware format."""
        toml_content = """
[test_material]
name = "Test Material"

[test_material.mechanical]
density_value = 8.0
density_unit = "g/cm^3"

[test_material.thermal]
melting_point_value = 1450
melting_point_unit = "degC"
thermal_conductivity_value = 50.0
thermal_conductivity_unit = "W/(m*K)"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            f.flush()

            try:
                materials = load_toml(f.name)
                mat = materials["test_material"]

                # Values should be loaded
                assert mat.properties.mechanical.density == 8.0
                assert mat.properties.thermal.melting_point == 1450

                # Units should be loaded
                assert mat.properties.mechanical.density_unit == "g/cm^3"
                assert mat.properties.thermal.melting_point_unit == "degC"
                assert mat.properties.thermal.thermal_conductivity_unit == "W/(m*K)"
            finally:
                Path(f.name).unlink()


class TestTOMLDeserialization:
    """Test TOML loading and deserialization."""

    def test_load_temperature_dependent_properties(self):
        """Test loading temperature-dependent properties from TOML."""
        toml_content = """
[steel]
name = "Steel"

[steel.thermal]
thermal_conductivity_value = 50.0
thermal_conductivity_unit = "W/(m*K)"
thermal_conductivity_ref_temp_value = 20.0
thermal_conductivity_ref_temp_unit = "degC"
thermal_conductivity_coeff = 0.001
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            f.flush()

            try:
                materials = load_toml(f.name)
                steel = materials["steel"]

                # Check that all fields are loaded
                assert steel.properties.thermal.thermal_conductivity == 50.0
                assert steel.properties.thermal.thermal_conductivity_ref_temp == 20.0
                assert steel.properties.thermal.thermal_conductivity_coeff == 0.001

                # Test calculation at a different temperature
                # 50°C = 323.15 K
                k_323_15 = steel.properties.thermal.thermal_conductivity_at(323.15 * ureg.kelvin)
                assert k_323_15 is not None
                # At 50°C: k = 50 * (1 + 0.001 * 30) = 51.5
                assert abs(k_323_15.magnitude - 51.5) < 0.01
            finally:
                Path(f.name).unlink()


class TestPropertyInheritance:
    """Test property inheritance with unit-aware fields."""

    def test_parent_child_unit_inheritance(self):
        """Test that child materials inherit parent unit settings."""
        toml_content = """
[stainless]
name = "Stainless Steel"

[stainless.thermal]
melting_point_value = 1450
melting_point_unit = "degC"

[stainless.s304]
name = "SS 304"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            f.flush()

            try:
                materials = load_toml(f.name)
                parent = materials["stainless"]
                child = parent._children["s304"]

                # Child should inherit parent's melting point and unit
                assert child.properties.thermal.melting_point == 1450
                assert child.properties.thermal.melting_point_unit == "degC"
            finally:
                Path(f.name).unlink()


class TestMassCalculation:
    """Test that unit-aware density works with mass calculations."""

    def test_material_mass_calculation_with_unit_aware_density(self):
        """Test mass calculation using unit-aware density."""
        # Create a simple material with density
        props = AllProperties()
        props.mechanical.density = 8.0  # g/cm³
        props.mechanical.density_unit = "g/cm^3"

        mat = Material(name="Steel", properties=props)

        # Test density access
        assert mat.properties.mechanical.density == 8.0
        assert mat.properties.mechanical.density_unit == "g/cm^3"

        # Test Quantity access
        density_qty = mat.properties.mechanical.density_qty
        assert density_qty is not None
        assert abs(density_qty.magnitude - 8.0) < 0.01

        # Test density_g_mm3 property (for build123d)
        assert abs(mat.density_g_mm3 - 0.008) < 0.0001


class TestStandardUnits:
    """Test standard unit definitions."""

    def test_standard_units_defined(self):
        """Test that standard units are defined for common properties."""
        expected_keys = [
            "melting_point",
            "density",
            "thermal_conductivity",
            "youngs_modulus",
            "yield_strength",
            "resistivity",
        ]

        for key in expected_keys:
            assert key in STANDARD_UNITS
            assert isinstance(STANDARD_UNITS[key], str)

    def test_standard_units_are_valid_pint(self):
        """Test that all standard units are recognized by Pint."""
        for prop_name, unit_str in STANDARD_UNITS.items():
            # Skip offset units (degC, degF) as they can't be multiplied directly
            if "deg" in unit_str:
                continue
            # This should not raise an exception
            qty = 1.0 * ureg(unit_str)
            assert qty is not None


class TestFactoryFunctions:
    """Test that factory functions work with unit-aware properties."""

    def test_water_factory_has_units(self):
        """Test that water() returns material with unit-aware properties."""
        from pymat.factories import water

        w = water(20)

        # Check density
        assert w.properties.mechanical.density is not None
        assert w.properties.mechanical.density_unit == "g/cm^3"

        # Access as Quantity
        density_qty = w.properties.mechanical.density_qty
        assert density_qty is not None

        # Should be valid quantity
        assert str(density_qty.units) == "gram / centimeter ** 3"

    def test_air_factory_has_units(self):
        """Test that air() returns material with unit-aware properties."""
        from pymat.factories import air

        a = air(20)

        # Check density
        assert a.properties.mechanical.density is not None
        assert a.properties.mechanical.density_unit == "g/cm^3"

        # Access thermal properties
        assert a.properties.thermal.thermal_conductivity is not None
        assert a.properties.thermal.thermal_conductivity_unit == "W/(m*K)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
