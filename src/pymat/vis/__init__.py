"""
Visual material data from mat-vis.

Public API — all functions importable from `pymat.vis` directly:

    from pymat import vis

    vis.search(category="metal", roughness=0.3)
    vis.fetch("ambientcg", "Metal032", tier="1k")
    vis.prefetch("ambientcg", tier="1k")
    vis.get_manifest()
    vis.rowmap_entry("ambientcg", "Metal032", tier="1k")

Powered by mat-vis-client (installed separately or from git).
Material.vis wires into this module for lazy texture loading.
"""

import mat_vis_client
from mat_vis_client import (
    MatVisClient,
    fetch,
    get_manifest,
    prefetch,
    rowmap_entry,
    seed_indexes,
    search as _upstream_search,
)

# Re-export the full adapters module so new adapters (e.g. to_ktx2)
# are available as soon as mat-vis-client ships them
from mat_vis_client import adapters  # noqa: F401

from typing import Any


def search(
    *,
    category: str | None = None,
    roughness: float | None = None,
    metalness: float | None = None,
    source: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Search the mat-vis index by category and scalar similarity.

    Does NOT filter by tier — search is for finding materials,
    tier is a fetch-time concern.
    """
    from mat_vis_client import _get_client

    client = _get_client()

    roughness_range = None
    if roughness is not None:
        roughness_range = (max(0.0, roughness - 0.2), min(1.0, roughness + 0.2))

    metalness_range = None
    if metalness is not None:
        metalness_range = (max(0.0, metalness - 0.2), min(1.0, metalness + 0.2))

    # Search all sources, no tier filter
    sources = [source] if source else client.sources()
    results: list[dict] = []
    for src in sources:
        try:
            for entry in client.index(src):
                if category and entry.get("category") != category:
                    continue
                if roughness_range and not (
                    entry.get("roughness") is not None
                    and roughness_range[0] <= entry["roughness"] <= roughness_range[1]
                ):
                    continue
                if metalness_range and not (
                    entry.get("metalness") is not None
                    and metalness_range[0] <= entry["metalness"] <= metalness_range[1]
                ):
                    continue
                results.append(entry)
        except Exception:
            continue

    # Score by scalar distance
    for r in results:
        score = 0.0
        if roughness is not None and r.get("roughness") is not None:
            score += abs(r["roughness"] - roughness)
        if metalness is not None and r.get("metalness") is not None:
            score += abs(r["metalness"] - metalness)
        r["score"] = score

    results.sort(key=lambda r: r["score"])
    return results[:limit]


__all__ = [
    # Client functions
    "search",
    "fetch",
    "prefetch",
    "rowmap_entry",
    "get_manifest",
    "seed_indexes",
    "MatVisClient",
    # Adapters module — pass-through from mat-vis-client
    # New adapters (to_ktx2, etc.) are available automatically
    "adapters",
]
