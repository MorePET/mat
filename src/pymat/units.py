"""
Unit registry and standard unit definitions for Pint integration.

Provides a shared UnitRegistry instance and standard unit defaults for all material properties.
"""

from pint import UnitRegistry

# Shared unit registry instance
ureg = UnitRegistry()

# Standard units for each property type
# Used for backward compatibility when TOML files don't specify units
STANDARD_UNITS = {
    # Temperature
    "melting_point": "degC",
    "glass_transition": "degC",
    "max_service_temp": "degC",
    "min_service_temp": "degC",
    "thermal_conductivity_ref_temp": "degC",
    # Mechanical properties
    "density": "g/cm^3",
    "youngs_modulus": "GPa",
    "shear_modulus": "GPa",
    "yield_strength": "MPa",
    "tensile_strength": "MPa",
    "compressive_strength": "MPa",
    "fracture_toughness": "MPa*m^0.5",
    # Thermal properties
    "thermal_conductivity": "W/(m*K)",
    "specific_heat": "J/(kg*K)",
    "thermal_expansion": "1/K",
    # Electrical properties
    "resistivity": "ohm*m",
    "conductivity": "S/m",
    "breakdown_voltage": "kV/mm",
    "volume_resistivity": "ohm*cm",
    # Manufacturing properties
    "cutting_speed": "m/min",
    "feed_rate": "mm",
    "print_nozzle_temp": "degC",
    "print_bed_temp": "degC",
    "print_chamber_temp": "degC",
    # Sourcing
    "cost_per_kg": "dimensionless",  # Cost in arbitrary currency per kg
    "lead_time_weeks": "week",
}
