"""
Output adapters — thin wrappers that map Material to mat-vis's
generic adapter functions.

The actual format logic (Three.js field names, glTF schema,
MaterialX XML) lives in mat_vis_client.adapters (installed from
mat-vis-client package). These wrappers extract scalars + textures
from a ``Material`` (or a standalone ``Vis``) and pass them through.

    from pymat.vis.adapters import to_threejs, to_gltf, export_mtlx
    result = to_threejs(material)          # Material form
    result = to_threejs(material.vis)      # Vis form — same output

The polymorphism lets ``Vis.to_gltf()`` / ``Vis.to_threejs()`` method
sugar delegate here without a back-reference from ``Vis`` to its
owning ``Material``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Union

from mat_vis_client.adapters import export_mtlx as _export_mtlx
from mat_vis_client.adapters import to_gltf as _to_gltf
from mat_vis_client.adapters import to_threejs as _to_threejs

if TYPE_CHECKING:
    from pymat.core import _MaterialInternal as Material
    from pymat.vis._model import Vis

    MaterialOrVis = Union[Material, Vis]


def _rgba_to_hex(rgba: list[float] | tuple[float, ...] | None) -> str | None:
    """Convert [r, g, b, a?] in 0-1 range to '#RRGGBB'. Alpha dropped."""
    if rgba is None:
        return None
    r, g, b = (int(round(max(0.0, min(1.0, c)) * 255)) for c in rgba[:3])
    return f"#{r:02x}{g:02x}{b:02x}"


def _resolve_vis_and_name(obj: MaterialOrVis) -> tuple[Vis, str]:
    """Unwrap a Material (``→ .vis, .name``) or a standalone Vis
    (``→ self, ""``). Duck-typed via the ``.vis`` attribute: anything
    that exposes ``.vis`` is treated as the owning Material."""
    if hasattr(obj, "vis"):
        return obj.vis, getattr(obj, "name", "") or ""
    return obj, ""  # assume it's a Vis


def _extract_scalars(obj: MaterialOrVis) -> dict[str, Any]:
    """Extract PBR scalars from material.vis (or a plain Vis).

    Maps py-mat "metallic" → mat-vis "metalness" and our RGBA
    base_color list → mat-vis's color_hex string (its adapters
    only know how to emit color from the hex form).
    """
    vis, _ = _resolve_vis_and_name(obj)
    return {
        "metalness": vis.get("metallic"),
        "roughness": vis.get("roughness"),
        "color_hex": _rgba_to_hex(vis.get("base_color")),
        "ior": vis.get("ior"),
        "transmission": vis.get("transmission"),
        "clearcoat": vis.get("clearcoat"),
        "emissive": vis.get("emissive"),
    }


def _extract_textures(obj: MaterialOrVis) -> dict[str, bytes]:
    """Extract texture bytes from a Material's Vis (or a plain Vis)."""
    vis, _ = _resolve_vis_and_name(obj)
    if not vis.has_mapping:
        return {}
    return vis.textures


def to_threejs(obj: MaterialOrVis) -> dict[str, Any]:
    """Format as a Three.js MeshPhysicalMaterial-compatible dict.

    Accepts either a ``Material`` or a standalone ``Vis``. Reads PBR
    scalars and texture maps from ``obj.vis`` (or from ``obj`` itself
    if it's a Vis). Delegates to mat-vis's generic adapter.
    """
    return _to_threejs(_extract_scalars(obj), _extract_textures(obj))


def to_gltf(obj: MaterialOrVis, *, name: str | None = None) -> dict[str, Any]:
    """Format as a glTF pbrMetallicRoughness material dict.

    Accepts either a ``Material`` (its ``.name`` is used as the glTF
    material ``name`` field) or a standalone ``Vis`` (pass ``name=``
    explicitly to populate the field; empty string otherwise).
    Delegates to mat-vis's generic adapter.
    """
    _, resolved_name = _resolve_vis_and_name(obj)
    result = _to_gltf(_extract_scalars(obj), _extract_textures(obj))
    result["name"] = name if name is not None else resolved_name
    return result


def export_mtlx(
    obj: MaterialOrVis,
    output_dir: Path,
    *,
    name: str | None = None,
) -> Path:
    """Export as a MaterialX .mtlx file + PNG textures on disk.

    Accepts either a ``Material`` (its ``.name`` becomes the filename
    stem) or a standalone ``Vis`` (pass ``name=`` explicitly to name
    the output). Delegates to mat-vis's generic adapter.
    """
    _, resolved_name = _resolve_vis_and_name(obj)
    mat_name = name if name is not None else resolved_name
    safe_name = mat_name.replace(" ", "_").replace("/", "_") or "material"
    return _export_mtlx(
        _extract_scalars(obj),
        _extract_textures(obj),
        output_dir,
        material_name=safe_name,
    )
