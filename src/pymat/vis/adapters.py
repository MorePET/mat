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

Field name mapping (see docs/specs/field-name-mapping.md):
    py-mat metallic  → Three.js metalness  → glTF metallicFactor
    py-mat roughness → Three.js roughness  → glTF roughnessFactor
    py-mat base_color → Three.js color     → glTF baseColorFactor
    mat-vis "color"   → Three.js "map"     → glTF baseColorTexture
    mat-vis "normal"  → Three.js "normalMap" → glTF normalTexture
    mat-vis "roughness" → Three.js "roughnessMap"
    mat-vis "metalness" → Three.js "metalnessMap"
    mat-vis "ao"        → Three.js "aoMap"   → glTF occlusionTexture
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import TYPE_CHECKING, Any
from xml.etree.ElementTree import Element, SubElement, ElementTree, indent

if TYPE_CHECKING:
    from pymat.core import _MaterialInternal as Material


def _to_data_uri(png_bytes: bytes) -> str:
    """Encode PNG bytes as a base64 data URI."""
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _color_to_hex_int(rgba: tuple) -> int:
    """Convert RGBA float tuple to Three.js hex int (RGB only)."""
    r = int(min(max(rgba[0], 0.0), 1.0) * 255)
    g = int(min(max(rgba[1], 0.0), 1.0) * 255)
    b = int(min(max(rgba[2], 0.0), 1.0) * 255)
    return (r << 16) | (g << 8) | b


# Channel → Three.js texture property name
_THREEJS_TEX_MAP = {
    "color": "map",
    "normal": "normalMap",
    "roughness": "roughnessMap",
    "metalness": "metalnessMap",
    "ao": "aoMap",
    "displacement": "displacementMap",
    "emission": "emissiveMap",
}


def to_threejs(material: Material) -> dict[str, Any]:
    """Format as a Three.js MeshPhysicalMaterial-compatible dict.

    Reads PBR scalars from material.properties.pbr and texture maps
    from material.vis. Textures are base64-encoded data URIs.

    Returns:
        Dict usable as MeshPhysicalMaterial constructor args.
    """
    pbr = material.properties.pbr
    result: dict[str, Any] = {
        "type": "MeshPhysicalMaterial",
        "color": _color_to_hex_int(pbr.base_color),
        "metalness": pbr.metallic,
        "roughness": pbr.roughness,
    }

    if pbr.ior != 1.5:
        result["ior"] = pbr.ior
    if pbr.transmission > 0.0:
        result["transmission"] = pbr.transmission
    if pbr.clearcoat > 0.0:
        result["clearcoat"] = pbr.clearcoat
    if any(c > 0 for c in pbr.emissive):
        result["emissive"] = _color_to_hex_int((*pbr.emissive, 1.0))

    # Texture maps from vis (if available)
    textures = material.vis.textures if material.vis.source_id else {}
    for channel, threejs_prop in _THREEJS_TEX_MAP.items():
        if channel in textures:
            result[threejs_prop] = _to_data_uri(textures[channel])

    return result


# Channel → glTF texture property name
_GLTF_TEX_MAP = {
    "color": "baseColorTexture",
    "normal": "normalTexture",
    "ao": "occlusionTexture",
    "emission": "emissiveTexture",
}


def to_gltf(material: Material) -> dict[str, Any]:
    """Format as a glTF material dict.

    Note: glTF packs metalness (B) and roughness (G) into a single
    metallicRoughnessTexture. This adapter does NOT composite them —
    it sets scalar factors and separate textures. A full glTF exporter
    would need to pack the channels.

    Returns:
        Dict conforming to the glTF material spec.
    """
    pbr = material.properties.pbr
    pbr_mr: dict[str, Any] = {
        "baseColorFactor": list(pbr.base_color),
        "metallicFactor": pbr.metallic,
        "roughnessFactor": pbr.roughness,
    }

    textures = material.vis.textures if material.vis.source_id else {}

    result: dict[str, Any] = {
        "name": material.name,
        "pbrMetallicRoughness": pbr_mr,
    }

    # Texture references (as data URIs)
    for channel, gltf_prop in _GLTF_TEX_MAP.items():
        if channel in textures:
            result[gltf_prop] = {
                "source": _to_data_uri(textures[channel]),
            }

    if any(c > 0 for c in pbr.emissive):
        result["emissiveFactor"] = list(pbr.emissive)

    if pbr.transmission > 0.0:
        result["extensions"] = {
            "KHR_materials_transmission": {
                "transmissionFactor": pbr.transmission,
            }
        }

    return result


def export_mtlx(material: Material, output_dir: Path) -> Path:
    """Export as a MaterialX .mtlx file + PNG textures on disk.

    Writes:
        output_dir/
            <name>.mtlx
            <name>_color.png
            <name>_normal.png
            ...

    Args:
        material: Material with vis data.
        output_dir: Directory to write into (created if needed).

    Returns:
        Path to the written .mtlx file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = material.name.replace(" ", "_").replace("/", "_")
    pbr = material.properties.pbr
    textures = material.vis.textures if material.vis.source_id else {}

    # Write PNG files
    tex_refs: dict[str, str] = {}
    for channel, png_bytes in textures.items():
        filename = f"{safe_name}_{channel}.png"
        (output_dir / filename).write_bytes(png_bytes)
        tex_refs[channel] = filename

    # Build MaterialX XML
    root = Element("materialx", version="1.39")
    root.set("xmlns", "http://www.materialx.org/")

    # Comment with provenance
    graph = SubElement(root, "nodegraph", name=f"{safe_name}_graph")

    # Image nodes for each texture
    for channel, filename in tex_refs.items():
        img = SubElement(graph, "image", name=f"{channel}_tex", type="color3")
        inp = SubElement(img, "input", name="file", type="filename")
        inp.set("value", filename)

    # Standard surface node
    surface = SubElement(graph, "standard_surface", name="surface", type="surfaceshader")

    # Base color
    if "color" in tex_refs:
        inp = SubElement(surface, "input", name="base_color", type="color3")
        inp.set("nodename", "color_tex")
    else:
        inp = SubElement(surface, "input", name="base_color", type="color3")
        inp.set("value", f"{pbr.base_color[0]}, {pbr.base_color[1]}, {pbr.base_color[2]}")

    # Normal
    if "normal" in tex_refs:
        inp = SubElement(surface, "input", name="normal", type="vector3")
        inp.set("nodename", "normal_tex")

    # Roughness
    inp = SubElement(surface, "input", name="specular_roughness", type="float")
    inp.set("value", str(pbr.roughness))

    # Metallic
    inp = SubElement(surface, "input", name="metalness", type="float")
    inp.set("value", str(pbr.metallic))

    # Material node
    mat = SubElement(root, "material", name=f"{safe_name}_mat")
    SubElement(mat, "shaderref", name="surface_ref", node="surface")

    # Write
    mtlx_path = output_dir / f"{safe_name}.mtlx"
    indent(root, space="  ")
    tree = ElementTree(root)
    tree.write(str(mtlx_path), xml_declaration=True, encoding="utf-8")

    return mtlx_path
