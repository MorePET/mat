"""Material-aware output adapters — dispatchers that resolve a
``Material`` (or standalone ``Vis``) to the right rendering path.

Per ADR-0002, mat-vis-client owns the actual rendering logic — both
the catalog-backed ``VisAsset`` ergonomic class and the dumb free-
function primitives. These wrappers are pure dispatch: pull the Vis +
optional Material name out, delegate to ``Vis.to_threejs()`` /
``to_gltf()`` / ``export_mtlx()``, which in turn pick between
``client.asset(...).to_X()`` (catalog) and the free-function
``mat_vis_client.adapters.to_X(scalars, textures)`` primitive (no
identity).

Usage::

    from pymat.vis.adapters import to_threejs, to_gltf, export_mtlx
    result = to_threejs(material)          # Material form
    result = to_threejs(material.vis)      # Vis form — same output

The polymorphism lets ``Vis.to_gltf()`` / ``Vis.to_threejs()`` method
sugar work without a back-reference from ``Vis`` to its owning
``Material``; module-level functions read ``material.name`` for
glTF/MTLX label fields.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Union

from pymat.vis._model import _rgba_to_hex

if TYPE_CHECKING:
    from pymat.core import _MaterialInternal as Material
    from pymat.vis._model import Vis

    MaterialOrVis = Union[Material, Vis]


def _resolve_vis_and_name(obj: MaterialOrVis) -> tuple[Vis, str]:
    """Unwrap a Material (``→ .vis, .name``) or a standalone Vis
    (``→ self, ""``). Duck-typed via the ``.vis`` attribute: anything
    that exposes ``.vis`` is treated as the owning Material."""
    if hasattr(obj, "vis"):
        return obj.vis, getattr(obj, "name", "") or ""
    return obj, ""  # assume it's a Vis


def _extract_scalars(obj: MaterialOrVis) -> dict[str, Any]:
    """Caller-set scalars + ``_PBR_DEFAULTS`` fallback.

    Compat shim for the legacy Vis-field-only extraction. Preserved
    because tests/test_adapters.py exercises it directly. The
    catalog-aware path lives in ``Vis.scalars`` (which delegates
    through ``VisAsset``); use that for new code.
    """
    vis, _ = _resolve_vis_and_name(obj)
    return vis._scalars_with_defaults()


def _extract_textures(obj: MaterialOrVis) -> dict[str, bytes]:
    """Texture dict from a Material's Vis (or a plain Vis).

    Compat shim. Returns ``{}`` when there's no mat-vis identity.
    """
    vis, _ = _resolve_vis_and_name(obj)
    if not vis.has_mapping:
        return {}
    return vis.textures


def to_threejs(obj: MaterialOrVis) -> dict[str, Any]:
    """Format as a Three.js ``MeshPhysicalMaterial`` parameter dict.

    Accepts either a ``Material`` or a standalone ``Vis``. Delegates
    to ``Vis.to_threejs()`` which dispatches on ``has_mapping``.
    """
    vis, _ = _resolve_vis_and_name(obj)
    return vis.to_threejs()


def to_gltf(obj: MaterialOrVis, *, name: str | None = None) -> dict[str, Any]:
    """Format as a glTF pbrMetallicRoughness material dict.

    Accepts either a ``Material`` (its ``.name`` is used as the glTF
    material ``name`` field) or a standalone ``Vis`` (pass ``name=``
    explicitly to populate the field; empty string otherwise).
    """
    vis, resolved_name = _resolve_vis_and_name(obj)
    return vis.to_gltf(name=name if name is not None else resolved_name)


def export_mtlx(
    obj: MaterialOrVis,
    output_dir: Path,
    *,
    name: str | None = None,
) -> Path:
    """Export as a MaterialX .mtlx file + PNG textures on disk.

    Accepts either a ``Material`` (its ``.name`` becomes the filename
    stem) or a standalone ``Vis`` (pass ``name=`` explicitly to name
    the output).
    """
    vis, resolved_name = _resolve_vis_and_name(obj)
    return vis.export_mtlx(output_dir, name=name if name is not None else resolved_name)
