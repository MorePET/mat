"""
mat-vis client — pure Python, stdlib-only fetch layer.

Talks to mat-vis GitHub Release assets via HTTP range reads
guided by rowmap JSON files. No pyarrow, no binary deps.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_GITHUB_BASE = "https://github.com/MorePET/mat-vis/releases/download"
_DEFAULT_TAG = "v0.1.0"

_CACHE_DIR = Path(
    os.environ.get("MAT_VIS_CACHE_DIR", Path.home() / ".cache" / "mat-vis")
)


def _cache_dir() -> Path:
    """Return the active cache directory, creating it if needed."""
    d = _CACHE_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _asset_url(tag: str, filename: str) -> str:
    """Build a GitHub Release asset URL."""
    return f"{_GITHUB_BASE}/{tag}/{filename}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _fetch_json(url: str, cache_path: Path | None = None) -> Any:
    """Fetch a JSON URL, optionally caching to disk."""
    if cache_path and cache_path.exists():
        return json.loads(cache_path.read_text())

    log.debug("fetching %s", url)
    try:
        resp = urlopen(url, timeout=30)
        data = json.loads(resp.read())
    except (HTTPError, URLError, TimeoutError) as exc:
        raise ConnectionError(f"Failed to fetch {url}: {exc}") from exc

    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(data))
        log.debug("cached to %s", cache_path)

    return data


def _range_read(url: str, offset: int, length: int) -> bytes:
    """HTTP range read — fetch exactly [offset, offset+length) bytes."""
    req = Request(url)
    req.add_header("Range", f"bytes={offset}-{offset + length - 1}")
    log.debug("range-read %s [%d, +%d]", url, offset, length)
    try:
        resp = urlopen(req, timeout=60)
        data = resp.read()
    except (HTTPError, URLError, TimeoutError) as exc:
        raise ConnectionError(
            f"Range read failed: {url} [{offset}:{offset + length}]: {exc}"
        ) from exc

    if len(data) != length:
        raise ValueError(
            f"Range read returned {len(data)} bytes, expected {length}"
        )
    return data


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_manifest(
    release_tag: str | None = None,
) -> dict:
    """Fetch release metadata (index + rowmap URLs).

    Currently returns a simple dict with the tag and base URL.
    Future: fetch release-manifest.json when it ships.

    Args:
        release_tag: Calver tag, e.g. "v0.1.0". Uses default if None.

    Returns:
        Dict with release_tag and base_url.
    """
    tag = release_tag or _DEFAULT_TAG
    return {
        "release_tag": tag,
        "base_url": f"{_GITHUB_BASE}/{tag}/",
    }


def search(
    *,
    category: str | None = None,
    roughness: float | None = None,
    metalness: float | None = None,
    source: str | None = None,
    tag: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Search the mat-vis index by scalar similarity.

    Runs locally against the cached JSON index (~50 entries in v0.1.0).
    No network needed if the index has been fetched once.

    Args:
        category: Filter by category ("metal", "wood", "stone", ...).
        roughness: Target roughness — results ranked by distance.
        metalness: Target metalness — results ranked by distance.
        source: Filter by source ("ambientcg", "polyhaven", ...).
        tag: Release tag. Uses default if None.
        limit: Max results to return.

    Returns:
        List of dicts with "id", "source", "category", "roughness",
        "metalness", "score". Sorted by score (lower = closer match).
    """
    tag = tag or _DEFAULT_TAG
    cache = _cache_dir() / ".index"
    cache.mkdir(parents=True, exist_ok=True)

    # Load all available indexes
    entries: list[dict] = []
    for src in ["ambientcg", "polyhaven", "gpuopen", "physicallybased"]:
        url = _asset_url(tag, f"{src}.json")
        cache_path = cache / f"{src}-{tag}.json"
        try:
            data = _fetch_json(url, cache_path)
            entries.extend(data)
        except ConnectionError:
            log.debug("index for %s not available at tag %s", src, tag)

    # Filter
    if source:
        entries = [e for e in entries if e.get("source") == source]
    if category:
        entries = [e for e in entries if e.get("category") == category]

    # Score by scalar distance
    def _score(entry: dict) -> float:
        score = 0.0
        if roughness is not None and entry.get("roughness") is not None:
            score += abs(entry["roughness"] - roughness)
        if metalness is not None and entry.get("metalness") is not None:
            score += abs(entry["metalness"] - metalness)
        return score

    for e in entries:
        e["score"] = _score(e)

    entries.sort(key=lambda e: e["score"])
    return entries[:limit]


def fetch(
    source: str,
    material_id: str,
    *,
    tier: str = "1k",
    tag: str | None = None,
    cache: bool = True,
    cache_dir: Path | None = None,
) -> dict[str, bytes]:
    """Fetch textures for a material via rowmap + HTTP range read.

    Args:
        source: Source name ("ambientcg", "polyhaven", ...).
        material_id: Material ID within the source (e.g. "Metal032").
        tier: Resolution tier ("1k", "2k", "4k", "8k").
        tag: Release tag. Uses default if None.
        cache: Write fetched bytes to local cache. Default True.
        cache_dir: Override cache directory.

    Returns:
        Dict of channel → PNG bytes, e.g. {"color": b"\\x89PNG...", ...}.
    """
    tag = tag or _DEFAULT_TAG
    cdir = Path(cache_dir) if cache_dir else _cache_dir()

    # Check local cache first
    mat_cache = cdir / source / tier / material_id
    if cache and mat_cache.exists():
        textures = {}
        for png_file in mat_cache.glob("*.png"):
            textures[png_file.stem] = png_file.read_bytes()
        if textures:
            log.debug("cache hit: %s/%s (%d channels)", source, material_id, len(textures))
            return textures

    # Fetch rowmap
    rowmap = _get_rowmap(source, tier, tag, cdir)
    mat_entry = rowmap.get("materials", {}).get(material_id)
    if mat_entry is None:
        raise KeyError(
            f"Material '{material_id}' not found in {source} {tier} rowmap. "
            f"Available: {list(rowmap.get('materials', {}).keys())[:10]}..."
        )

    # Build parquet URL
    parquet_file = rowmap.get("parquet_file", f"mat-vis-{source}-{tier}.parquet")
    parquet_url = _asset_url(tag, parquet_file)

    # Range-read each channel
    textures: dict[str, bytes] = {}
    for channel, offsets in mat_entry.items():
        png_bytes = _range_read(parquet_url, offsets["offset"], offsets["length"])

        # Verify PNG magic
        if not png_bytes[:4] == b"\x89PNG":
            log.warning(
                "%s/%s/%s: expected PNG magic, got %r",
                source, material_id, channel, png_bytes[:4],
            )
            continue

        textures[channel] = png_bytes

        # Cache to disk
        if cache:
            channel_path = mat_cache / f"{channel}.png"
            channel_path.parent.mkdir(parents=True, exist_ok=True)
            channel_path.write_bytes(png_bytes)

    log.debug("fetched %s/%s: %d channels", source, material_id, len(textures))
    return textures


def rowmap_entry(
    source: str,
    material_id: str,
    *,
    tier: str = "1k",
    tag: str | None = None,
) -> dict[str, dict[str, int]]:
    """Get raw byte-offset info for DIY consumers.

    Returns the rowmap entry for a material — channel → {offset, length}.

    Args:
        source: Source name.
        material_id: Material ID.
        tier: Resolution tier.
        tag: Release tag. Uses default if None.

    Returns:
        Dict of channel → {"offset": int, "length": int}.
    """
    tag = tag or _DEFAULT_TAG
    rowmap = _get_rowmap(source, tier, tag, _cache_dir())
    mat_entry = rowmap.get("materials", {}).get(material_id)
    if mat_entry is None:
        raise KeyError(
            f"Material '{material_id}' not found in {source} {tier} rowmap"
        )
    return mat_entry


# ---------------------------------------------------------------------------
# Internal: rowmap fetch + cache
# ---------------------------------------------------------------------------


def _get_rowmap(source: str, tier: str, tag: str, cache_root: Path) -> dict:
    """Fetch and cache a rowmap JSON."""
    cache_path = cache_root / ".index" / f"{source}-{tier}-{tag}-rowmap.json"
    url = _asset_url(tag, f"{source}-{tier}-rowmap.json")
    return _fetch_json(url, cache_path)
