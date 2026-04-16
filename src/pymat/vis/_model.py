"""
Vis model — the visual representation attached to a Material.

Material.vis returns a Vis instance. It holds:
- source_id: pointer to a mat-vis appearance
- finishes: dict of finish_name → source_id (for TOML-registered materials)
- textures: dict of channel → PNG bytes (lazy-fetched, cached)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ResolvedChannel:
    """Result of resolving a channel across texture + scalar sources."""

    texture: bytes | None = None  # PNG bytes if texture map available
    scalar: float | None = None  # scalar fallback from properties.pbr
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
            raise ValueError(
                f"Unknown finish '{name}'. Available: {available}"
            )
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

    def _fetch(self) -> None:
        """Fetch textures via the vis client. Called lazily."""
        if self.source_id is None:
            return

        # Parse "source/material_id" format
        parts = self.source_id.split("/", 1)
        if len(parts) != 2:
            raise ValueError(
                f"Invalid source_id '{self.source_id}'. "
                f"Expected 'source/material_id' format."
            )
        source, material_id = parts

        from pymat.vis._client import fetch

        self._textures = fetch(source, material_id, tier=self.tier)
        self._fetched = True

    @classmethod
    def from_toml(cls, vis_data: dict[str, Any]) -> Vis:
        """Construct from a TOML [vis] section.

        Expected TOML structure:
            [material.vis]
            default = "brushed"

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
            # No default specified — use first finish
            finish = next(iter(finishes))
            source_id = finishes[finish]

        return cls(
            source_id=source_id,
            finishes=finishes,
            _finish=finish,
        )
