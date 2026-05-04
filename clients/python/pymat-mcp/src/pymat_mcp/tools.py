"""Pure-Python tool functions backing the MCP server.

Each function takes plain types (str, int, list, dict) and returns
plain types. ``server.py`` wraps them in ``@mcp.tool()`` decorators;
that's the only place the MCP runtime touches the code. Keeping the
runtime separate means tests can call these directly without
spinning up a server.

Errors: every tool catches and translates py-materials exceptions
into ``{"error": "<human-readable>"}`` dicts rather than raising.
The MCP protocol surfaces structured errors through tool responses
better than via Python tracebacks, and an agent gets a usable
"material not found" hint either way.
"""

from __future__ import annotations

from typing import Any

# ── Helpers ────────────────────────────────────────────────────────


_ALL_DOMAINS = (
    "mechanical",
    "thermal",
    "electrical",
    "optical",
    "manufacturing",
    "compliance",
    "sourcing",
)


def _props_dict(props: Any, domains: list[str] | None = None) -> dict[str, dict[str, Any]]:
    """Flatten ``Material.properties`` into a JSON-serializable dict.

    ``AllProperties`` is a dataclass-of-dataclasses; reach in and
    expose only the fields with non-None values. Keeps payloads
    compact when most properties are unset (the common case).

    ``domains`` filters which top-level groups appear. Default = all.
    Unknown domain names are silently dropped (matches the kwargs
    forgiveness elsewhere; agent typos shouldn't surface as errors
    when the rest of the payload is still useful).
    """
    out: dict[str, dict[str, Any]] = {}
    selected = tuple(domains) if domains else _ALL_DOMAINS
    for group_name in selected:
        if group_name not in _ALL_DOMAINS:
            continue
        group = getattr(props, group_name, None)
        if group is None:
            continue
        group_out: dict[str, Any] = {}
        for field_name in dir(group):
            if field_name.startswith("_"):
                continue
            # Skip ``*_qty`` Pint-Quantity accessors — they're convenience
            # views over the bare-number fields below them and don't
            # JSON-serialize. The bare ``density`` etc. are already in
            # the dump with the units documented separately by py-mat.
            if field_name.endswith("_qty"):
                continue
            value = getattr(group, field_name, None)
            if value is None or callable(value):
                continue
            # Defensive: any remaining Pint Quantity (e.g. user-set
            # custom field) renders to its magnitude.
            if hasattr(value, "magnitude"):
                value = value.magnitude
            group_out[field_name] = value
        if group_out:
            out[group_name] = group_out
    return out


def _vis_dict(vis: Any) -> dict[str, Any]:
    """Compact dict view of a ``Vis`` instance — identity + scalars +
    finishes. Excludes the texture cache (which is bytes and not useful
    in an agent-facing response)."""
    out: dict[str, Any] = {
        "source": vis.source,
        "material_id": vis.material_id,
        "tier": vis.tier,
        "finish": vis.finish,
        "finishes": dict(vis.finishes) if vis.finishes else {},
    }
    for scalar_field in (
        "roughness",
        "metallic",
        "base_color",
        "ior",
        "transmission",
        "clearcoat",
        "emissive",
    ):
        v = getattr(vis, scalar_field, None)
        if v is not None:
            out[scalar_field] = v
    return out


def _brief(material: Any) -> dict[str, Any]:
    """Minimal summary of a material for search-result rows."""
    return {
        "key": material._key,
        "name": material.name,
        "grade": material.grade,
        "category": _category_of(material),
        "density": material.properties.mechanical.density,
    }


def _category_of(material: Any) -> str | None:
    """Walk up the parent chain to find the top-level category."""
    cur = material
    while cur is not None and cur.parent is not None:
        cur = cur.parent
    return cur.name if cur is not None else None


def _resolve(key_or_name: str) -> Any:
    """Look up a material via the public subscript interface; return
    None on miss (caller wraps in error envelope)."""
    import pymat

    try:
        return pymat[key_or_name]
    except KeyError:
        return None


def _not_found(key_or_name: str) -> dict[str, Any]:
    """Standard error envelope for "no material matched" — used by
    every tool that resolves a single material. ``did_you_mean``
    returns ``[{key, name}]`` pairs (not just names) so the agent can
    retry with the canonical key without a second round-trip.
    """
    import pymat

    suggestions = []
    for s in pymat.search(key_or_name)[:5]:
        suggestions.append({"key": s._key, "name": s.name})
    return {
        "error": f"No material matched {key_or_name!r}",
        "did_you_mean": suggestions,
    }


# ── Tools ──────────────────────────────────────────────────────────


def search_materials(query: str, limit: int = 10) -> dict[str, Any]:
    """Fuzzy-search the curated material library.

    Returns a list of brief summary rows (key, name, grade, category,
    density). Use ``get_material`` for the full property dump on a
    chosen result.
    """
    import pymat

    hits = pymat.search(query)
    return {"query": query, "results": [_brief(m) for m in hits[:limit]]}


def get_material(
    material: str,
    domains: list[str] | None = None,
    include_vis: bool = True,
) -> dict[str, Any]:
    """Return the curated property dump for a material.

    Resolution: registry key OR ``Material.name`` OR ``grade``
    (case-insensitive, NFKC-normalized).

    Args:
        material: Key / name / grade. ``"s304"``, ``"Stainless Steel
            304"``, ``"304"`` all resolve to the same material.
        domains: Property domains to include. Subset of
            ``["mechanical", "thermal", "electrical", "optical",
            "manufacturing", "compliance", "sourcing"]``. Defaults to
            all — pass a narrower list (e.g. ``["mechanical",
            "thermal"]``) to halve typical payload size for prompts
            that don't need compliance / sourcing metadata.
        include_vis: Include the ``vis`` block (PBR + finishes).
            Default ``True``; set ``False`` to skip when only chemistry
            / mechanical properties are needed.

    On miss returns ``{"error": "...", "did_you_mean": [{key, name},
    ...]}``; never raises.
    """
    m = _resolve(material)
    if m is None:
        return _not_found(material)
    out: dict[str, Any] = {
        "key": m._key,
        "name": m.name,
        "grade": m.grade,
        "temper": m.temper,
        "treatment": m.treatment,
        "category": _category_of(m),
        "formula": m.formula,
        "molar_mass": m.molar_mass,
        "properties": _props_dict(m.properties, domains=domains),
    }
    if include_vis:
        out["vis"] = _vis_dict(m.vis)
    return out


def list_categories() -> dict[str, Any]:
    """Top-level material categories shipped in py-materials.

    These are the parent nodes (aluminum, stainless, lyso, …) — every
    other material descends from one of these via ``parent``. Useful
    as a discovery starting point.

    Implementation note: ``pymat`` lazy-loads category groups on first
    attribute access. ``_CATEGORY_BASES`` maps group-names (``metals``,
    ``scintillators``, …) to lists of *base material names*
    (``aluminum``, ``stainless``, …). Group-names are NOT valid
    pymat attributes; the base names are. We trigger the loader by
    touching one base name per group, which loads the entire group
    (and registers all parents under it).
    """
    import pymat

    for group, bases in pymat._CATEGORY_BASES.items():
        if not bases:
            continue
        try:
            # Touching the first base name in each group fires the
            # lazy loader for the whole group. ``pymat.aluminum``
            # → loads metals; ``pymat.lyso`` → loads scintillators.
            getattr(pymat, bases[0])
        except Exception:
            # Optional categories that fail to load shouldn't poison
            # the result; skip them.
            continue

    cats = sorted(
        key for key in pymat.registry.list_all() if pymat.registry.get(key).parent is None
    )
    return {"categories": cats}


def list_grades(material: str) -> dict[str, Any]:
    """Children (grades / tempers / treatments) of a parent material.

    A child node carries its parent's properties unless overridden.
    For ``stainless`` you get s303, s304, s316L, …; for ``s316L`` you
    might get further variants (passivated, electropolished, …).
    """
    m = _resolve(material)
    if m is None:
        return _not_found(material)
    children = [_brief(child) for child in m._children.values()]
    return {"parent": _brief(m), "children": children}


def list_finishes(material: str) -> dict[str, Any]:
    """Available finishes (brushed / polished / matte / …) for a
    material's appearance.

    Each finish maps to a different mat-vis ``(source, material_id)``
    pair — switching finishes flips the texture set without changing
    the engineering material. Returns a list of ``{name, source,
    material_id}`` rows + the currently-selected default.
    """
    m = _resolve(material)
    if m is None:
        return _not_found(material)
    finishes = [
        {"name": name, "source": entry["source"], "material_id": entry["id"]}
        for name, entry in m.vis.finishes.items()
    ]
    return {
        "material": m.name,
        "default_finish": m.vis.finish,
        "finishes": finishes,
    }


def compute_mass(material: str, volume_mm3: float) -> dict[str, Any]:
    """Compute mass in grams for a given volume using curated density.

    ``volume_mm3`` is in cubic millimeters (matches build123d
    ``shape.volume`` units). Returns mass in grams + the density used.
    """
    m = _resolve(material)
    if m is None:
        return _not_found(material)
    density = m.properties.mechanical.density
    if density is None:
        return {
            "error": f"{m.name!r} has no curated density (mechanical.density is None)",
            "material": m.name,
        }
    # density is g/cm³ → g/mm³ via /1000
    mass_g = volume_mm3 * (density / 1000.0)
    return {
        "material": m.name,
        "volume_mm3": volume_mm3,
        "density_g_per_cm3": density,
        "mass_g": mass_g,
    }


def get_appearance(material: str) -> dict[str, Any]:
    """Visual / PBR identity for a material — ``Vis`` payload as dict.

    Includes mat-vis ``(source, material_id, tier)``, available
    finishes, current finish, PBR scalars (roughness, metallic,
    base_color, …). For renderer-ready output use ``to_threejs`` /
    ``to_gltf``.
    """
    m = _resolve(material)
    if m is None:
        return _not_found(material)
    return {"material": m.name, "vis": _vis_dict(m.vis)}


# Texture-data heuristic: strings longer than this are treated as
# embedded image bytes (base64 or data URIs) and replaced with handles.
# 1 KiB is well above any realistic non-data string in either adapter
# output (color hex codes, factor names, etc. are <100 chars) and well
# below any meaningful PNG (smallest known mat-vis channels are several
# KiB).
_TEXTURE_BYTE_THRESHOLD = 1024


def _strip_texture_bytes(value: Any, *, vis_handle: dict[str, Any]) -> Any:
    """Recursively replace embedded texture data with light handles.

    The upstream ``pymat.vis.to_threejs`` / ``to_gltf`` adapters embed
    textures as base64 strings or ``data:image/png;base64,...`` URIs.
    A single material's threejs dict can be 4+ MB — unusable across
    the MCP transport.

    We replace any string longer than ``_TEXTURE_BYTE_THRESHOLD`` with
    a handle ``{"_texture": True, "bytes": <int>, ...vis_handle}``
    that an agent can use to (a) know textures exist, and (b) fetch
    them out-of-band via the mat-vis HTTP substrate (per-file URLs
    since mat-vis 0.6.0).

    ``vis_handle`` is the ``(source, material_id, tier)`` triple of
    the resolved material — copied into every handle so the agent
    has everything needed to construct a fetch URL without a second
    tool call.
    """
    if isinstance(value, str) and len(value) >= _TEXTURE_BYTE_THRESHOLD:
        return {"_texture": True, "bytes": len(value), **vis_handle}
    if isinstance(value, dict):
        return {k: _strip_texture_bytes(v, vis_handle=vis_handle) for k, v in value.items()}
    if isinstance(value, list):
        return [_strip_texture_bytes(v, vis_handle=vis_handle) for v in value]
    return value


def to_threejs(material: str, finish: str | None = None) -> dict[str, Any]:
    """Three.js ``MeshPhysicalMaterial`` init dict (textures stripped).

    Texture-map fields (``map``, ``normalMap``, ``roughnessMap``,
    ``metalnessMap``, ``displacementMap``) are replaced with light
    handles ``{"_texture": True, "bytes": ..., "source": ...,
    "material_id": ..., "tier": ..., "channel": ...}`` — agents fetch
    the actual image bytes out-of-band via mat-vis URLs. Without this
    a single material response is multiple MB.

    If ``finish`` is given, derives a polished/brushed/etc. variant
    via ``Vis.override`` + ``Material.with_vis`` (registry singleton
    is not mutated).
    """
    from pymat.vis import to_threejs as _to_threejs

    m = _resolve(material)
    if m is None:
        return _not_found(material)
    target = m.with_vis(m.vis.override(finish=finish)) if finish else m
    raw = _to_threejs(target)
    handle = {
        "source": target.vis.source,
        "material_id": target.vis.material_id,
        "tier": target.vis.tier,
    }
    return {
        "material": target.name,
        "threejs": _strip_texture_bytes(raw, vis_handle=handle),
        "_handle": handle,
    }


def to_gltf(material: str, finish: str | None = None) -> dict[str, Any]:
    """glTF 2.0 material node dict (textures stripped).

    Same handle-replacement semantics as :func:`to_threejs` —
    embedded ``data:image/png;base64,…`` URIs are swapped for fetch
    handles. PBR factors (``metallicFactor``, ``baseColorFactor``,
    etc.) pass through unchanged.

    Args:
        material: Material key or name.
        finish: Optional finish name from the material's finishes map.
            Derives a variant via ``Vis.override`` + ``Material.with_vis``;
            the registry singleton is NOT mutated.
    """
    from pymat.vis import to_gltf as _to_gltf

    m = _resolve(material)
    if m is None:
        return _not_found(material)
    target = m.with_vis(m.vis.override(finish=finish)) if finish else m
    raw = _to_gltf(target)
    handle = {
        "source": target.vis.source,
        "material_id": target.vis.material_id,
        "tier": target.vis.tier,
    }
    return {
        "material": target.name,
        "gltf": _strip_texture_bytes(raw, vis_handle=handle),
        "_handle": handle,
    }


def compare_materials(
    materials: list[str],
    properties: list[str] | None = None,
) -> dict[str, Any]:
    """Side-by-side comparison of N materials across selected properties.

    Args:
        materials: List of material keys or names.
        properties: Dotted paths like ``"mechanical.density"`` or
            ``"thermal.melting_point"``. Default: density,
            youngs_modulus, yield_strength, melting_point,
            thermal_conductivity.

    Per-row errors (material not found) appear inline as
    ``{"key": "...", "error": "not found"}`` — comparison continues
    for the rest, so an agent gets partial results rather than a
    whole-table failure.
    """
    if not properties:
        properties = [
            "mechanical.density",
            "mechanical.youngs_modulus",
            "mechanical.yield_strength",
            "thermal.melting_point",
            "thermal.thermal_conductivity",
        ]

    rows: list[dict[str, Any]] = []
    for key in materials:
        m = _resolve(key)
        if m is None:
            rows.append({"key": key, "error": "not found"})
            continue
        row: dict[str, Any] = {"key": m._key, "name": m.name, "grade": m.grade}
        for path in properties:
            head, tail = path.split(".", 1)
            group = getattr(m.properties, head, None)
            row[path] = getattr(group, tail, None) if group is not None else None
        rows.append(row)

    return {"properties": properties, "rows": rows}
