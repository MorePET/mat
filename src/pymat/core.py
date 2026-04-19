"""
Core Material class with hierarchy, chaining, and properties.

Supports:
- Hierarchical inheritance (parents -> children)
- Chainable syntax: stainless.s316L.electropolished.apply_to(part)
- Direct access: s316L.apply_to(part) (auto-registered if no collision)
- Property inheritance (children inherit parent properties unless overridden)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Optional, TypeVar

if TYPE_CHECKING:
    from .pbr import PbrSource

from .properties import AllProperties

# Type variable for generic object application
T = TypeVar("T")


def _make_material(
    name: str,
    *,
    density: Optional[float] = None,
    formula: Optional[str] = None,
    composition: Optional[Dict[str, float]] = None,
    color: Optional[tuple] = None,
    grade: Optional[str] = None,
    temper: Optional[str] = None,
    treatment: Optional[str] = None,
    vendor: Optional[str] = None,
    mechanical: Optional[Dict[str, Any]] = None,
    thermal: Optional[Dict[str, Any]] = None,
    electrical: Optional[Dict[str, Any]] = None,
    optical: Optional[Dict[str, Any]] = None,
    pbr: Optional[Dict[str, Any]] = None,
    manufacturing: Optional[Dict[str, Any]] = None,
    compliance: Optional[Dict[str, Any]] = None,
    sourcing: Optional[Dict[str, Any]] = None,
    properties: Optional[AllProperties] = None,
    parent: Optional["Material"] = None,
    _key: Optional[str] = None,
) -> "Material":
    """Factory function to create Material with density convenience param."""
    # Create the internal material object
    mat = _MaterialInternal(
        name=name,
        formula=formula,
        composition=composition,
        color=color,
        grade=grade,
        temper=temper,
        treatment=treatment,
        vendor=vendor,
        mechanical=mechanical,
        thermal=thermal,
        electrical=electrical,
        optical=optical,
        pbr=pbr,
        manufacturing=manufacturing,
        compliance=compliance,
        sourcing=sourcing,
        properties=properties or AllProperties(),
        parent=parent,
        _key=_key,
    )

    # Apply density convenience param
    if density is not None:
        mat.properties.mechanical.density = density

    return mat


@dataclass
class _MaterialInternal:
    """
    Internal Material implementation. Use Material() constructor.

    A hierarchical, chainable material node.

    Properties cascade down the chain - children inherit from parents
    but can override any property at any level.
    """

    # Identity
    name: str
    formula: Optional[str] = None  # Chemical formula (e.g., "Al2O3")
    composition: Optional[Dict[str, float]] = None  # element -> fraction

    # Convenience parameters (backward compatibility)
    color: Optional[tuple] = None  # RGB or RGBA for visualization

    # Hierarchy metadata
    grade: Optional[str] = None  # e.g., "304", "6061"
    temper: Optional[str] = None  # e.g., "T6", "annealed"
    treatment: Optional[str] = None  # e.g., "passivated", "anodized"
    vendor: Optional[str] = None  # e.g., "saint_gobain", "hamamatsu"

    # Property groups as kwargs
    mechanical: Optional[Dict[str, Any]] = None
    thermal: Optional[Dict[str, Any]] = None
    electrical: Optional[Dict[str, Any]] = None
    optical: Optional[Dict[str, Any]] = None  # Physics properties, NOT visualization
    pbr: Optional[Dict[str, Any]] = None  # Visualization properties, NOT physics
    manufacturing: Optional[Dict[str, Any]] = None
    compliance: Optional[Dict[str, Any]] = None
    sourcing: Optional[Dict[str, Any]] = None

    # Properties (all domains)
    properties: AllProperties = field(default_factory=AllProperties)

    # Optional rich PBR backend. When set, takes precedence over
    # `properties.pbr` (the lite native dataclass) for rendering. See
    # ADR-0002 — this is the integration point for
    # `threejs_materials.PbrProperties` and any other external PBR
    # loader that conforms to the `pymat.pbr.PbrSource` Protocol.
    pbr_source: Optional["PbrSource"] = field(default=None, repr=False)

    # Hierarchy (not shown in repr)
    parent: Optional[_MaterialInternal] = field(default=None, repr=False)
    _children: Dict[str, _MaterialInternal] = field(default_factory=dict, repr=False)
    _key: Optional[str] = field(default=None, repr=False)  # for registry

    def __post_init__(self):
        """Apply convenience parameters and property groups to properties object."""
        # Apply color if provided
        if self.color is not None:
            if len(self.color) == 3:
                # RGB provided, add full opacity
                self.properties.pbr.base_color = (*self.color, 1.0)
            elif len(self.color) == 4:
                # RGBA provided
                self.properties.pbr.base_color = self.color
            else:
                raise ValueError(
                    f"color must be RGB (3 values) or RGBA (4 values), got {len(self.color)}"
                )

        # Apply property groups
        if self.mechanical:
            for key, value in self.mechanical.items():
                if hasattr(self.properties.mechanical, key):
                    setattr(self.properties.mechanical, key, value)

        if self.thermal:
            for key, value in self.thermal.items():
                if hasattr(self.properties.thermal, key):
                    setattr(self.properties.thermal, key, value)

        if self.electrical:
            for key, value in self.electrical.items():
                if hasattr(self.properties.electrical, key):
                    setattr(self.properties.electrical, key, value)

        if self.optical:
            for key, value in self.optical.items():
                if hasattr(self.properties.optical, key):
                    setattr(self.properties.optical, key, value)

        if self.pbr:
            for key, value in self.pbr.items():
                if hasattr(self.properties.pbr, key):
                    setattr(self.properties.pbr, key, value)

        if self.manufacturing:
            for key, value in self.manufacturing.items():
                if hasattr(self.properties.manufacturing, key):
                    setattr(self.properties.manufacturing, key, value)

        if self.compliance:
            for key, value in self.compliance.items():
                if hasattr(self.properties.compliance, key):
                    setattr(self.properties.compliance, key, value)

        if self.sourcing:
            for key, value in self.sourcing.items():
                if hasattr(self.properties.sourcing, key):
                    setattr(self.properties.sourcing, key, value)

        # Apply PBR defaults from optical properties (DRY principle)
        # Allow physics properties to drive rendering defaults, but preserve explicit overrides

        # If ior wasn't explicitly set (still at default 1.5) and optical.refractive_index exists,
        # use optical.refractive_index as the PBR ior
        if self.properties.pbr.ior == 1.5 and self.properties.optical.refractive_index is not None:
            self.properties.pbr.ior = self.properties.optical.refractive_index

        # If transmission wasn't explicitly set (still at default 0.0) and
        # optical.transparency exists, convert transparency (0-100%) to
        # transmission (0-1)
        if (
            self.properties.pbr.transmission == 0.0
            and self.properties.optical.transparency is not None
        ):
            self.properties.pbr.transmission = self.properties.optical.transparency / 100.0

        # When a rich pbr_source is provided, project its fields down
        # onto the lite `properties.pbr` dataclass. This lets existing
        # ocp_vscode / downstream renderers that only read
        # `material.properties.pbr.<field>` pick up the rich data
        # without any changes on their side (graceful enhancement).
        # `to_three_js_material_dict()` still prefers the full rich
        # source for callers that can handle it.
        if self.pbr_source is not None:
            self._backfill_pbr_from_source()

    def _backfill_pbr_from_source(self) -> None:
        """
        Populate the lite `properties.pbr` dataclass from the rich
        `pbr_source`'s `to_dict()` output.

        Supports two `to_dict()` shapes, detected at runtime:

        - **Nested** (`threejs_materials.PbrProperties` format):
          ``{id, name, source, url, license, values: {...}, textures: {...}}``
          — scalars under ``values``, maps under ``textures``.
        - **Flat** (`pymat`'s own lite `PBRProperties.to_dict()` format):
          ``{color, metalness, roughness, normalMap, ...}`` — Three.js
          MeshPhysicalMaterial camelCase keys at the top level.

        The lite dataclass is a strict subset of the Three.js
        MeshPhysicalMaterial spec — fields on the rich source that
        don't have a corresponding lite field (sheen, anisotropy,
        iridescence, dispersion, etc.) are dropped. Downstream
        consumers that need full fidelity should read
        `material.pbr_source` directly.
        """
        if self.pbr_source is None:
            return
        try:
            d = self.pbr_source.to_dict()
        except Exception:
            return

        # Detect shape: nested has `values` key, flat has top-level scalars.
        if isinstance(d.get("values"), dict):
            values = d["values"]
            maps = d.get("textures") if isinstance(d.get("textures"), dict) else {}
        else:
            values = d
            maps = {}

        lite = self.properties.pbr

        # Scalars
        color = values.get("color")
        if isinstance(color, (list, tuple)) and len(color) >= 3:
            r, g, b = color[:3]
            alpha = values.get(
                "opacity",
                lite.base_color[3] if len(lite.base_color) >= 4 else 1.0,
            )
            lite.base_color = (r, g, b, alpha)
        if "metalness" in values:
            lite.metallic = values["metalness"]
        if "roughness" in values:
            lite.roughness = values["roughness"]
        emissive = values.get("emissive")
        if isinstance(emissive, (list, tuple)):
            lite.emissive = tuple(emissive)
        if "ior" in values:
            lite.ior = values["ior"]
        if "transmission" in values:
            lite.transmission = values["transmission"]
        if "clearcoat" in values:
            lite.clearcoat = values["clearcoat"]

        # Texture maps. Nested (`textures`) keys are short names like
        # `color`, `normal`, `roughness`, `metalness`, `ao`. Flat
        # format uses Three.js camelCase: `map` (the color channel),
        # `normalMap`, `roughnessMap`, `metalnessMap`, `aoMap`.
        lite.base_color_map = maps.get("color") or values.get("map") or lite.base_color_map
        lite.normal_map = maps.get("normal") or values.get("normalMap") or lite.normal_map
        lite.roughness_map = (
            maps.get("roughness") or values.get("roughnessMap") or lite.roughness_map
        )
        lite.metallic_map = maps.get("metalness") or values.get("metalnessMap") or lite.metallic_map
        lite.ambient_occlusion_map = (
            maps.get("ao") or values.get("aoMap") or lite.ambient_occlusion_map
        )

    # =========================================================================
    # Chaining API
    # =========================================================================

    def __getattr__(self, name: str) -> _MaterialInternal:
        """
        Access child variants by attribute.

        Usage:
            stainless.s316L -> accesses s316L grade
            s316L.electropolished -> accesses treatment

        Note: This is only called when normal attribute lookup fails.
        """
        # For private/protected attributes that don't exist, raise immediately
        if name.startswith("_"):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

        # For public attributes, try to find in children
        try:
            children = object.__getattribute__(self, "_children")
            if name in children:
                return children[name]
        except AttributeError:
            pass

        # Not found in children either
        try:
            children = object.__getattribute__(self, "_children")
            available = list(children.keys())
        except AttributeError:
            available = []

        raise AttributeError(
            f"'{self.name}' has no variant '{name}'. "
            f"Available: {available if available else 'none'}"
        )

    def _add_child(self, key: str, **overrides) -> _MaterialInternal:
        """
        Internal: add a child node with inherited properties.

        Child inherits all properties from parent unless explicitly overridden.
        """
        # Inherit property objects (deep copy to avoid mutation)
        from copy import deepcopy

        inherited_props = deepcopy(self.properties)

        # Handle property group overrides (mechanical, thermal, etc.)
        # These are dicts that should be applied to the inherited properties
        property_groups = [
            ("mechanical", inherited_props.mechanical),
            ("thermal", inherited_props.thermal),
            ("electrical", inherited_props.electrical),
            ("optical", inherited_props.optical),
            ("pbr", inherited_props.pbr),
            ("manufacturing", inherited_props.manufacturing),
            ("compliance", inherited_props.compliance),
            ("sourcing", inherited_props.sourcing),
        ]

        for group_name, prop_obj in property_groups:
            if group_name in overrides:
                group_dict = overrides.pop(group_name)
                if isinstance(group_dict, dict):
                    for k, v in group_dict.items():
                        if v is not None and hasattr(prop_obj, k):
                            setattr(prop_obj, k, v)

        # Build child properties
        child_props = {
            "name": overrides.get("name", f"{self.name} {key}"),
            "formula": overrides.get("formula", self.formula),
            "composition": overrides.get("composition", self.composition),
            "properties": inherited_props,
            "parent": self,
            "_key": key,
        }

        # Carry forward metadata unless overridden
        for meta in ("grade", "temper", "treatment", "vendor"):
            child_props[meta] = overrides.get(meta, getattr(self, meta))

        # Remove used overrides
        for k in list(overrides.keys()):
            if k in ("name", "formula", "composition", "grade", "temper", "treatment", "vendor"):
                overrides.pop(k)

        # Store any remaining overrides in custom properties
        if overrides:
            child_props["properties"].custom.update(overrides)

        child = Material(**child_props)
        self._children[key] = child
        return child

    # =========================================================================
    # Chainable Methods
    # =========================================================================

    def grade_(self, key: str, **props) -> _MaterialInternal:
        """Add a grade variant (e.g., 304, 316L, 6061, a7075)."""
        return self._add_child(key, grade=key, **props)

    def temper_(self, key: str, **props) -> _MaterialInternal:
        """Add a temper/heat treatment (e.g., T6, O, annealed)."""
        return self._add_child(key, temper=key, **props)

    def treatment_(self, key: str, **props) -> _MaterialInternal:
        """Add a surface treatment (e.g., passivated, anodized, electropolished)."""
        return self._add_child(key, treatment=key, **props)

    def vendor_(self, key: str, **props) -> _MaterialInternal:
        """Add a vendor-specific variant."""
        return self._add_child(key, vendor=key, **props)

    def variant_(self, key: str, **props) -> _MaterialInternal:
        """Add a generic variant (dopant, alloy composition, etc.)."""
        return self._add_child(key, **props)

    # =========================================================================
    # Application to Shapes
    # =========================================================================

    def apply_to(self, obj):
        """
        Apply this material to an object.

        For build123d Shapes: sets material, color, and calculates mass
        For other objects: sets obj.material = self

        Args:
            obj: Object to apply material to (build123d Shape or any object)

        Returns:
            The modified object

        Raises:
            TypeError: If obj doesn't support attribute assignment

        Example:
            # build123d Shape - full features
            crystal = Box(10, 10, 10)
            lyso.apply_to(crystal)  # Sets: material, color, mass

            # Custom object - just material attribute
            class MyPart:
                pass
            part = MyPart()
            stainless.apply_to(part)  # Sets: part.material = stainless
        """
        # Check if object supports attribute assignment
        try:
            obj.material = self
        except (AttributeError, TypeError) as e:
            raise TypeError(
                f"Cannot apply material to {type(obj).__name__}: "
                f"object doesn't support attribute assignment ({e})"
            )

        # Try build123d-specific features (color, mass calculation)
        # Check for build123d Shape characteristics: has volume and color attributes
        try:
            if hasattr(obj, "volume") and hasattr(obj, "color"):
                # Set color from PBR with alpha derived from transmission
                # Alpha = 1 - transmission (transmission=1 → fully transparent, alpha=0)
                color = self.properties.pbr.base_color
                transmission = self.properties.pbr.transmission
                alpha = 1.0 - transmission
                obj.color = (*color[:3], alpha)

                # Calculate mass if density is available
                if self.properties.mechanical.density and self.properties.mechanical.density > 0:
                    # build123d volume is in mm³, density is g/cm³
                    # 1 cm³ = 1000 mm³, so g/mm³ = g/cm³ / 1000
                    density_g_mm3 = self.properties.mechanical.density / 1000
                    obj.mass = obj.volume * density_g_mm3

        except (AttributeError, TypeError):
            # If build123d-specific features fail, that's fine
            # The material attribute is already set, which is the minimum requirement
            pass

        return obj

    # =========================================================================
    # Information & Inspection
    # =========================================================================

    @property
    def path(self) -> str:
        """Full hierarchical path from root (e.g., 'aluminum.a7075.T6')."""
        parts = []
        node = self
        while node:
            part_key = node._key or node.name.lower().replace(" ", "_")
            parts.append(part_key)
            node = node.parent
        return ".".join(reversed(parts))

    @property
    def density(self) -> Optional[float]:
        """Density in g/cm³ (convenience property for mechanical.density)."""
        return self.properties.mechanical.density

    @density.setter
    def density(self, value: Optional[float]) -> None:
        """Set density in g/cm³."""
        self.properties.mechanical.density = value

    @property
    def density_g_mm3(self) -> float:
        """Density in g/mm³ (for build123d calculations)."""
        mech_density = self.properties.mechanical.density
        if not mech_density:
            return 0.0
        return mech_density / 1000

    @property
    def molar_mass(self) -> Optional[float]:
        """
        Molar mass in g/mol, parsed from `formula`.

        Only meaningful for materials with a well-defined chemical
        formula (compounds, pure elements). Returns `None` for
        alloys/mixtures without a formula, and for formulas containing
        element symbols not in the local atomic-weight table. Derived
        on every access — not stored, not authored in TOML. See
        ADR-0001.

        Note: this intentionally does not use `composition` because
        alloys store composition as mass fractions, not atom counts,
        and a single "molar mass" isn't well-defined for mixtures.
        """
        if not self.formula:
            return None
        from .elements import compute_molar_mass

        try:
            return compute_molar_mass(self.formula)
        except ValueError:
            return None

    @property
    def molar_mass_qty(self):
        """Molar mass as a Pint Quantity in g/mol, or None."""
        mass = self.molar_mass
        if mass is None:
            return None
        from .units import ureg

        return mass * ureg("g/mol")

    def mass_from_volume_mm3(self, volume_mm3: float) -> float:
        """Calculate mass in grams from volume in mm³."""
        return volume_mm3 * self.density_g_mm3

    def to_three_js_material_dict(self) -> dict:
        """
        Return a Three.js ``MeshPhysicalMaterial`` dict for this material.

        Uses `pbr_source` if set (rich backend such as
        `threejs_materials.PbrProperties` with full MaterialX
        support), otherwise falls back to `properties.pbr` (the
        lite native in-tree backend). See ADR-0002.
        """
        if self.pbr_source is not None:
            return self.pbr_source.to_dict()
        return self.properties.pbr.to_dict()

    def __repr__(self) -> str:
        """String representation showing path and density."""
        density_str = f"ρ={self.density} g/cm³" if self.density else "ρ=?"
        return f"Material({self.path!r}, {density_str})"

    def __str__(self) -> str:
        """Human-readable string."""
        return f"{self.name} ({self.path})"

    def info(self) -> str:
        """Detailed information about this material."""
        lines = [
            f"Material: {self.name}",
            f"Path: {self.path}",
            "",
            "Mechanical Properties:",
            f"  Density: {self.density} g/cm³" if self.density else "  Density: N/A",
            f"  Young's Modulus: {self.properties.mechanical.youngs_modulus} GPa"
            if self.properties.mechanical.youngs_modulus
            else "",
            f"  Yield Strength: {self.properties.mechanical.yield_strength} MPa"
            if self.properties.mechanical.yield_strength
            else "",
        ]

        if self.formula:
            lines.append(f"Formula: {self.formula}")
        if self.composition:
            lines.append(f"Composition: {self.composition}")

        return "\n".join(line for line in lines if line)


# Create the public Material class as an alias that accepts density param
class Material(_MaterialInternal):
    """
    A hierarchical, chainable material node.

    Properties cascade down the chain - children inherit from parents
    but can override any property at any level.

    Constructor parameters:
    - name: Material name (required)
    - density: Density in g/cm³ (convenience parameter, sets mechanical.density)
    - color: Visualization color - RGB tuple (r, g, b) or RGBA (r, g, b, alpha)
    - formula: Chemical formula (e.g., "Al2O3")
    - composition: Element fractions dict
    - mechanical: Dict of mechanical properties (density, youngs_modulus, etc.)
    - thermal: Dict of thermal properties (melting_point, conductivity, etc.)
    - electrical: Dict of electrical properties (resistivity, dielectric_constant, etc.)
    - optical: Dict of optical properties (refractive_index, transparency, etc.) - PHYSICS
    - pbr: Dict of PBR visualization properties (base_color, metallic, roughness) - RENDERING
    - pbr_source: Optional rich PBR backend conforming to `pymat.pbr.PbrSource`
      (typically `threejs_materials.PbrProperties` via the `[pbr]` extra).
      Takes precedence over `pbr` for `to_three_js_material_dict()`.
    - manufacturing: Dict of manufacturing properties (machinability, weldability, etc.)
    - compliance: Dict of compliance properties (rohs_compliant, food_safe, etc.)
    - sourcing: Dict of sourcing properties (cost_per_kg, availability, etc.)

    Example usage:
        Material(name="Steel", density=7.8, color=(0.7, 0.7, 0.7))
        Material(name="Steel", mechanical={"density": 7.8, "youngs_modulus": 200})
        Material(name="LYSO", optical={"transparency": 92, "refractive_index": 1.82})
    """

    def __init__(
        self,
        name: str,
        *,
        density: Optional[float] = None,
        formula: Optional[str] = None,
        composition: Optional[Dict[str, float]] = None,
        color: Optional[tuple] = None,
        grade: Optional[str] = None,
        temper: Optional[str] = None,
        treatment: Optional[str] = None,
        vendor: Optional[str] = None,
        mechanical: Optional[Dict[str, Any]] = None,
        thermal: Optional[Dict[str, Any]] = None,
        electrical: Optional[Dict[str, Any]] = None,
        optical: Optional[Dict[str, Any]] = None,
        pbr: Optional[Dict[str, Any]] = None,
        pbr_source: Optional["PbrSource"] = None,
        manufacturing: Optional[Dict[str, Any]] = None,
        compliance: Optional[Dict[str, Any]] = None,
        sourcing: Optional[Dict[str, Any]] = None,
        properties: Optional[AllProperties] = None,
        parent: Optional["Material"] = None,
        _key: Optional[str] = None,
    ):
        # Call parent init without density
        super().__init__(
            name=name,
            formula=formula,
            composition=composition,
            color=color,
            grade=grade,
            temper=temper,
            treatment=treatment,
            vendor=vendor,
            mechanical=mechanical,
            thermal=thermal,
            electrical=electrical,
            optical=optical,
            pbr=pbr,
            pbr_source=pbr_source,
            manufacturing=manufacturing,
            compliance=compliance,
            sourcing=sourcing,
            properties=properties or AllProperties(),
            parent=parent,
            _key=_key,
        )

        # Apply density convenience param after parent init
        if density is not None:
            self.properties.mechanical.density = density
