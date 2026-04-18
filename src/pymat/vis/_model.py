"""
Vis model — the visual representation attached to a Material.

Material.vis returns a Vis instance. It holds:
- source + material_id: pointer to a mat-vis appearance (matches
  mat-vis-client's two-arg signature; see ADR-0002)
- finishes: dict of finish_name → {"source": ..., "id": ...}
- PBR scalars (roughness, metallic, base_color, ior, transmission, ...)

Per ADR-0002, Vis holds identity + scalars only. Anything reachable
on the mat-vis-client is exposed directly via:

- `material.vis.client` — the shared MatVisClient (escape hatch)
- `material.vis.source` — MtlxSource (pre-filled delegate)
- `material.vis.textures` / `.channels` / `.materialize(...)` — same

These are thin delegates, not wrappers. No translation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from mat_vis_client import MatVisClient, MtlxSource


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
    source=None and empty textures for custom materials.
    Populated from TOML [vis] section for registered materials.

    Usage:
        steel.vis.source           # "ambientcg"
        steel.vis.material_id      # "Metal012"
        steel.vis.textures["color"]  # PNG bytes (lazy-fetched)
        steel.vis.finishes         # {"brushed": {"source": ..., "id": ...}, ...}
        steel.vis.finish = "polished"  # switch appearance
        steel.vis.mtlx.xml         # MaterialX document (3.1+)
    """

    # Identity — matches mat-vis-client's (source, material_id, tier) signature
    source: str | None = None
    material_id: str | None = None
    tier: str = "1k"
    # {finish_name: {"source": str, "id": str}}
    finishes: dict[str, dict[str, str]] = field(default_factory=dict)

    # PBR scalars — the canonical home in 3.0+. Loaded from the [vis]
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

    # ── Identity helpers ─────────────────────────────────────────

    @property
    def has_mapping(self) -> bool:
        """True when this Vis points at a concrete mat-vis appearance."""
        return self.source is not None and self.material_id is not None

    @property
    def source_id(self) -> str | None:
        """Deprecated alias. Use `source` + `material_id` instead.

        Retained as a read-only convenience for logging and tests; raises
        on assignment in 3.1 per ADR-0002. See docs/migration/v2-to-v3.md.
        """
        if not self.has_mapping:
            return None
        return f"{self.source}/{self.material_id}"

    @source_id.setter
    def source_id(self, _value: str) -> None:
        raise AttributeError(
            "Vis.source_id is read-only in 3.1+. Set vis.source and "
            "vis.material_id separately, or assign a finish. "
            "See docs/migration/v2-to-v3.md."
        )

    # ── Finish switcher ──────────────────────────────────────────

    @property
    def finish(self) -> str | None:
        """Current finish name, or None if set directly without a finish map."""
        return self._finish

    @finish.setter
    def finish(self, name: str) -> None:
        """Switch to a named finish. Clears cached textures."""
        if name not in self.finishes:
            available = list(self.finishes.keys())
            raise ValueError(f"Unknown finish '{name}'. Available: {available}")
        self._finish = name
        entry = self.finishes[name]
        self.source = entry["source"]
        self.material_id = entry["id"]
        self._textures.clear()
        self._fetched = False

    # ── mat-vis-client: exposed, not wrapped (ADR-0002) ─────────

    @property
    def client(self) -> MatVisClient:
        """The shared mat-vis-client singleton.

        Escape hatch for mat-vis-client methods not keyed by a material —
        tier enumeration, cache management, discovery before a material
        is picked. Material-keyed operations should prefer the dotted
        sugar on this Vis (`.textures`, `.source`, `.channels`, ...).
        """
        from mat_vis_client import _get_client

        return _get_client()

    @property
    def mtlx(self) -> MtlxSource | None:
        """MaterialX document accessor — lazy, no network IO until used.

        Returns None if this Vis has no mapping.

            xml = material.vis.mtlx.xml
            material.vis.mtlx.export("./out")
            material.vis.mtlx.original   # upstream-author variant, or None

        Thin delegate for `client.mtlx(source, material_id, tier=tier)`.
        """
        if not self.has_mapping:
            return None
        return self.client.mtlx(self.source, self.material_id, tier=self.tier)

    # ── Textures + channels ──────────────────────────────────────

    @property
    def textures(self) -> dict[str, bytes]:
        """Channel → PNG bytes. Lazy-fetched on first access.

        Returns empty dict if no mapping is set.
        """
        if not self.has_mapping:
            return {}

        if not self._fetched:
            self._fetch()

        return self._textures

    @property
    def channels(self) -> list[str]:
        """Available texture channels for this material at this tier."""
        if not self.has_mapping:
            return []
        return self.client.channels(self.source, self.material_id, self.tier)

    def materialize(self, output_dir: str | Path) -> Path | None:
        """Write PNGs for every channel to a directory. Returns the directory.

        Thin delegate for `client.materialize(source, material_id, tier, out)`.
        Returns None if this Vis has no mapping.
        """
        if not self.has_mapping:
            return None
        return self.client.materialize(
            self.source, self.material_id, self.tier, output_dir
        )

    def resolve(self, channel: str, scalar: float | None = None) -> ResolvedChannel:
        """Resolve a channel: texture if available, scalar fallback."""
        tex = self.textures.get(channel)
        return ResolvedChannel(
            texture=tex,
            scalar=scalar,
            has_texture=tex is not None,
        )

    # ── Discovery (py-mat's tag-aware layer over client.search) ─

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

        Returns candidates with {source, id, category, score, ...}.
        Pass auto_set=True to set the top match on this Vis.
        """
        from mat_vis_client import search

        results = search(
            category=category,
            roughness=roughness,
            metalness=metallic,
            limit=limit,
        )

        if auto_set and results:
            top = results[0]
            self.source = top["source"]
            self.material_id = top["id"]
            self._textures.clear()
            self._fetched = False

        return results

    # ── Internals ────────────────────────────────────────────────

    def _fetch(self) -> None:
        """Fetch textures via the vis client. Called lazily."""
        if not self.has_mapping:
            return

        # Thin delegate — matches the ADR-0002 principle.
        self._textures = self.client.fetch_all_textures(
            self.source, self.material_id, tier=self.tier
        )
        self._fetched = True

    _PBR_SCALAR_FIELDS: ClassVar[tuple[str, ...]] = (
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
        """Get a PBR scalar with fallback to default."""
        val = getattr(self, field, None)
        if val is not None:
            return val
        if default is not None:
            return default
        return self._PBR_DEFAULTS.get(field)

    # ── TOML loader ──────────────────────────────────────────────

    @classmethod
    def from_toml(cls, vis_data: dict[str, Any]) -> Vis:
        """Construct from a TOML [vis] section.

        3.1 expects finishes as inline tables {source="...", id="..."}.
        Bare-string values like "source/id" raise on load.
        """
        finishes_raw = vis_data.get("finishes", {})
        finishes: dict[str, dict[str, str]] = {}
        for name, entry in finishes_raw.items():
            if isinstance(entry, str):
                raise ValueError(
                    f"Finish '{name}' uses the 3.0 slashed-string form "
                    f"({entry!r}); 3.1 expects inline tables like "
                    f'{{ source = "ambientcg", id = "Metal012" }}. '
                    f"Run `python scripts/migrate_toml_finishes.py` or see "
                    f"docs/migration/v2-to-v3.md."
                )
            if not isinstance(entry, dict) or "source" not in entry or "id" not in entry:
                raise ValueError(
                    f"Finish '{name}' is malformed. Expected an inline table "
                    f'with keys `source` and `id`, got: {entry!r}'
                )
            finishes[name] = {"source": entry["source"], "id": entry["id"]}

        default_finish = vis_data.get("default")

        source: str | None = None
        material_id: str | None = None
        finish: str | None = None
        if default_finish and default_finish in finishes:
            picked = finishes[default_finish]
            source, material_id = picked["source"], picked["id"]
            finish = default_finish
        elif finishes:
            finish = next(iter(finishes))
            picked = finishes[finish]
            source, material_id = picked["source"], picked["id"]

        scalars = {}
        for fname in cls._PBR_SCALAR_FIELDS:
            if fname in vis_data:
                val = vis_data[fname]
                if isinstance(val, list):
                    val = tuple(val)
                scalars[fname] = val

        return cls(
            source=source,
            material_id=material_id,
            finishes=finishes,
            _finish=finish,
            **scalars,
        )
