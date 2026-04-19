"""
Property dataclasses for materials.

Organized by physical/engineering domain:
- MechanicalProperties: structural and deformation behavior
- ThermalProperties: temperature-related properties
- ElectricalProperties: electrical conductivity and dielectric behavior
- OpticalProperties: light interaction and scintillator-specific properties
- PBRProperties: physically-based rendering for visualization
- ManufacturingProperties: machinability, printability, weldability
- ComplianceProperties: regulatory and material suitability
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from pint import Quantity

from .units import ureg


@dataclass
class MechanicalProperties:
    """Structural and deformation behavior."""

    density: Optional[float] = None  # g/cm³
    density_unit: str = "g/cm^3"
    youngs_modulus: Optional[float] = None  # GPa
    youngs_modulus_unit: str = "GPa"
    shear_modulus: Optional[float] = None  # GPa
    shear_modulus_unit: str = "GPa"
    poissons_ratio: Optional[float] = None  # dimensionless
    yield_strength: Optional[float] = None  # MPa
    yield_strength_unit: str = "MPa"
    tensile_strength: Optional[float] = None  # MPa
    tensile_strength_unit: str = "MPa"
    compressive_strength: Optional[float] = None  # MPa
    compressive_strength_unit: str = "MPa"
    elongation: Optional[float] = None  # % at break
    hardness_vickers: Optional[float] = None  # HV (Vickers hardness)
    hardness_rockwell: Optional[float] = None  # HR (Rockwell hardness)
    fracture_toughness: Optional[float] = None  # MPa·m^0.5
    fracture_toughness_unit: str = "MPa*m^0.5"

    # Quantity properties for unit-aware access
    @property
    def density_qty(self) -> Optional[Quantity]:
        """Get density as Pint Quantity."""
        if self.density is None:
            return None
        return self.density * ureg(self.density_unit)

    @property
    def youngs_modulus_qty(self) -> Optional[Quantity]:
        """Get Young's modulus as Pint Quantity."""
        if self.youngs_modulus is None:
            return None
        return self.youngs_modulus * ureg(self.youngs_modulus_unit)

    @property
    def shear_modulus_qty(self) -> Optional[Quantity]:
        """Get shear modulus as Pint Quantity."""
        if self.shear_modulus is None:
            return None
        return self.shear_modulus * ureg(self.shear_modulus_unit)

    @property
    def yield_strength_qty(self) -> Optional[Quantity]:
        """Get yield strength as Pint Quantity."""
        if self.yield_strength is None:
            return None
        return self.yield_strength * ureg(self.yield_strength_unit)

    @property
    def tensile_strength_qty(self) -> Optional[Quantity]:
        """Get tensile strength as Pint Quantity."""
        if self.tensile_strength is None:
            return None
        return self.tensile_strength * ureg(self.tensile_strength_unit)

    @property
    def compressive_strength_qty(self) -> Optional[Quantity]:
        """Get compressive strength as Pint Quantity."""
        if self.compressive_strength is None:
            return None
        return self.compressive_strength * ureg(self.compressive_strength_unit)

    @property
    def fracture_toughness_qty(self) -> Optional[Quantity]:
        """Get fracture toughness as Pint Quantity."""
        if self.fracture_toughness is None:
            return None
        return self.fracture_toughness * ureg(self.fracture_toughness_unit)


@dataclass
class ThermalProperties:
    """Temperature-related properties."""

    melting_point: Optional[float] = None  # °C
    melting_point_unit: str = "degC"
    glass_transition: Optional[float] = None  # °C (for polymers)
    glass_transition_unit: str = "degC"
    thermal_conductivity: Optional[float] = None  # W/(m·K)
    thermal_conductivity_unit: str = "W/(m*K)"
    thermal_conductivity_ref_temp: Optional[float] = None  # Reference temperature
    thermal_conductivity_ref_temp_unit: str = "degC"
    thermal_conductivity_coeff: Optional[float] = None  # Linear coefficient (1/K)
    specific_heat: Optional[float] = None  # J/(kg·K)
    specific_heat_unit: str = "J/(kg*K)"
    thermal_expansion: Optional[float] = None  # µm/(m·K) or 1e-6/K
    thermal_expansion_unit: str = "1/K"
    max_service_temp: Optional[float] = None  # °C
    max_service_temp_unit: str = "degC"
    min_service_temp: Optional[float] = None  # °C
    min_service_temp_unit: str = "degC"
    thermal_shock_resistance: Optional[str] = None  # "excellent", "good", "fair", "poor"

    # Quantity properties for unit-aware access
    @property
    def melting_point_qty(self) -> Optional[Quantity]:
        """Get melting point as Pint Quantity."""
        if self.melting_point is None:
            return None
        # Convert to Kelvin for Pint (to avoid offset unit issues)
        # degC = K - 273.15, but we return as the original unit for user convenience
        if self.melting_point_unit == "degC":
            # Store as degC but convert to K for Pint Quantity
            return (self.melting_point + 273.15) * ureg.kelvin
        return self.melting_point * ureg(self.melting_point_unit)

    @property
    def glass_transition_qty(self) -> Optional[Quantity]:
        """Get glass transition temperature as Pint Quantity."""
        if self.glass_transition is None:
            return None
        if self.glass_transition_unit == "degC":
            return (self.glass_transition + 273.15) * ureg.kelvin
        return self.glass_transition * ureg(self.glass_transition_unit)

    @property
    def thermal_conductivity_qty(self) -> Optional[Quantity]:
        """Get thermal conductivity as Pint Quantity."""
        if self.thermal_conductivity is None:
            return None
        return self.thermal_conductivity * ureg(self.thermal_conductivity_unit)

    @property
    def specific_heat_qty(self) -> Optional[Quantity]:
        """Get specific heat as Pint Quantity."""
        if self.specific_heat is None:
            return None
        return self.specific_heat * ureg(self.specific_heat_unit)

    @property
    def thermal_expansion_qty(self) -> Optional[Quantity]:
        """Get thermal expansion coefficient as Pint Quantity."""
        if self.thermal_expansion is None:
            return None
        return self.thermal_expansion * ureg(self.thermal_expansion_unit)

    @property
    def max_service_temp_qty(self) -> Optional[Quantity]:
        """Get maximum service temperature as Pint Quantity."""
        if self.max_service_temp is None:
            return None
        if self.max_service_temp_unit == "degC":
            return (self.max_service_temp + 273.15) * ureg.kelvin
        return self.max_service_temp * ureg(self.max_service_temp_unit)

    @property
    def min_service_temp_qty(self) -> Optional[Quantity]:
        """Get minimum service temperature as Pint Quantity."""
        if self.min_service_temp is None:
            return None
        if self.min_service_temp_unit == "degC":
            return (self.min_service_temp + 273.15) * ureg.kelvin
        return self.min_service_temp * ureg(self.min_service_temp_unit)

    def thermal_conductivity_at(self, temp: Quantity) -> Optional[Quantity]:
        """
        Calculate thermal conductivity at given temperature.

        Uses linear temperature dependence:
            k(T) = k(T_ref) * (1 + coeff * (T - T_ref))

        Args:
            temp: Temperature as Pint Quantity in Kelvin (e.g., 373.15 * ureg.kelvin)
                  Note: Input must be in Kelvin to avoid Pint offset unit issues

        Returns:
            Thermal conductivity as Pint Quantity, or None if not available

        Raises:
            ValueError: If temperature is not in Kelvin or calculation fails
        """
        if self.thermal_conductivity is None:
            return None

        # Default reference temperature if not specified (20°C = 293.15 K)
        if self.thermal_conductivity_ref_temp is None:
            t_ref_k = 293.15
        else:
            # Convert reference temp to Kelvin
            t_ref_c = self.thermal_conductivity_ref_temp
            t_ref_k = t_ref_c + 273.15

        # Default coefficient if not specified
        coeff = self.thermal_conductivity_coeff or 0.0

        # Extract temperature in Kelvin
        try:
            temp_k = temp.to(ureg.kelvin).magnitude
        except Exception as e:
            raise ValueError(
                f"Temperature must be in absolute units (Kelvin). Got {temp.units}: {e}"
            )

        # Calculate delta T in Kelvin
        delta_t_k = temp_k - t_ref_k

        # Linear: k(T) = k(T_ref) * (1 + coeff * delta_T)
        k_ref = self.thermal_conductivity * ureg(self.thermal_conductivity_unit)
        return k_ref * (1 + coeff * delta_t_k)


@dataclass
class ElectricalProperties:
    """Electrical conductivity and dielectric behavior."""

    resistivity: Optional[float] = None  # Ω·m
    resistivity_unit: str = "ohm*m"
    conductivity: Optional[float] = None  # S/m
    conductivity_unit: str = "S/m"
    dielectric_constant: Optional[float] = None  # relative permittivity (εr)
    dielectric_loss_tangent: Optional[float] = None  # tan(δ)
    breakdown_voltage: Optional[float] = None  # kV/mm
    breakdown_voltage_unit: str = "kV/mm"
    volume_resistivity: Optional[float] = None  # Ω·cm
    volume_resistivity_unit: str = "ohm*cm"

    # Quantity properties for unit-aware access
    @property
    def resistivity_qty(self) -> Optional[Quantity]:
        """Get resistivity as Pint Quantity."""
        if self.resistivity is None:
            return None
        return self.resistivity * ureg(self.resistivity_unit)

    @property
    def conductivity_qty(self) -> Optional[Quantity]:
        """Get conductivity as Pint Quantity."""
        if self.conductivity is None:
            return None
        return self.conductivity * ureg(self.conductivity_unit)

    @property
    def breakdown_voltage_qty(self) -> Optional[Quantity]:
        """Get breakdown voltage as Pint Quantity."""
        if self.breakdown_voltage is None:
            return None
        return self.breakdown_voltage * ureg(self.breakdown_voltage_unit)

    @property
    def volume_resistivity_qty(self) -> Optional[Quantity]:
        """Get volume resistivity as Pint Quantity."""
        if self.volume_resistivity is None:
            return None
        return self.volume_resistivity * ureg(self.volume_resistivity_unit)


@dataclass
class OpticalProperties:
    """
    Physical optical properties (measured values, physics calculations).

    These are PHYSICS properties, not visualization/rendering properties.
    For visualization, see PBRProperties.
    """

    # Basic optical properties
    refractive_index: Optional[float] = None  # n at 550nm (default)
    transparency: Optional[float] = None  # % transmission (0-100) - MEASURED VALUE
    absorption_coefficient: Optional[float] = None  # 1/cm
    absorption_length: Optional[float] = None  # mm (inverse of coefficient)

    # Scintillator properties (detector physics)
    light_yield: Optional[float] = None  # photons/MeV
    decay_time: Optional[float] = None  # ns (mean decay time)
    rise_time: Optional[float] = None  # ns
    emission_peak: Optional[float] = None  # nm (peak emission wavelength)
    emission_range: Optional[tuple] = None  # (min_nm, max_nm)

    # Radiation interaction (detector/shielding physics)
    radiation_length: Optional[float] = None  # cm (X₀ for photons)
    interaction_length: Optional[float] = None  # cm (λ for hadrons)
    moliere_radius: Optional[float] = None  # cm
    energy_resolution: Optional[float] = None  # % at 1 MeV (for detectors)


@dataclass
class PBRProperties:
    """
    Physically-based rendering properties for visualization (NOT physics).

    These control how the material LOOKS in 3D viewers and renders.
    They may differ from physical optical properties intentionally.

    For physics/measured optical properties, see OpticalProperties.
    """

    # Surface appearance
    base_color: tuple = (0.8, 0.8, 0.8, 1.0)  # RGBA (0-1) - Alpha is VISUAL opacity
    metallic: float = 0.0  # 0=dielectric, 1=metal
    roughness: float = 0.5  # 0=glossy, 1=rough
    emissive: tuple = (0, 0, 0)  # RGB emitted light

    # Transparency (RENDERING property, not physical measurement)
    ior: float = 1.5  # index of refraction (for rendering)
    transmission: float = 0.0  # 0=opaque, 1=transparent (volumetric)
    clearcoat: float = 0.0  # secondary glossy layer

    # Texture maps (paths or URIs)
    base_color_map: Optional[str] = None  # albedo / diffuse texture
    normal_map: Optional[str] = None
    roughness_map: Optional[str] = None
    metallic_map: Optional[str] = None
    ambient_occlusion_map: Optional[str] = None

    def to_dict(self) -> dict:
        """
        Serialize to a Three.js ``MeshPhysicalMaterial`` dict.

        Makes this class conform to the `pymat.pbr.PbrSource` Protocol
        so it can be assigned to `Material.pbr_source` as the
        lightweight, in-tree, zero-dependency backend. For full
        MaterialX / texture-library support, use
        `threejs_materials.PbrProperties` instead (install the
        `[pbr]` extra).

        Keys are Three.js camelCase. Defaults are omitted so the
        result stays compact.
        """
        out: dict = {}
        r, g, b, a = self.base_color
        out["color"] = [r, g, b]
        if self.metallic != 0.0:
            out["metalness"] = self.metallic
        if self.roughness != 0.5:
            out["roughness"] = self.roughness
        if self.emissive != (0, 0, 0):
            out["emissive"] = list(self.emissive)
        if self.ior != 1.5:
            out["ior"] = self.ior
        if self.transmission > 0.0:
            out["transmission"] = self.transmission
        if self.clearcoat > 0.0:
            out["clearcoat"] = self.clearcoat
        if a < 1.0:
            out["opacity"] = a
            out["transparent"] = True
        # Texture maps — keys use Three.js naming (normalMap, etc.).
        if self.base_color_map is not None:
            out["map"] = self.base_color_map  # Three.js color channel is plain `map`
        if self.normal_map is not None:
            out["normalMap"] = self.normal_map
        if self.roughness_map is not None:
            out["roughnessMap"] = self.roughness_map
        if self.metallic_map is not None:
            out["metalnessMap"] = self.metallic_map
        if self.ambient_occlusion_map is not None:
            out["aoMap"] = self.ambient_occlusion_map
        return out


@dataclass
class ManufacturingProperties:
    """Machinability, weldability, printability."""

    # General manufacturability
    machinability: Optional[float] = None  # % relative to free-cutting steel (100%)
    weldability: Optional[str] = None  # "excellent", "good", "fair", "poor"
    formability: Optional[str] = None  # "excellent", "good", "fair", "poor"
    castability: Optional[str] = None  # "excellent", "good", "fair", "poor"

    # CNC machining
    cutting_speed: Optional[float] = None  # m/min (recommended)
    cutting_speed_unit: str = "m/min"
    feed_rate: Optional[float] = None  # mm/rev
    feed_rate_unit: str = "mm/rev"
    tool_material: Optional[str] = None  # "HSS", "carbide", "ceramic", "diamond"

    # 3D printing
    printable_fdm: Optional[bool] = None  # FDM/FFF
    printable_sla: Optional[bool] = None  # SLA/DLP
    printable_sls: Optional[bool] = None  # SLS
    printable_binder_jet: Optional[bool] = None  # Binder jetting
    print_nozzle_temp: Optional[float] = None  # °C (FDM)
    print_nozzle_temp_unit: str = "degC"
    print_bed_temp: Optional[float] = None  # °C (FDM)
    print_bed_temp_unit: str = "degC"
    print_chamber_temp: Optional[float] = None  # °C (for high-temp)
    print_chamber_temp_unit: str = "degC"
    print_support_removal: Optional[str] = None  # "easy", "moderate", "difficult"

    # Other processes
    anodizable: Optional[bool] = None
    polishable: Optional[bool] = None
    solderable: Optional[bool] = None

    # Quantity properties for unit-aware access
    @property
    def cutting_speed_qty(self) -> Optional[Quantity]:
        """Get cutting speed as Pint Quantity."""
        if self.cutting_speed is None:
            return None
        return self.cutting_speed * ureg(self.cutting_speed_unit)

    @property
    def feed_rate_qty(self) -> Optional[Quantity]:
        """Get feed rate as Pint Quantity."""
        if self.feed_rate is None:
            return None
        return self.feed_rate * ureg(self.feed_rate_unit)

    @property
    def print_nozzle_temp_qty(self) -> Optional[Quantity]:
        """Get print nozzle temperature as Pint Quantity."""
        if self.print_nozzle_temp is None:
            return None
        return self.print_nozzle_temp * ureg(self.print_nozzle_temp_unit)

    @property
    def print_bed_temp_qty(self) -> Optional[Quantity]:
        """Get print bed temperature as Pint Quantity."""
        if self.print_bed_temp is None:
            return None
        return self.print_bed_temp * ureg(self.print_bed_temp_unit)

    @property
    def print_chamber_temp_qty(self) -> Optional[Quantity]:
        """Get print chamber temperature as Pint Quantity."""
        if self.print_chamber_temp is None:
            return None
        return self.print_chamber_temp * ureg(self.print_chamber_temp_unit)


@dataclass
class ComplianceProperties:
    """Regulatory compliance and material suitability."""

    rohs_compliant: Optional[bool] = None
    reach_compliant: Optional[bool] = None
    halogen_free: Optional[bool] = None
    lead_free: Optional[bool] = None

    # Application suitability
    food_safe: Optional[bool] = None
    biocompatible: Optional[bool] = None
    uv_resistant: Optional[bool] = None
    radiation_resistant: Optional[bool] = None  # gamma, neutron, etc.
    flame_retardant: Optional[bool] = None

    # Recyclability
    recyclable: Optional[bool] = None
    recycling_symbol: Optional[int] = None  # 1-7 for plastics


@dataclass
class SourcingProperties:
    """Cost and availability information."""

    cost_per_kg: Optional[float] = None  # USD/kg (approximate, volatile)
    cost_per_kg_unit: str = "USD/kg"
    availability: Optional[str] = None  # "stock", "common", "specialty", "rare"
    lead_time_weeks: Optional[float] = None  # weeks
    lead_time_weeks_unit: str = "week"
    suppliers: list = field(default_factory=list)  # list of supplier names

    # Quantity properties for unit-aware access
    @property
    def cost_per_kg_qty(self) -> Optional[Quantity]:
        """Get cost per kg as Pint Quantity."""
        if self.cost_per_kg is None:
            return None
        return self.cost_per_kg * ureg(self.cost_per_kg_unit)

    @property
    def lead_time_weeks_qty(self) -> Optional[Quantity]:
        """Get lead time as Pint Quantity."""
        if self.lead_time_weeks is None:
            return None
        return self.lead_time_weeks * ureg(self.lead_time_weeks_unit)


@dataclass
class AllProperties:
    """Container for all material properties."""

    mechanical: MechanicalProperties = field(default_factory=MechanicalProperties)
    thermal: ThermalProperties = field(default_factory=ThermalProperties)
    electrical: ElectricalProperties = field(default_factory=ElectricalProperties)
    optical: OpticalProperties = field(default_factory=OpticalProperties)
    pbr: PBRProperties = field(default_factory=PBRProperties)
    manufacturing: ManufacturingProperties = field(default_factory=ManufacturingProperties)
    compliance: ComplianceProperties = field(default_factory=ComplianceProperties)
    sourcing: SourcingProperties = field(default_factory=SourcingProperties)

    # Extra user properties
    custom: Dict[str, Any] = field(default_factory=dict)
