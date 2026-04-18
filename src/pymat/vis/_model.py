"""
Vis model — the visual representation attached to a Material.

Material.vis returns a Vis instance. It holds:
- source_id: pointer to a mat-vis appearance
- finishes: dict of finish_name → source_id (for TOML-registered materials)
- textures: dict of channel → PNG bytes (lazy-fetched, cached)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar


@dataclass
class ResolvedChannel:
    """Result of resolving a channel across texture + scalar sources."""

    texture: bytes | None = None  # PNG bytes if texture map available
    scalar: float | None = None  # scalar fallback (e.g. the vis.roughness value)
    has_texture: bool = False


@dataclass
class Vis:
    """Visual representation of a material, backed by mat-vis data.

    Always instantiated (never None on Material). Starts with
    source_id=None and empty textures for custom materials.
    Populated from TOML [vis] section for registered materials.

    Usage:
        steel.vis.source_id          # "ambientcg/Metal_Brushed_001"
        steel.vis.textures["color"]  # PNG bytes (lazy-fetched)
        steel.vis.finishes           # {"brushed": "...", "polished": "..."}
        steel.vis.finish = "polished"  # switch appearance
    """

    source_id: str | None = None
    tier: str = "1k"
    finishes: dict[str, str] = field(default_factory=dict)

    # PBR scalars — the canonical home in 3.0. Loaded from the [vis]
    # section of a TOML material, or derived from physics properties
    # (ior from optical.refractive_index, transmission from optical
    # .transparency / 100) in Material.__post_init__.
    roughness: float | None = None
    metallic: float | None = None
    base_color: tuple | None = None
    ior: float | None = None
    transmission: float | None = None
    clearcoat: float | None = None
    emissive: tuple | None = None

    _finish: str | None = None
    _textures: dict[str, bytes] = field(default_factory=dict, repr=False)
    _fetched: bool = False

    @property
    def finish(self) -> str | None:
        """Current finish name, or None if using source_id directly."""
        return self._finish

    @finish.setter
    def finish(self, name: str) -> None:
        """Switch to a named finish. Clears cached textures."""
        if name not in self.finishes:
            available = list(self.finishes.keys())
            raise ValueError(f"Unknown finish '{name}'. Available: {available}")
        self._finish = name
        self.source_id = self.finishes[name]
        self._textures.clear()
        self._fetched = False

    @property
    def textures(self) -> dict[str, bytes]:
        """Channel → PNG bytes. Lazy-fetched on first access.

        Returns empty dict if source_id is None (no appearance set).
        """
        if self.source_id is None:
            return {}

        if not self._fetched:
            self._fetch()

        return self._textures

    def resolve(self, channel: str, scalar: float | None = None) -> ResolvedChannel:
        """Resolve a channel: texture if available, scalar fallback.

        Args:
            channel: Channel name ("roughness", "metalness", etc.)
            scalar: Scalar fallback value (from properties.pbr).

        Returns:
            ResolvedChannel with texture bytes and/or scalar value.
        """
        tex = self.textures.get(channel)
        return ResolvedChannel(
            texture=tex,
            scalar=scalar,
            has_texture=tex is not None,
        )

    def discover(
        self,
        *,
        category: str | None = None,
        roughness: float | None = None,
        metallic: float | None = None,
        limit: int = 5,
        auto_set: bool = False,
    ) -> list[dict[str, Any]]:
        """Search mat-vis for appearances matching this material's scalars.

        Does NOT set source_id automatically — returns candidates for
        the user to review. Pass auto_set=True to pick the top match.

        Args:
            category: Filter by category. If None, tries to infer from
                the material's existing PBR properties.
            roughness: Target roughness. If None, reads from the material.
            metallic: Target metalness. If None, reads from the material.
            limit: Max candidates to return.
            auto_set: If True, set source_id to the top match.

        Returns:
            List of candidate dicts with "id", "source", "category",
            "score". Sorted by score (lower = closer match).

        Example:
            candidates = steel.vis.discover(category="metal")
            # [{"id": "ambientcg/Metal032", "score": 0.05}, ...]
            steel.vis.source_id = candidates[0]["id"]  # manual pick
            # or:
            steel.vis.discover(category="metal", auto_set=True)
        """
        from mat_vis_client import search

        results = search(
            category=category,
            roughness=roughness,
            metalness=metallic,
            limit=limit,
        )

        # Reformat ids as "source/id" for direct assignment
        for r in results:
            if "source" in r and "id" in r and "/" not in r["id"]:
                r["id"] = f"{r['source']}/{r['id']}"

        if auto_set and results:
            self.source_id = results[0]["id"]
            self._textures.clear()
            self._fetched = False

        return results

    def _fetch(self) -> None:
        """Fetch textures via the vis client. Called lazily."""
        if self.source_id is None:
            return

        # Parse "source/material_id" format
        parts = self.source_id.split("/", 1)
        if len(parts) != 2:
            raise ValueError(
                f"Invalid source_id '{self.source_id}'. Expected 'source/material_id' format."
            )
        source, material_id = parts

        # Import from pymat.vis (our wrapper) rather than mat-vis-client
        # directly. mat-vis-client 0.2.0+ removed the module-level `fetch`
        # in favor of the explicit-client style (MatVisClient().fetch_all_textures).
        from pymat.vis import fetch

        self._textures = fetch(source, material_id, tier=self.tier)
        self._fetched = True

    _PBR_SCALAR_FIELDS = (
        "roughness",
        "metallic",
        "base_color",
        "ior",
        "transmission",
        "clearcoat",
        "emissive",
    )

    _PBR_DEFAULTS: ClassVar[dict[str, Any]] = {
        "roughness": 0.5,
        "metallic": 0.0,
        "base_color": (0.8, 0.8, 0.8, 1.0),
        "ior": 1.5,
        "transmission": 0.0,
        "clearcoat": 0.0,
        "emissive": (0, 0, 0),
    }

    def get(self, field: str, default: Any = None) -> Any:
        """Get a PBR scalar with fallback to default.

        Returns the field value if set (not None), otherwise the
        default. If no default provided, uses _PBR_DEFAULTS.

        Usage:
            vis.get("roughness")       # → 0.3 if set, 0.5 if None
            vis.get("roughness", 0.0)  # → 0.3 if set, 0.0 if None
        """
        val = getattr(self, field, None)
        if val is not None:
            return val
        if default is not None:
            return default
        return self._PBR_DEFAULTS.get(field)

    @classmethod
    def from_toml(cls, vis_data: dict[str, Any]) -> Vis:
        """Construct from a TOML [vis] section.

        Accepts PBR scalars alongside finishes/source_id. When PBR
        scalars are present in [vis], they become the canonical source
        and are synced back to properties.pbr for backward compat.

        TOML structure:
            [material.vis]
            default = "brushed"
            roughness = 0.3
            metallic = 1.0
            base_color = [0.75, 0.75, 0.77, 1.0]

            [material.vis.finishes]
            brushed = "ambientcg/Metal_Brushed_001"
            polished = "ambientcg/Metal_Polished_002"
        """
        finishes = vis_data.get("finishes", {})
        default_finish = vis_data.get("default")

        source_id = None
        finish = None
        if default_finish and default_finish in finishes:
            source_id = finishes[default_finish]
            finish = default_finish
        elif finishes:
            finish = next(iter(finishes))
            source_id = finishes[finish]

        # Extract PBR scalars from [vis] section
        scalars = {}
        for fname in cls._PBR_SCALAR_FIELDS:
            if fname in vis_data:
                val = vis_data[fname]
                if isinstance(val, list):
                    val = tuple(val)
                scalars[fname] = val

        return cls(
            source_id=source_id,
            finishes=finishes,
            _finish=finish,
            **scalars,
        )
