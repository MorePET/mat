"""MCP server entrypoint — registers each tool function with FastMCP.

Why thin: tool logic lives in :mod:`pymat_mcp.tools` as plain Python
functions. This module only:

1. Builds a FastMCP instance with one ``@mcp.tool()`` per tool
2. Runs the stdio transport (what Claude Desktop / Cursor expect)

Logging goes to stderr exclusively — stdout is the MCP transport
channel and any non-JSON-RPC byte there breaks the connection.
"""

from __future__ import annotations

import logging

# stderr-only logging. Default WARNING; bump via PYMAT_MCP_LOG=DEBUG.
import os
import sys

from mcp.server.fastmcp import FastMCP

from pymat_mcp import __version__, tools

logging.basicConfig(
    level=os.environ.get("PYMAT_MCP_LOG", "WARNING").upper(),
    stream=sys.stderr,
    format="%(levelname)s pymat-mcp: %(message)s",
)
log = logging.getLogger("pymat-mcp")


mcp = FastMCP(
    name="pymat",
    instructions=(
        f"pymat-mcp {__version__} — curated material property database "
        "for CAD / engineering. Use search_materials to find candidates "
        "by name, then get_material for the full property dump. "
        "compute_mass turns a build123d volume (mm³) into a mass via "
        "the curated density. to_threejs / to_gltf produce renderer-"
        "ready material dicts."
    ),
)


@mcp.tool()
def search_materials(query: str, limit: int = 10) -> dict:
    """Fuzzy-search the curated material library.

    Args:
        query: Free-text material name, alloy designation, or partial
            string ("stainless", "6061", "lyso"). Case-insensitive.
        limit: Max results (default 10).

    Returns: dict with ``query`` echoed and ``results`` — a list of
    summary rows (``key``, ``name``, ``grade``, ``category``, ``density``).
    """
    return tools.search_materials(query, limit)


@mcp.tool()
def get_material(
    material: str,
    domains: list[str] | None = None,
    include_vis: bool = True,
) -> dict:
    """Curated property dump for a material — chemistry + properties + vis.

    Args:
        material: Registry key (``"s304"``), full name (``"Stainless
            Steel 304"``), or grade (``"304"``). Case-insensitive.
        domains: Property groups to include. Subset of
            ``["mechanical", "thermal", "electrical", "optical",
            "manufacturing", "compliance", "sourcing"]``. Pass a
            narrower list for compact payloads (e.g.
            ``["mechanical"]`` for "what's the yield strength of …").
            Default: all groups.
        include_vis: Include the ``vis`` block (PBR scalars, finishes,
            mat-vis identity). Default ``True``; set ``False`` when
            only mechanical / chemistry data is needed.

    Returns dict with ``key``, ``name``, ``grade``, ``temper``,
    ``treatment``, ``category``, ``formula``, ``molar_mass``,
    ``properties`` (grouped by domain), and optionally ``vis``. On
    miss: ``{"error": ..., "did_you_mean": [{"key": ..., "name": ...},
    ...]}`` with fuzzy suggestions the agent can retry with directly.
    """
    return tools.get_material(material, domains=domains, include_vis=include_vis)


@mcp.tool()
def list_categories() -> dict:
    """Top-level material categories (aluminum, stainless, lyso, …).

    Useful as a discovery starting point before drilling down with
    ``list_grades``.
    """
    return tools.list_categories()


@mcp.tool()
def list_grades(material: str) -> dict:
    """Children (grades / tempers / treatments) of a parent material.

    For ``"stainless"`` returns s304, s316L, …; for ``"s316L"`` may
    return further variants (passivated, electropolished, …).
    """
    return tools.list_grades(material)


@mcp.tool()
def list_finishes(material: str) -> dict:
    """Available finishes (brushed / polished / matte / …) for a material.

    Switching finishes flips the texture set without changing the
    engineering material. Pass the chosen finish name to
    ``to_threejs`` / ``to_gltf`` to get a renderer-ready dict for that
    finish.
    """
    return tools.list_finishes(material)


@mcp.tool()
def compute_mass(material: str, volume_mm3: float) -> dict:
    """Mass in grams for a given volume using curated density.

    Args:
        material: Material key or name.
        volume_mm3: Volume in cubic millimeters (matches build123d
            ``shape.volume`` units).
    """
    return tools.compute_mass(material, volume_mm3)


@mcp.tool()
def get_appearance(material: str) -> dict:
    """Visual / PBR identity for a material.

    Returns ``Vis`` as a dict — mat-vis ``(source, material_id, tier)``,
    finishes map, current finish, PBR scalars. For renderer-ready
    output use ``to_threejs`` / ``to_gltf``.
    """
    return tools.get_appearance(material)


@mcp.tool()
def to_threejs(material: str, finish: str | None = None) -> dict:
    """Three.js ``MeshPhysicalMaterial`` init dict.

    Args:
        material: Material key or name.
        finish: Optional finish name from the material's finishes map
            (e.g. ``"polished"``, ``"brushed"``). Derives a variant via
            ``Vis.override`` + ``Material.with_vis`` — registry is not
            mutated.
    """
    return tools.to_threejs(material, finish)


@mcp.tool()
def to_gltf(material: str, finish: str | None = None) -> dict:
    """glTF 2.0 material node dict.

    Same finish-override semantics as ``to_threejs``.
    """
    return tools.to_gltf(material, finish)


@mcp.tool()
def compare_materials(
    materials: list[str],
    properties: list[str] | None = None,
) -> dict:
    """Side-by-side comparison across selected properties.

    Args:
        materials: List of material keys or names.
        properties: Dotted paths like ``"mechanical.density"`` or
            ``"thermal.melting_point"``. Default: density,
            youngs_modulus, yield_strength, melting_point,
            thermal_conductivity.
    """
    return tools.compare_materials(materials, properties)


def main() -> None:
    """Console entry point — registered as ``pymat-mcp`` script.

    Runs the server on stdio transport. Override via env if you ever
    want SSE/HTTP, but Claude Desktop / Cursor / MCP Inspector all
    expect stdio.

    ``pymat-mcp --version`` prints the version + exits without
    starting the transport — useful for Claude Desktop config
    debugging without a full MCP handshake round-trip.
    """
    if "--version" in sys.argv:
        print(f"pymat-mcp {__version__}")
        return
    log.debug("pymat-mcp %s starting", __version__)
    mcp.run()


if __name__ == "__main__":
    main()
