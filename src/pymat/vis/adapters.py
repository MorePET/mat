"""
Output adapters — standalone functions that format Material data
for specific consumers.

Each adapter takes a Material and reads from both .properties.pbr
(scalars) and .vis (textures) to produce consumer-specific output.

    from pymat.vis.adapters import to_threejs, to_gltf, export_mtlx

    threejs_dict = to_threejs(material)
    gltf_dict = to_gltf(material)
    export_mtlx(material, Path("/tmp/steel/"))

Consumers can write their own adapters — no changes to pymat needed.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pymat.core import _MaterialInternal as Material


def to_threejs(material: Material) -> dict[str, Any]:
    """Format as a Three.js MeshPhysicalMaterial-compatible dict.

    Reads PBR scalars from material.properties.pbr and texture maps
    from material.vis. Textures are base64-encoded data URIs.

    See docs/specs/field-name-mapping.md for the naming translation.

    Returns:
        Dict usable as MeshPhysicalMaterial constructor args.
    """
    raise NotImplementedError("Adapter not yet implemented — see MorePET/mat#35")


def to_gltf(material: Material) -> dict[str, Any]:
    """Format as a glTF pbrMetallicRoughness material dict.

    Note: glTF packs metalness (B) and roughness (G) into a single
    metallicRoughnessTexture. This adapter composites the separate
    mat-vis channels if both textures exist.

    See docs/specs/field-name-mapping.md for the naming translation.

    Returns:
        Dict conforming to the glTF material spec.
    """
    raise NotImplementedError("Adapter not yet implemented — see MorePET/mat#35")


def export_mtlx(material: Material, output_dir: Path) -> Path:
    """Export as a MaterialX .mtlx file + PNG textures on disk.

    Writes:
        output_dir/
            <material_name>.mtlx   — MaterialX XML, texture refs as siblings
            <material_name>_color.png
            <material_name>_normal.png
            ...

    Args:
        material: Material with vis data.
        output_dir: Directory to write into (created if needed).

    Returns:
        Path to the written .mtlx file.
    """
    raise NotImplementedError("Adapter not yet implemented — see MorePET/mat#35")


def _to_data_uri(png_bytes: bytes) -> str:
    """Encode PNG bytes as a base64 data URI."""
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"
