"""
Output adapters — thin wrappers that map Material to mat-vis's
generic adapter functions.

The actual format logic (Three.js field names, glTF schema,
MaterialX XML) lives in mat_vis_client.adapters (installed from
mat-vis-client package). These wrappers extract scalars + textures
from a Material and pass them through.

    from pymat.vis.adapters import to_threejs, to_gltf, export_mtlx
    result = to_threejs(material)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from mat_vis_client.adapters import export_mtlx as _export_mtlx
from mat_vis_client.adapters import to_gltf as _to_gltf
from mat_vis_client.adapters import to_threejs as _to_threejs

if TYPE_CHECKING:
    from pymat.core import _MaterialInternal as Material


def _rgba_to_hex(rgba: list[float] | tuple[float, ...] | None) -> str | None:
    """Convert [r, g, b, a?] in 0-1 range to '#RRGGBB'. Alpha dropped."""
    if rgba is None:
        return None
    r, g, b = (int(round(max(0.0, min(1.0, c)) * 255)) for c in rgba[:3])
    return f"#{r:02x}{g:02x}{b:02x}"


def _extract_scalars(material: Material) -> dict[str, Any]:
    """Extract PBR scalars from material.vis with defaults.

    Maps py-mat "metallic" → mat-vis "metalness" and our RGBA
    base_color list → mat-vis's color_hex string (its adapters
    only know how to emit color from the hex form).
    """
    vis = material.vis
    return {
        "metalness": vis.get("metallic"),
        "roughness": vis.get("roughness"),
        "color_hex": _rgba_to_hex(vis.get("base_color")),
        "ior": vis.get("ior"),
        "transmission": vis.get("transmission"),
        "clearcoat": vis.get("clearcoat"),
        "emissive": vis.get("emissive"),
    }


def _extract_textures(material: Material) -> dict[str, bytes]:
    """Extract texture bytes from Material.vis."""
    if not material.vis.has_mapping:
        return {}
    return material.vis.textures


def to_threejs(material: Material) -> dict[str, Any]:
    """Format as a Three.js MeshPhysicalMaterial-compatible dict.

    Reads PBR scalars and texture maps from material.vis.
    Delegates to mat-vis's generic adapter.
    """
    return _to_threejs(_extract_scalars(material), _extract_textures(material))


def to_gltf(material: Material) -> dict[str, Any]:
    """Format as a glTF pbrMetallicRoughness material dict.

    Delegates to mat-vis's generic adapter.
    """
    result = _to_gltf(_extract_scalars(material), _extract_textures(material))
    result["name"] = material.name
    return result


def export_mtlx(material: Material, output_dir: Path) -> Path:
    """Export as a MaterialX .mtlx file + PNG textures on disk.

    Delegates to mat-vis's generic adapter.
    """
    safe_name = material.name.replace(" ", "_").replace("/", "_")
    return _export_mtlx(
        _extract_scalars(material),
        _extract_textures(material),
        output_dir,
        material_name=safe_name,
    )
