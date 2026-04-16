"""
mat-vis client — pure Python, stdlib-only fetch layer.

Talks to mat-vis GitHub Release assets via HTTP range reads
guided by rowmap JSON files. No pyarrow, no binary deps.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DEFAULT_CACHE_DIR = Path(
    os.environ.get("MAT_VIS_CACHE_DIR", Path.home() / ".cache" / "mat-vis")
)
_DEFAULT_MANIFEST_URL: str | None = os.environ.get("MAT_VIS_MANIFEST_URL")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_manifest(
    release_tag: str | None = None,
    manifest_url: str | None = None,
) -> dict:
    """Fetch the release manifest (URL discovery for all sources × tiers).

    Args:
        release_tag: Calver tag, e.g. "v2026.04.0". Uses latest if None.
        manifest_url: Override URL for the manifest JSON.

    Returns:
        Parsed release-manifest.json dict.
    """
    raise NotImplementedError("mat-vis client not yet implemented — see MorePET/mat#35")


def search(
    *,
    category: str | None = None,
    roughness: float | None = None,
    metalness: float | None = None,
    source: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Search the mat-vis index by scalar similarity.

    Runs locally against the cached JSON index (~3100 entries, in memory).
    No network needed if the index has been fetched once.

    Args:
        category: Filter by category ("metal", "wood", "stone", ...).
        roughness: Target roughness — results ranked by distance.
        metalness: Target metalness — results ranked by distance.
        source: Filter by source ("ambientcg", "polyhaven", ...).
        limit: Max results to return.

    Returns:
        List of dicts with "id", "source", "category", "roughness",
        "metalness", "score" (lower = closer match). Sorted by score.
    """
    raise NotImplementedError("mat-vis client not yet implemented — see MorePET/mat#35")


def fetch(
    source: str,
    material_id: str,
    *,
    tier: str = "1k",
    cache: bool = True,
    cache_dir: Path | None = None,
) -> dict[str, bytes]:
    """Fetch textures for a material via rowmap + HTTP range read.

    Args:
        source: Source name ("ambientcg", "polyhaven", ...).
        material_id: Material ID within the source (e.g. "Metal_Brushed_001").
        tier: Resolution tier ("1k", "2k", "4k", "8k").
        cache: Write fetched bytes to local cache. Default True.
        cache_dir: Override cache directory.

    Returns:
        Dict of channel → PNG bytes, e.g. {"color": b"\\x89PNG...", ...}.
        Only channels present for this material are included.
    """
    raise NotImplementedError("mat-vis client not yet implemented — see MorePET/mat#35")


def rowmap_entry(
    source: str,
    material_id: str,
    *,
    tier: str = "1k",
) -> dict[str, dict[str, int]]:
    """Get raw byte-offset info for DIY consumers.

    Returns the rowmap entry for a material — channel → {offset, length}.
    Consumer can use this with their own HTTP client (JS fetch, curl,
    Rust reqwest, etc.).

    Args:
        source: Source name.
        material_id: Material ID.
        tier: Resolution tier.

    Returns:
        Dict of channel → {"offset": int, "length": int}, e.g.:
        {"color": {"offset": 102400, "length": 51200}, ...}
    """
    raise NotImplementedError("mat-vis client not yet implemented — see MorePET/mat#35")
