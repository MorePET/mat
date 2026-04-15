"""
pymat - Hierarchical material library for CAD applications.

Features:
- Chainable hierarchy: stainless.s316L.electropolished.apply_to(part)
- Direct access: s316L.apply_to(part) (auto-registered if no collision)
- Property inheritance: children inherit parent properties
- Lazy loading: categories load on first access
- periodictable integration: auto-fill density from formula
- PBR support: rendering properties for glTF/3MF export
- Unit-aware properties with Pint for dimensional analysis

Usage:
    from pymat import stainless, aluminum, lyso, s304, T6, ureg

    # Chainable
    housing = stainless.s316L.electropolished.apply_to(Box(50, 50, 10))

    # Direct access
    crystal = lyso.apply_to(Box(10, 10, 30))
    bracket = s304.apply_to(Box(30, 20, 5))

    # Check properties
    print(housing.material.properties.pbr.roughness)
    print(crystal.material.properties.optical.light_yield)

    # Unit-aware calculations
    density_qty = stainless.s304.properties.mechanical.density_qty
    density_kg_m3 = density_qty.to('kg/m^3')

    # Temperature-dependent properties
    k_at_100c = stainless.properties.thermal.thermal_conductivity_at(100 * ureg.degC)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from .core import Material

# Exports
from . import factories, registry
from .core import Material
from .enrichers import enrich_all, enrich_from_matproj, enrich_from_periodictable
from .loader import load_category, load_toml
from .properties import (
    AllProperties,
    ComplianceProperties,
    ElectricalProperties,
    ManufacturingProperties,
    MechanicalProperties,
    OpticalProperties,
    PBRProperties,
    SourcingProperties,
    ThermalProperties,
)
from .units import ureg

__version__ = "2.1.0"
__all__ = [
    "Material",
    "AllProperties",
    "MechanicalProperties",
    "ThermalProperties",
    "ElectricalProperties",
    "OpticalProperties",
    "PBRProperties",
    "ManufacturingProperties",
    "ComplianceProperties",
    "SourcingProperties",
    "ureg",
    "load_toml",
    "load_category",
    "enrich_from_periodictable",
    "enrich_from_matproj",
    "enrich_all",
    "factories",
]

# ============================================================================
# Lazy Loading State
# ============================================================================

_LOADED_CATEGORIES: set[str] = set()


# Category to base materials mapping
_CATEGORY_BASES: Dict[str, list[str]] = {
    "metals": ["stainless", "aluminum", "copper", "tungsten", "lead", "titanium", "brass"],
    "scintillators": ["lyso", "bgo", "nai", "csi", "labr3", "pwo", "plastic_scint"],
    "plastics": [
        "peek",
        "delrin",
        "ultem",
        "ptfe",
        "esr",
        "nylon",
        "pla",
        "abs",
        "petg",
        "tpu",
        "vespel",
        "torlon",
        "pctfe",
        "pmma",
        "pe",
        "pc",
    ],
    "ceramics": ["alumina", "macor", "zirconia", "glass"],
    "electronics": ["fr4", "rogers", "kapton", "copper_pcb", "solder"],
    "liquids": ["water", "heavy_water", "mineral_oil", "glycerol", "silicone_oil"],
    "gases": [
        "air",
        "nitrogen",
        "oxygen",
        "argon",
        "co2",
        "helium",
        "hydrogen",
        "neon",
        "xenon",
        "methane",
        "vacuum",
    ],
}


def _ensure_loaded(category: str) -> None:
    """Load a material category if not already loaded."""
    if category not in _LOADED_CATEGORIES:
        try:
            load_category(category)
            _LOADED_CATEGORIES.add(category)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Material category '{category}' not found. "
                f"Available categories: {list(_CATEGORY_BASES.keys())}"
            )


def _ensure_material_loaded(name: str) -> None:
    """Ensure a specific material is loaded by finding its category."""
    # Check if already in registry
    if registry.get(name):
        return

    # Try each category
    for category, bases in _CATEGORY_BASES.items():
        if name in bases or name.lower() in [b.lower() for b in bases]:
            _ensure_loaded(category)
            if registry.get(name):
                return

    # If still not found, raise error with helpful message
    all_bases = []
    for bases in _CATEGORY_BASES.values():
        all_bases.extend(bases)
    raise AttributeError(f"Material '{name}' not found. Available materials: {all_bases}")


def __getattr__(name: str) -> Material:
    """
    Lazy-load materials on first access.

    Usage:
        from pymat import stainless  # triggers lazy load of metals.toml
        from pymat import lyso       # triggers lazy load of scintillators.toml
    """
    if name.startswith("_"):
        raise AttributeError(f"module 'pymat' has no attribute '{name}'")

    # Try to find and load the material
    _ensure_material_loaded(name)

    # Retrieve from registry
    material = registry.get(name)
    if material:
        return material

    raise AttributeError(f"module 'pymat' has no attribute '{name}'")


def __dir__() -> list[str]:
    """
    Help IDE discover available materials.

    Returns list of all registered materials plus standard exports.
    """
    base_exports = [
        "Material",
        "AllProperties",
        "MechanicalProperties",
        "ThermalProperties",
        "ElectricalProperties",
        "OpticalProperties",
        "PBRProperties",
        "ManufacturingProperties",
        "ComplianceProperties",
        "SourcingProperties",
        "load_toml",
        "load_category",
        "enrich_from_periodictable",
        "enrich_from_matproj",
        "enrich_all",
    ]

    # Add all known base materials
    known_materials = []
    for bases in _CATEGORY_BASES.values():
        known_materials.extend(bases)

    return base_exports + known_materials


def load_all() -> Dict[str, Material]:
    """
    Load all material categories.

    Useful if you want everything available at startup.

    Returns:
        Dictionary of {name -> Material} for all registered materials
    """
    for category in _CATEGORY_BASES.keys():
        _ensure_loaded(category)

    return registry.list_all()
