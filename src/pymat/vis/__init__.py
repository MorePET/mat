"""
Visual material data from mat-vis.

Public API — all functions importable from `pymat.vis` directly:

    from pymat import vis

    # Search the mat-vis index (runs locally against cached JSON index)
    results = vis.search(category="metal", roughness=0.3)

    # Fetch textures by mat-vis source ID
    textures = vis.fetch("ambientcg", "Metal_Brushed_001", tier="1k")
    textures["color"]  # raw PNG bytes

    # Raw rowmap entry for DIY consumers (JS shim, curl, etc.)
    entry = vis.rowmap_entry("ambientcg", "Metal_Brushed_001", tier="1k")
    # → {"color": {"offset": 102400, "length": 51200}, ...}

    # URL discovery
    manifest = vis.get_manifest(release_tag="v2026.04.0")

The fetch layer is independent of Material — usable standalone
for any consumer that just wants textures without physics data.

Material.vis wires into this module for its lazy texture loading.
"""

from pymat.vis._client import fetch, get_manifest, prefetch, rowmap_entry, search

__all__ = [
    "search",
    "fetch",
    "prefetch",
    "rowmap_entry",
    "get_manifest",
]
