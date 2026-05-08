"""Material-aware output adapters.

Pure dispatchers that unwrap a ``Material`` (``→ .vis, .name``) or a
standalone ``Vis`` (``→ self, ""``) and delegate to the corresponding
``Vis`` method. Per ADR-0002 the actual rendering logic lives in
mat-vis-client; ``Vis.to_threejs()`` / ``to_gltf()`` / ``export_mtlx()``
in turn dispatch between catalog-backed (``client.asset(...).scalars``)
and free-function (``mat_vis_client.adapters.to_X(scalars, textures)``)
paths.

Usage::

    from pymat.vis.adapters import to_threejs, to_gltf, export_mtlx
    result = to_threejs(material)          # Material form
    result = to_threejs(material.vis)      # Vis form — same output
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pymat.core import _MaterialInternal as Material
    from pymat.vis._model import Vis

    MaterialOrVis = Material | Vis


def _resolve_vis_and_name(obj: MaterialOrVis) -> tuple[Vis, str]:
    """Unwrap a Material (``→ .vis, .name``) or a standalone Vis
    (``→ self, ""``). Duck-typed via the ``.vis`` attribute: anything
    that exposes ``.vis`` is treated as the owning Material."""
    if hasattr(obj, "vis"):
        return obj.vis, getattr(obj, "name", "") or ""
    return obj, ""  # assume it's a Vis


def to_threejs(obj: MaterialOrVis) -> dict[str, Any]:
    """Three.js ``MeshPhysicalMaterial`` parameter dict. Material name
    is unused (Three.js materials don't carry a name field)."""
    vis, _ = _resolve_vis_and_name(obj)
    return vis.to_threejs()


def to_gltf(obj: MaterialOrVis, *, name: str | None = None) -> dict[str, Any]:
    """glTF pbrMetallicRoughness material dict. ``name=`` overrides;
    otherwise filled from ``Material.name`` (or empty for a bare Vis).
    """
    vis, resolved_name = _resolve_vis_and_name(obj)
    return vis.to_gltf(name=name if name is not None else resolved_name)


def export_mtlx(
    obj: MaterialOrVis,
    output_dir: Path,
    *,
    name: str | None = None,
) -> Path:
    """Export a MaterialX .mtlx file + PNG textures on disk. ``name=``
    sets the filename stem; otherwise from ``Material.name``.
    """
    vis, resolved_name = _resolve_vis_and_name(obj)
    return vis.export_mtlx(output_dir, name=name if name is not None else resolved_name)
