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

from typing import Any

# Re-export the full adapters module so new adapters (e.g. to_ktx2)
# are available as soon as mat-vis-client ships them
from mat_vis_client import (
    MatVisClient,
    adapters,  # noqa: F401
    get_manifest,
    prefetch,
    rowmap_entry,
    seed_indexes,
)


def fetch(
    source: str, material_id: str, *, tier: str = "1k", tag: str | None = None
) -> dict[str, bytes]:
    """Fetch all texture channels for a material from mat-vis.

    Thin wrapper around MatVisClient.fetch_all_textures so we don't
    depend on a module-level `fetch` function in mat-vis-client (it
    was removed upstream after 2026.4.x in favor of explicit-client
    style — see mat-vis __init__.py docstring).
    """
    from mat_vis_client import _get_client

    client = MatVisClient(tag=tag) if tag else _get_client()
    return client.fetch_all_textures(source, material_id, tier=tier)


def search(
    *,
    category: str | None = None,
    tags: list[str] | None = None,
    roughness: float | None = None,
    metalness: float | None = None,
    source: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Search the mat-vis index by category, tags, and scalar similarity.

    Args:
        category: filter by canonical category (metal, wood, stone, ...)
        tags: require ALL these tags to be present in the entry's tags list
        roughness / metalness: score by scalar distance (if set in index)
        source: limit to one source
        limit: max results

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

    required_tags = set(t.lower() for t in (tags or []))

    # Search all sources, no tier filter
    sources = [source] if source else client.sources()
    results: list[dict] = []
    for src in sources:
        try:
            for entry in client.index(src):
                if category and entry.get("category") != category:
                    continue
                entry_tags = set(t.lower() for t in entry.get("tags", []))
                if required_tags and not required_tags.issubset(entry_tags):
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


def client() -> MatVisClient:
    """Get the shared MatVisClient instance (lazy-initialized).

    Future-proof access point — any new methods mat-vis-client adds
    are available immediately without pymat code changes:

        c = vis.client()
        c.tiers()           # discover available tiers
        c.sources("1k")     # discover sources for a tier
        c.search("metal")   # search by category
        c.fetch_all_textures("ambientcg", "Metal032", tier="1k")
    """
    from mat_vis_client import _get_client

    return _get_client()


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
    # Adapters module — new adapters auto-available
    "adapters",
]
