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
    pass

from .properties import AllProperties
from .sources import Source, resolve_path

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
    vis: Optional[Dict[str, Any]] = None,
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
        manufacturing=manufacturing,
        compliance=compliance,
        sourcing=sourcing,
        properties=properties or AllProperties(),
        parent=parent,
        _key=_key,
    )

    # vis={} kwarg — apply after internal init so we write through the
    # public .vis accessor (which sets _vis lazily). Identity keys are
    # batched through set_identity so construction never exposes a
    # half-assigned (source-but-no-material_id) state.
    if vis:
        _IDENTITY_KEYS = {"source", "material_id", "tier"}
        identity_kwargs = {k: vis[k] for k in _IDENTITY_KEYS if k in vis}
        if identity_kwargs:
            mat.vis.set_identity(**identity_kwargs)
        for key, value in vis.items():
            if key in _IDENTITY_KEYS:
                continue
            setattr(mat.vis, key, value)

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
    manufacturing: Optional[Dict[str, Any]] = None
    compliance: Optional[Dict[str, Any]] = None
    sourcing: Optional[Dict[str, Any]] = None

    # Properties (all domains)
    properties: AllProperties = field(default_factory=AllProperties)

    # Visual representation (mat-vis textures, lazy-fetched)
    _vis: Optional[Any] = field(default=None, repr=False)

    # Hierarchy (not shown in repr)
    parent: Optional[_MaterialInternal] = field(default=None, repr=False)
    _children: Dict[str, _MaterialInternal] = field(default_factory=dict, repr=False)
    _key: Optional[str] = field(default=None, repr=False)  # for registry

    # Provenance (#150) — keyed by dotted property path; `_default` fallback.
    _sources: Dict[str, Source] = field(default_factory=dict, repr=False)

    def __post_init__(self):
        """Apply convenience parameters and property groups to properties object."""
        # Apply color → vis.base_color (3.0: vis is the canonical home)
        if self.color is not None:
            if len(self.color) == 3:
                self.vis.base_color = (*self.color, 1.0)
            elif len(self.color) == 4:
                self.vis.base_color = self.color
            else:
                raise ValueError(
                    f"color must be RGB (3 values) or RGBA (4 values), got {len(self.color)}"
                )

        # Apply property groups (non-PBR)
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

        # Optical → vis derivations — vis is the single source of truth in 3.0
        if self.vis.ior is None and self.properties.optical.refractive_index is not None:
            self.vis.ior = self.properties.optical.refractive_index

        if self.vis.transmission is None and self.properties.optical.transparency is not None:
            self.vis.transmission = self.properties.optical.transparency / 100.0

    # =========================================================================
    # Visual representation (mat-vis)
    # =========================================================================

    @property
    def vis(self):
        """Visual representation — identity, PBR scalars, textures, finishes.

        Always returns a Vis instance (never None). Starts with
        ``source=None`` for materials without mat-vis data. Populated
        from TOML ``[vis]`` section for registered materials.

        Usage::

            steel.vis.source              # "ambientcg"
            steel.vis.material_id         # "Metal012"
            steel.vis.textures["color"]   # PNG bytes (lazy-fetched)
            steel.vis.finishes            # {"brushed": {"source": ..., "id": ...}}
            steel.vis.finish = "polished" # switch appearance
            steel.vis.mtlx.xml()          # MaterialX document (method since mat-vis-client 0.5)

        See ADR-0002 and ``pymat.vis._model.Vis`` for the full surface.
        External renderers consume via ``pymat.vis.to_threejs(material)``.
        """
        if self._vis is None:
            from pymat.vis._model import Vis

            self._vis = Vis()
        return self._vis

    @vis.setter
    def vis(self, value):
        self._vis = value

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
                # Set color from vis scalars with alpha from transmission.
                # Fall back to the grey default when vis.base_color is None
                # (child nodes that haven't had a color set).
                color = self.vis.base_color or (0.8, 0.8, 0.8, 1.0)
                transmission = self.vis.transmission or 0.0
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

    def copy(self) -> "Material":
        """Return a detached copy of this Material.

        Materials reached via ``pymat["..."]`` or category imports
        (``from pymat import stainless``) are *shared instances* — the
        same object every caller in the process sees. Mutating
        ``m.properties.mechanical.density``, reassigning ``m.vis``, or
        flipping ``m.vis.finish`` on those leaks into every other
        consumer. ``copy`` returns an independent instance — same name
        / grade / properties / vis — that can be tweaked freely.

        Materials *you* construct (``Material(name="custom", ...)``)
        are not shared and need no copy. The hazard only applies to
        registry instances.

        Detached:

        - ``_vis`` deep-copied AND its texture cache zeroed (deepcopy
          bypasses ``Vis.__post_init__``, so the cache is cleared
          explicitly here)
        - ``properties`` deep-copied
        - all property-group kwarg dicts (mechanical, thermal, …) deep-copied

        Preserved by reference (intentionally — these are part of the
        registry hierarchy, not per-instance state):

        - ``parent`` (the registry parent the copy still belongs under).
          Note: mutating ``c.parent.<anything>`` still affects the
          registry. Don't.
        - ``_children`` dict — empty for the copy (a detached node has
          no children of its own; it's a leaf variant). For parent-level
          materials this means ``stainless.copy().s304`` raises.
        - ``_key`` cleared so it can't be confused with the registry entry

        For just changing appearance, prefer
        :meth:`with_vis` + :meth:`Vis.override` — single-shot and clearer.
        """
        from copy import deepcopy

        new = type(self)(name=self.name)
        # Identity / hierarchy metadata
        new.formula = self.formula
        new.composition = deepcopy(self.composition)
        new.color = self.color
        new.grade = self.grade
        new.temper = self.temper
        new.treatment = self.treatment
        new.vendor = self.vendor
        # Property-group kwarg dicts — preserve so re-init is consistent
        new.mechanical = deepcopy(self.mechanical)
        new.thermal = deepcopy(self.thermal)
        new.electrical = deepcopy(self.electrical)
        new.optical = deepcopy(self.optical)
        new.manufacturing = deepcopy(self.manufacturing)
        new.compliance = deepcopy(self.compliance)
        new.sourcing = deepcopy(self.sourcing)
        # Independent properties + vis. ``deepcopy`` bypasses
        # ``Vis.__post_init__`` (it goes through ``__reduce_ex__``), so
        # the texture cache must be zeroed explicitly. Otherwise the copy
        # carries duplicated texture bytes (waste, not a leak — the deep
        # copy is independent of the parent — but the docstring promises
        # a clean cache so we deliver it).
        new.properties = deepcopy(self.properties)
        if self._vis is not None:
            new_vis = deepcopy(self._vis)
            # ``deepcopy`` bypasses ``Vis.__post_init__`` (it goes through
            # ``__reduce_ex__``), so the texture cache must be zeroed
            # explicitly. ``object.__setattr__`` skips the identity-
            # invalidation hook in ``Vis.__setattr__`` (which is fine here
            # — we're not changing identity, just resetting cache).
            object.__setattr__(new_vis, "_textures", {})
            object.__setattr__(new_vis, "_fetched", False)
            new._vis = new_vis
        else:
            new._vis = None
        # Registry decoupling
        new.parent = self.parent  # stays registry-aware for fallback chain
        new._children = {}
        new._key = None
        return new

    def with_vis(self, vis: "Vis") -> "Material":  # noqa: F821 — forward ref
        """Return a detached copy with the given Vis attached.

        The canonical safe path for "I want this material with a tweaked
        appearance" — pairs cleanly with :meth:`Vis.override`::

            steel = pymat["Stainless Steel 304"]
            shiny = steel.with_vis(steel.vis.override(roughness=0.05, finish="polished"))
            pymat.vis.to_threejs(shiny)
            # steel is the registry singleton; shiny is independent.

        Closes the parent-singleton hazard: ``m.vis = ...`` directly on
        a registry instance still mutates the shared object. ``with_vis``
        returns a fresh Material whose ``vis`` slot is the new value,
        leaving the registry untouched.

        The supplied ``vis`` is deep-copied so passing in a registry
        instance's own ``vis`` (e.g. ``m.with_vis(m.vis)``) does not
        re-alias the singleton. Always returns an independent Vis.
        """
        from copy import deepcopy

        from pymat.vis._model import Vis

        if not isinstance(vis, Vis):
            raise TypeError(f"with_vis expects a Vis instance, got {type(vis).__name__}")
        new = self.copy()
        # Deep-copy the supplied vis so callers passing the registry's
        # own ``m.vis`` don't re-alias the singleton. ``override`` already
        # returns an independent Vis, but we cannot rely on the caller
        # having gone through it.
        new._vis = deepcopy(vis)
        return new

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
        """Density in g/mm³ (for build123d calculations).

        Always returns a plain float — if the underlying density is a
        ufloat (#149), the nominal value is taken so build123d/JSON
        boundaries don't see a ufloat they can't handle.
        """
        mech_density = self.properties.mechanical.density
        if not mech_density:
            return 0.0
        nominal = float(getattr(mech_density, "nominal_value", mech_density))
        return nominal / 1000

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

    # =========================================================================
    # Provenance API (#150) — see ADR-0003 and src/pymat/sources.py
    # =========================================================================

    def source_of(self, path: str) -> Optional[Source]:
        """Return the `Source` for a property path, or `_default`, or None.

        Accepts short aliases (`"density"`) or fully-qualified paths
        (`"mechanical.density"`). Resolution order: exact path → `_default`
        → None.
        """
        if not self._sources:
            return None
        qpath = resolve_path(path)
        if qpath in self._sources:
            return self._sources[qpath]
        return self._sources.get("_default")

    def cite(self, path: Optional[str] = None) -> str:
        """Emit BibTeX. Without `path`: every source used by this material,
        deduplicated by citation key. With `path`: just that one source.

        Returns "" when nothing is cited (graceful, never raises)."""
        if not self._sources:
            return ""
        if path is not None:
            src = self.source_of(path)
            return src.to_bibtex() if src is not None else ""
        seen: Dict[str, Source] = {}
        for src in self._sources.values():
            seen.setdefault(src.citation, src)
        return "\n\n".join(s.to_bibtex() for s in seen.values())

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
    - vis: Dict of visualization scalars (base_color, metallic, roughness, ior, transmission)
    - manufacturing: Dict of manufacturing properties (machinability, weldability, etc.)
    - compliance: Dict of compliance properties (rohs_compliant, food_safe, etc.)
    - sourcing: Dict of sourcing properties (cost_per_kg, availability, etc.)

    Example usage:
        Material(name="Steel", density=7.8, color=(0.7, 0.7, 0.7))
        Material(name="Steel", mechanical={"density": 7.8, "youngs_modulus": 200})
        Material(name="LYSO", optical={"transparency": 92, "refractive_index": 1.82})
        Material(name="Polished Steel", vis={"metallic": 1.0, "roughness": 0.15})
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
        vis: Optional[Dict[str, Any]] = None,
        manufacturing: Optional[Dict[str, Any]] = None,
        compliance: Optional[Dict[str, Any]] = None,
        sourcing: Optional[Dict[str, Any]] = None,
        properties: Optional[AllProperties] = None,
        parent: Optional["Material"] = None,
        _key: Optional[str] = None,
        _sources: Optional[Dict[str, Source]] = None,
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
            manufacturing=manufacturing,
            compliance=compliance,
            sourcing=sourcing,
            properties=properties or AllProperties(),
            parent=parent,
            _key=_key,
            _sources=_sources or {},
        )

        # Apply density convenience param after parent init
        if density is not None:
            self.properties.mechanical.density = density

        # Apply vis={} kwarg — writes through the public .vis accessor.
        # Identity keys batch through set_identity (single invalidation,
        # no half-assigned intermediate state).
        if vis:
            _IDENTITY_KEYS = {"source", "material_id", "tier"}
            identity_kwargs = {k: vis[k] for k in _IDENTITY_KEYS if k in vis}
            if identity_kwargs:
                self.vis.set_identity(**identity_kwargs)
            for key, value in vis.items():
                if key in _IDENTITY_KEYS:
                    continue
                setattr(self.vis, key, value)
