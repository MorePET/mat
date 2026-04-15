"""
Factory functions for creating materials with dynamic/computed properties.

Use these when material properties depend on external parameters like temperature.

Note: All properties are stored with their standard units. Access Quantity objects
via the `*_qty` properties on the property objects for unit-aware calculations.

Example:
    water_20c = water(20)
    # Get density as float in g/cm³
    density_val = water_20c.properties.mechanical.density
    # Get density as Pint Quantity
    density_qty = water_20c.properties.mechanical.density_qty
    # Convert to other units
    density_kg_m3 = density_qty.to('kg/m^3')
"""

from __future__ import annotations

from typing import Optional

from .core import Material
from .properties import AllProperties


def water(temperature_c: float = 20.0, name: Optional[str] = None) -> Material:
    """
    Create water material at a specific temperature.

    Density varies with temperature using empirical formula.
    Valid range: 0°C to 100°C (liquid water at 1 atm).

    Args:
        temperature_c: Temperature in Celsius (default: 20°C)
        name: Optional custom name (default: "Water @ {temp}°C")

    Returns:
        Material instance with temperature-appropriate properties

    Example:
        from pymat.factories import water

        cold_water = water(4)      # Maximum density ~1.0 g/cm³
        hot_water = water(80)      # Lower density ~0.972 g/cm³
        room_temp = water()        # 20°C default
    """
    # Clamp temperature to valid liquid range
    t = max(0.0, min(100.0, temperature_c))

    # Density of water (g/cm³) - empirical formula
    # Maximum density at 4°C (~0.99997 g/cm³)
    # Source: Engineering Toolbox / CRC Handbook / Tanaka et al. (2001)
    # Parabolic approximation for 0-40°C, linear decrease for 40-100°C
    if t <= 40:
        density = 0.99997 * (1 - (t - 4) ** 2 / 119000)
    else:
        # Linear decrease from 40°C to 100°C
        density_40 = 0.99997 * (1 - (40 - 4) ** 2 / 119000)  # ~0.9891
        density = density_40 - 0.00035 * (t - 40)

    # Thermal conductivity (W/(m·K)) - varies with temperature
    # Approximate linear fit for 0-100°C
    thermal_conductivity = 0.569 + 0.0019 * t - 8e-6 * t**2

    # Specific heat (J/(kg·K)) - relatively constant but has minimum around 35°C
    specific_heat = 4217.6 - 3.4 * t + 0.05 * t**2 - 0.0003 * t**3

    # Dielectric constant decreases with temperature
    dielectric = 87.74 - 0.4 * t + 9.4e-4 * t**2

    # Refractive index (slight temperature dependence)
    refractive_index = 1.3330 - 0.00008 * t

    # Dynamic viscosity (mPa·s) - for reference
    # viscosity = 1.79 * exp(-0.0267 * t)  # Approximate

    props = AllProperties()
    props.mechanical.density = density
    props.thermal.thermal_conductivity = thermal_conductivity
    props.thermal.specific_heat = specific_heat
    props.thermal.melting_point = 0
    props.electrical.dielectric_constant = dielectric
    props.optical.refractive_index = refractive_index

    # PBR - water appearance
    props.pbr.base_color = (0.7, 0.85, 0.95, 0.3)
    props.pbr.metallic = 0.0
    props.pbr.roughness = 0.0
    props.pbr.transmission = 0.95
    props.pbr.ior = refractive_index

    mat_name = name or f"Water @ {temperature_c}°C"

    return Material(
        name=mat_name,
        formula="H2O",
        properties=props,
        _key=f"water_{int(temperature_c)}C",
    )


def air(
    temperature_c: float = 20.0, pressure_atm: float = 1.0, name: Optional[str] = None
) -> Material:
    """
    Create air material at specific temperature and pressure.

    Args:
        temperature_c: Temperature in Celsius (default: 20°C)
        pressure_atm: Pressure in atmospheres (default: 1.0)
        name: Optional custom name

    Returns:
        Material instance with computed properties

    Example:
        from pymat.factories import air

        room_air = air()
        cold_air = air(-20)
        high_altitude = air(15, 0.5)  # ~5500m altitude
    """
    t_kelvin = temperature_c + 273.15

    # Ideal gas law: ρ = PM/(RT)
    # M_air ≈ 28.97 g/mol, R = 8.314 J/(mol·K)
    # At 1 atm, 20°C: ρ ≈ 1.204 kg/m³
    density = (pressure_atm * 101325 * 0.02897) / (8.314 * t_kelvin) / 1000  # g/cm³

    # Thermal conductivity (W/(m·K))
    thermal_conductivity = 0.0241 + 7.7e-5 * temperature_c

    # Specific heat (J/(kg·K)) - relatively constant
    specific_heat = 1005

    props = AllProperties()
    props.mechanical.density = density
    props.thermal.thermal_conductivity = thermal_conductivity
    props.thermal.specific_heat = specific_heat
    props.optical.refractive_index = 1.000293  # At STP

    # Air is essentially invisible
    props.pbr.base_color = (0.9, 0.95, 1.0, 0.02)
    props.pbr.metallic = 0.0
    props.pbr.roughness = 0.0
    props.pbr.transmission = 0.99

    mat_name = name or f"Air @ {temperature_c}°C, {pressure_atm} atm"

    return Material(
        name=mat_name,
        formula="N2O2",  # Simplified
        properties=props,
        _key=f"air_{int(temperature_c)}C",
    )


def saline(
    concentration_pct: float = 0.9, temperature_c: float = 20.0, name: Optional[str] = None
) -> Material:
    """
    Create saline solution (NaCl in water).

    Args:
        concentration_pct: NaCl concentration by weight (default: 0.9% = physiological)
        temperature_c: Temperature in Celsius (default: 20°C)
        name: Optional custom name

    Returns:
        Material instance

    Example:
        from pymat.factories import saline

        physiological = saline()           # 0.9% NaCl
        seawater = saline(3.5)             # ~3.5% NaCl (approximate seawater)
        saturated = saline(26)             # Near saturation
    """
    # Start with water properties at temperature
    base_water = water(temperature_c)

    # Density increases with salt concentration
    # Approximate: ρ = ρ_water * (1 + 0.0068 * concentration)
    water_density = base_water.density
    density = water_density * (1 + 0.0068 * concentration_pct)

    props = AllProperties()
    props.mechanical.density = density
    props.thermal.thermal_conductivity = base_water.properties.thermal.thermal_conductivity
    props.thermal.specific_heat = base_water.properties.thermal.specific_heat * (
        1 - 0.004 * concentration_pct
    )
    props.optical.refractive_index = 1.333 + 0.0017 * concentration_pct

    # Slightly different appearance than pure water
    props.pbr.base_color = (0.75, 0.85, 0.9, 0.35)
    props.pbr.metallic = 0.0
    props.pbr.roughness = 0.0
    props.pbr.transmission = 0.9
    props.pbr.ior = props.optical.refractive_index

    mat_name = name or f"Saline {concentration_pct}% @ {temperature_c}°C"

    return Material(
        name=mat_name,
        formula="NaCl(aq)",
        properties=props,
        _key=f"saline_{concentration_pct}pct",
    )
