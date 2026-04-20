"""
pymat - Hierarchical material library for CAD applications.

Features:
- Chainable hierarchy: stainless.s316L.electropolished.apply_to(part)
- Direct access: s316L.apply_to(part) (auto-registered if no collision)
- Property inheritance: children inherit parent properties
- Lazy loading: categories load on first access
- periodictable integration: auto-fill density from formula
- Visual PBR via Material.vis: roughness, metallic, textures, finishes
- Unit-aware properties with Pint for dimensional analysis

Usage:
    from pymat import stainless, aluminum, lyso, s304, T6, ureg

    # Chainable
    housing = stainless.s316L.electropolished.apply_to(Box(50, 50, 10))

    # Direct access
    crystal = lyso.apply_to(Box(10, 10, 30))
    bracket = s304.apply_to(Box(30, 20, 5))

    # Check properties
    print(housing.material.vis.roughness)
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
from . import factories, registry, vis
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
    SourcingProperties,
    ThermalProperties,
)
from .search import search
from .units import ureg

__version__ = "4.0.0"  # x-release-please-version
__all__ = [
    "Material",
    "AllProperties",
    "MechanicalProperties",
    "ThermalProperties",
    "ElectricalProperties",
    "OpticalProperties",
    "ManufacturingProperties",
    "ComplianceProperties",
    "SourcingProperties",
    "ureg",
    "load_toml",
    "load_category",
    "search",
    "enrich_from_periodictable",
    "enrich_from_matproj",
    "enrich_all",
    "factories",
    "vis",
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
    "ceramics": ["alumina", "zirconia", "sic", "macor", "shapal", "glass", "beryllia", "yttria"],
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


def _lookup(name_or_key: str) -> Material:
    """Exact-lookup implementation for ``pymat["..."]``.

    Resolves ``name_or_key`` against the registered material library via
    ``search(..., exact=True)``. Raises ``KeyError`` for empty queries,
    misses, and ambiguous matches — the candidate list is attached to
    the error message so the user can pick.

    Backing the subscript form (``pymat["Stainless Steel 304"]``) is the
    idiomatic Python-registry pattern (see ``os.environ``, ``sys.modules``,
    ``collections.ChainMap``) — raises on miss by convention, unlike
    ``dict.get`` which returns None.
    """
    if not isinstance(name_or_key, str):
        raise TypeError(f"pymat[...] takes a string key or name, got {type(name_or_key).__name__}")
    if not name_or_key.strip():
        raise KeyError("pymat[...] requires a non-empty material name or key; got empty/whitespace")

    hits = search(name_or_key, exact=True, limit=50)
    if not hits:
        # Offer the closest fuzzy matches so the user can see what was
        # close — far more useful than a bare KeyError.
        fuzzy = search(name_or_key, limit=5)
        if fuzzy:
            suggestions = ", ".join(repr(m.name) for m in fuzzy)
            raise KeyError(
                f"No material matches {name_or_key!r} exactly. "
                f"Close matches: {suggestions}. "
                f"Use pymat.search({name_or_key!r}) for the full fuzzy list."
            )
        raise KeyError(f"No material matches {name_or_key!r}")
    if len(hits) > 1:
        names = ", ".join(repr(m.name) for m in hits[:8])
        raise KeyError(
            f"Ambiguous: {len(hits)} materials match {name_or_key!r} "
            f"(key, name, or grade). Candidates: {names}"
            f"{' …' if len(hits) > 8 else ''}. "
            f"Use a more specific query or index by key."
        )
    return hits[0]


# Install module-level __getitem__ so ``pymat["Stainless Steel 304"]`` works.
# PEP 562 covers module-level __getattr__ but not __getitem__; the standard
# pattern is to swap the module's __class__ for a subtype of ModuleType that
# defines __getitem__. Python's import machinery is unaffected.
import sys as _sys  # noqa: E402 — must run after _lookup / Material definitions
import types as _types  # noqa: E402 — same reason


class _PymatModule(_types.ModuleType):
    def __getitem__(self, key: str) -> Material:  # type: ignore[override]
        return _lookup(key)

    def __contains__(self, key: str) -> bool:  # type: ignore[override]
        try:
            _lookup(key)
        except KeyError:
            return False
        return True


_sys.modules[__name__].__class__ = _PymatModule


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
