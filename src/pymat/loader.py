"""
TOML loader with inheritance resolution.

Parses hierarchical TOML files and builds Material trees with property inheritance.
Children inherit all properties from parents unless explicitly overridden.

Supports both legacy single-value format and new unit-aware (value, unit) format.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

if TYPE_CHECKING:
    from .core import Material

from . import registry
from .core import Material
from .properties import (
    AllProperties,
)
from .units import STANDARD_UNITS

logger = logging.getLogger(__name__)


def _build_properties_from_dict(
    data: Dict[str, Any], parent_props: Optional[AllProperties] = None
) -> AllProperties:
    """
    Build AllProperties from a dictionary, inheriting from parent if provided.

    Supports both legacy format (single values) and new unit-aware format (*_value, *_unit pairs).

    Args:
        data: Dictionary with property keys
        parent_props: Parent AllProperties to inherit from (optional)

    Returns:
        Fully populated AllProperties

    Legacy format (backward compatible):
        thermal.melting_point = 1450  -> auto-assigns degC unit

    New unit-aware format:
        thermal.melting_point_value = 1450
        thermal.melting_point_unit = "degC"
    """
    from copy import deepcopy

    # Start with parent properties or empty
    props = deepcopy(parent_props) if parent_props else AllProperties()

    # Helper to safely get and update nested properties
    def update_properties(prop_obj, prop_dict, prop_name):
        """Update property object from dictionary, handling both legacy and new formats."""
        for key, value in prop_dict.items():
            if value is None:
                continue

            # Skip processed value/unit pairs
            if key.endswith("_unit"):
                continue

            # Check if this is a value in a value/unit pair
            if key.endswith("_value"):
                base_key = key[:-6]  # Remove "_value" suffix
                unit_key = f"{base_key}_unit"

                # Get the unit from the dictionary
                unit = prop_dict.get(unit_key)
                if unit is None:
                    # No unit specified, try to assign default
                    full_key = f"{prop_name}.{base_key}"
                    default_unit = STANDARD_UNITS.get(base_key)
                    if default_unit:
                        unit = default_unit
                        logger.warning(
                            f"No unit specified for {full_key}, auto-assigning {default_unit}"
                        )
                    else:
                        logger.warning(f"Could not determine unit for {full_key}")
                        unit = None

                # Set both value and unit
                if hasattr(prop_obj, base_key):
                    setattr(prop_obj, base_key, value)
                if unit and hasattr(prop_obj, unit_key):
                    setattr(prop_obj, unit_key, unit)

            # Legacy format: single value (not a value/unit pair)
            elif not key.endswith("_unit"):
                if hasattr(prop_obj, key):
                    setattr(prop_obj, key, value)
                    # Try to set default unit
                    unit_key = f"{key}_unit"
                    if hasattr(prop_obj, unit_key):
                        default_unit = STANDARD_UNITS.get(key)
                        if default_unit:
                            setattr(prop_obj, unit_key, default_unit)
                            logger.warning(
                                "No unit specified for %s.%s, auto-assigning %s",
                                prop_name,
                                key,
                                default_unit,
                            )

    # Parse each property group
    if "mechanical" in data:
        update_properties(props.mechanical, data["mechanical"], "mechanical")
    if "thermal" in data:
        update_properties(props.thermal, data["thermal"], "thermal")
    if "electrical" in data:
        update_properties(props.electrical, data["electrical"], "electrical")
    if "optical" in data:
        update_properties(props.optical, data["optical"], "optical")
    if "pbr" in data:
        pbr_data = data["pbr"]
        # Special handling for tuples
        if "base_color" in pbr_data:
            pbr_data["base_color"] = tuple(pbr_data["base_color"])
        if "emissive" in pbr_data:
            pbr_data["emissive"] = tuple(pbr_data["emissive"])
        update_properties(props.pbr, pbr_data, "pbr")
    if "manufacturing" in data:
        update_properties(props.manufacturing, data["manufacturing"], "manufacturing")
    if "compliance" in data:
        update_properties(props.compliance, data["compliance"], "compliance")
    if "sourcing" in data:
        update_properties(props.sourcing, data["sourcing"], "sourcing")

    # Custom properties
    if "custom" in data:
        props.custom.update(data["custom"])

    return props


def _resolve_material_node(
    key: str,
    data: Dict[str, Any],
    parent_material: Optional[Material] = None,
    parent_props: Optional[AllProperties] = None,
) -> Material:
    """
    Recursively build a Material node from TOML data.

    Args:
        key: Material key (e.g., "s304")
        data: Dictionary with material data
        parent_material: Parent Material (for hierarchy)
        parent_props: Parent properties (for inheritance)

    Returns:
        Material instance
    """
    # Extract material-level attributes
    name = data.get("name", key)
    formula = data.get("formula")
    composition = data.get("composition")
    grade = data.get("grade")
    temper = data.get("temper")
    treatment = data.get("treatment")
    vendor = data.get("vendor")

    # Build properties from all property groups
    properties = _build_properties_from_dict(
        {
            k: v
            for k, v in data.items()
            if k
            in (
                "mechanical",
                "thermal",
                "electrical",
                "optical",
                "pbr",
                "manufacturing",
                "compliance",
                "sourcing",
                "custom",
            )
        },
        parent_props,
    )

    # Create material
    material = Material(
        name=name,
        formula=formula,
        composition=composition,
        grade=grade or parent_material.grade if parent_material else None,
        temper=temper or parent_material.temper if parent_material else None,
        treatment=treatment or parent_material.treatment if parent_material else None,
        vendor=vendor or parent_material.vendor if parent_material else None,
        properties=properties,
        parent=parent_material,
        _key=key,
    )

    # Register for direct access
    registry.register(key, material)

    # Process children (nested dictionaries that represent child materials)
    for child_key, child_data in data.items():
        if isinstance(child_data, dict) and not child_key.startswith("_"):
            # Skip property group keys
            if child_key not in (
                "mechanical",
                "thermal",
                "electrical",
                "optical",
                "pbr",
                "manufacturing",
                "compliance",
                "sourcing",
                "custom",
                "name",
                "formula",
                "composition",
                "grade",
                "temper",
                "treatment",
                "vendor",
            ):
                child_material = _resolve_material_node(
                    child_key,
                    child_data,
                    parent_material=material,
                    parent_props=properties,
                )
                material._children[child_key] = child_material

    return material


def load_toml(file_path: Path | str) -> Dict[str, Material]:
    """
    Load materials from a TOML file.

    Args:
        file_path: Path to TOML file

    Returns:
        Dictionary of {key -> Material} for top-level materials

    Example TOML:
        [stainless]
        name = "Stainless Steel"
        [stainless.mechanical]
        density = 8.0

        [stainless.s304]
        grade = "304"
        [stainless.s304.mechanical]
        yield_strength = 170
    """
    file_path = Path(file_path)
    with open(file_path, "rb") as f:
        data = tomllib.load(f)

    materials = {}
    for key, mat_data in data.items():
        if isinstance(mat_data, dict) and not key.startswith("_"):
            material = _resolve_material_node(key, mat_data)
            materials[key] = material

    return materials


def load_category(category_name: str) -> Dict[str, Material]:
    """
    Load a material category from data/ directory.

    Args:
        category_name: Category name (e.g., "metals", "scintillators")

    Returns:
        Dictionary of {key -> Material}
    """
    data_dir = Path(__file__).parent / "data"
    file_path = data_dir / f"{category_name}.toml"

    if not file_path.exists():
        raise FileNotFoundError(f"Material category not found: {file_path}")

    return load_toml(file_path)
