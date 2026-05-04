"""
Visual material data from mat-vis.

Public API — all functions importable from ``pymat.vis`` directly::

    from pymat import vis

    # Discovery
    vis.search(category="metal", tags=["brushed", "silver"])

    # Raw fetch (usually you want material.vis.textures instead)
    vis.fetch("ambientcg", "Metal032", tier="1k")
    vis.prefetch("ambientcg", tier="1k")
    vis.get_manifest()
    vis.rowmap_entry("ambientcg", "Metal032", tier="1k")

    # Adapters — Material → external format
    vis.to_threejs(material)    # MeshPhysicalMaterial init dict
    vis.to_gltf(material)       # glTF 2.0 material
    vis.export_mtlx(material, "./out")

    # Escape hatch — the shared MatVisClient
    vis.client().tiers()

Powered by ``mat-vis-client`` (separate PyPI package). ``Material.vis``
wires into this module for lazy texture loading; see ADR-0002.
"""

from typing import Any

from mat_vis_client import (
    MatVisClient,
    get_manifest,
    prefetch,
    rowmap_entry,
    seed_indexes,
)

# Shared-singleton accessor: ``get_client`` became public in
# mat-vis-client 0.5.0 (see mat-vis#84). Pinned in pyproject.toml.
from mat_vis_client import get_client as _shared_client
from mat_vis_client import search as _client_search

# Domain types: re-exported so consumers can construct or type-hint
# without reaching into the private ``_model`` module.
from pymat.vis._model import FinishEntry, Vis, VisDeltas

# Material-accepting adapters: Three.js / glTF / MaterialX.
# Re-exported at top level so ``from pymat.vis import to_threejs`` works
# and tab completion on ``pymat.vis.`` surfaces the main cross-tool
# handoff. Note: ``pymat.vis.adapters`` resolves to the local submodule
# (Material signatures). Users who want mat-vis-client's primitive-
# signature adapters (``(scalars_dict, textures_dict)``) should import
# them explicitly: ``from mat_vis_client import adapters``.
from pymat.vis.adapters import export_mtlx, to_gltf, to_threejs


def fetch(
    source: str, material_id: str, *, tier: str = "1k", tag: str | None = None
) -> dict[str, bytes]:
    """Fetch all texture channels for a material from mat-vis.

    Thin wrapper around MatVisClient.fetch_all_textures so we don't
    depend on a module-level `fetch` function in mat-vis-client (it
    was removed upstream after 2026.4.x in favor of explicit-client
    style — see mat-vis __init__.py docstring).
    """
    client = MatVisClient(tag=tag) if tag else _shared_client()
    return client.fetch_all_textures(source, material_id, tier=tier)


def search(
    *,
    category: str | None = None,
    tags: list[str] | None = None,
    roughness: float | None = None,
    metalness: float | None = None,
    source: str | None = None,
    tier: str = "1k",
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Search the mat-vis index by category, tags, and scalar similarity.

    Args:
        category: filter by canonical category (metal, wood, stone, ...)
        tags: require ALL these tags to be present in the entry's tags list
        roughness / metalness: score by scalar distance (widened ±0.2)
        source: limit to one source
        tier: only return entries that have this tier available (default 1k);
            scalar-only sources (e.g. physicallybased) are tier-independent
        limit: max results

    Thin forwarder to ``mat_vis_client.search`` for the category / scalar /
    tier / scoring path; adds the ``tags`` post-filter (not in upstream).

    Index entries follow the mat-vis 0.6.x schema: scalars and category
    live under ``entry["mat_vis"]["category"]`` / ``["pbr"]["roughness"]``.
    """
    results = _client_search(
        category=category,
        roughness=roughness,
        metalness=metalness,
        source=source,
        tier=tier,
        limit=None,  # apply limit after tags post-filter
    )

    if tags:
        required = {t.lower() for t in tags}
        results = [
            e
            for e in results
            if required.issubset({t.lower() for t in (e.get("mat_vis") or {}).get("tags") or []})
        ]

    return results[:limit]


def client() -> MatVisClient:
    """Get the shared ``MatVisClient`` singleton (lazy-initialized).

    Module-level entry point for operations that don't have a material
    in hand yet — tier enumeration, cache management, discovery before
    a material is picked::

        c = vis.client()
        c.tiers()           # ["128", "256", "1k", "ktx2-1k", "mtlx", ...]
        c.sources("1k")     # ["ambientcg", "polyhaven", ...]
        c.search("metal")   # search by category
        c.fetch_all_textures("ambientcg", "Metal032", tier="1k")

    **Note:** if you already have a ``Material``, use
    ``material.vis.client`` — it's the same singleton without the
    parens, and the property exists on every ``Vis`` by ADR-0002.

    Future-proof: any new method ``mat-vis-client`` adds is callable
    immediately without a py-mat release.
    """
    return _shared_client()


__all__ = [
    # Factory — future-proof, exposes full mat-vis-client API
    "client",
    # Convenience functions (delegates to client singleton)
    "search",
    "fetch",
    "prefetch",
    "rowmap_entry",
    "get_manifest",
    "seed_indexes",
    "MatVisClient",
    # Domain types — Vis dataclass + the override-kwargs TypedDict
    "Vis",
    "VisDeltas",
    "FinishEntry",
    # Material → external-format adapters (the main cross-tool handoff)
    "to_threejs",
    "to_gltf",
    "export_mtlx",
    # Adapters module — new adapters auto-available
    "adapters",
]
