"""
PBR (physically-based rendering) integration for `pymat.Material`.

This package defines the `PbrSource` Protocol that `Material.pbr_source`
accepts. Any object conforming to the protocol can be assigned — the
native `PBRProperties` dataclass (lite, in-tree, no extra deps) and the
optional `threejs_materials.PbrProperties` (rich, full MaterialX
support) both satisfy it.

Install the `[pbr]` extra to get the rich backend:

    pip install py-materials[pbr]

Then `from pymat.pbr import PbrProperties` re-exports
`threejs_materials.PbrProperties`, the canonical PBR loader for
build123d / ocp_vscode. See ADR-0002 for the design rationale.
"""

from __future__ import annotations

from pymat.pbr._protocol import PbrSource

__all__ = ["PbrSource"]

# Optional re-export: threejs_materials.PbrProperties when the [pbr]
# extra is installed. Keeps `from pymat.pbr import PbrProperties`
# working as a thin alias, so downstream code doesn't need to know
# which underlying library provides the loader.
try:
    from threejs_materials import PbrProperties  # noqa: F401

    __all__.append("PbrProperties")
except ImportError:  # pragma: no cover
    pass
