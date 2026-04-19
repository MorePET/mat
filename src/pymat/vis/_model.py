"""
Vis model — the visual representation attached to a Material.

Material.vis returns a Vis instance. It holds:

- source + material_id + tier — identity triple matching mat-vis-client's
  ``(source, material_id, tier)`` signature. See ADR-0002.
- finishes — dict of finish_name → {"source": ..., "id": ...}.
- PBR scalars (roughness, metallic, base_color, ior, transmission, ...).

Per ADR-0002, Vis holds identity + scalars only. Anything reachable on
the mat-vis-client is exposed directly via thin delegation sugar, not
wrappers:

- ``material.vis.client`` — the shared MatVisClient (escape hatch)
- ``material.vis.mtlx`` — MtlxSource (pre-filled delegate for ``client.mtlx``)
- ``material.vis.textures`` / ``.channels`` / ``.materialize(...)`` — same

The ``pymat.vis.to_threejs(material)``, ``to_gltf(...)``, and
``export_mtlx(...)`` adapters are the main handoff into external
renderers — re-exported from ``pymat.vis`` for discoverability.

Thread safety
-------------

``Vis`` instances are NOT safe to mutate concurrently. The lazy texture
cache (``_textures`` / ``_fetched``) is populated by a single ``_fetch``
call guarded only by the ``_fetched`` flag — two threads racing on
``.textures`` will each trigger a fetch. The shared ``MatVisClient`` is
safe for concurrent *reads* of its manifest / index cache; concurrent
``prefetch`` / ``cache_prune`` calls are not.

If you need thread-safe access, wrap ``Vis`` reads in a lock or
pre-populate the cache from a single thread before handing the Material
to workers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, TypedDict

if TYPE_CHECKING:
    from mat_vis_client import MatVisClient, MtlxSource


class FinishEntry(TypedDict):
    """A single entry in the ``Vis.finishes`` map.

    Mirrors mat-vis-client's ``(source, material_id)`` positional args —
    see ADR-0002 for the rationale for carrying identity as two fields
    rather than a single slashed string.
    """

    source: str
    id: str


# Identity fields whose mutation invalidates the lazy texture cache.
# Kept as a module-level constant so `__setattr__` can check membership
# in O(1) without re-allocating a set each call.
_IDENTITY_FIELDS = frozenset({"source", "material_id", "tier"})

# Sentinel for the no-op short-circuit in __setattr__ — distinguishes
# "attribute not present yet" from "attribute is None" when comparing
# the old value against the incoming one.
_SENTINEL: Any = object()


@dataclass
class ResolvedChannel:
    """Result of resolving a channel across texture + scalar sources.

    ``has_texture`` is derived from ``texture`` so the two can never
    disagree — construct with just ``texture=`` and/or ``scalar=``.
    """

    texture: bytes | None = None  # PNG bytes if texture map available
    scalar: float | None = None  # scalar fallback (e.g. the vis.roughness value)

    @property
    def has_texture(self) -> bool:
        return self.texture is not None


@dataclass
class Vis:
    """Visual representation of a material, backed by mat-vis data.

    Always instantiated (never None on Material). Starts with
    ``source=None`` and empty textures for custom materials.
    Populated from TOML ``[vis]`` section for registered materials.

    Identity::

        steel.vis.source           # "ambientcg"
        steel.vis.material_id      # "Metal012"
        steel.vis.tier             # "1k"
        steel.vis.finishes         # {"brushed": {"source": ..., "id": ...}, ...}
        steel.vis.finish = "polished"  # switch appearance

    Material-keyed delegates (ADR-0002)::

        steel.vis.textures["color"]  # {channel: PNG bytes} — lazy-fetched
        steel.vis.channels           # list of channel names
        steel.vis.mtlx.xml()         # MaterialX XML (method since 0.5)
        steel.vis.materialize(out)   # dump PNG files to disk

    External renderers consume the material via ``pymat.vis.to_threejs``::

        import pymat
        d = pymat.vis.to_threejs(steel)   # MeshPhysicalMaterial init dict

    Assigning ``source``, ``material_id``, or ``tier`` invalidates the
    lazy texture cache automatically — the next ``.textures`` access
    will re-fetch for the new identity.
    """

    # Identity — matches mat-vis-client's (source, material_id, tier)
    # positional-arg signature (ADR-0002).
    source: str | None = None
    material_id: str | None = None
    tier: str = "1k"
    finishes: dict[str, FinishEntry] = field(default_factory=dict)

    # PBR scalars — the canonical home in 3.0+. Loaded from the [vis]
    # section of a TOML material, or derived from physics properties
    # (ior from optical.refractive_index, transmission from optical
    # .transparency / 100) in Material.__post_init__.
    roughness: float | None = None
    metallic: float | None = None
    base_color: tuple[float, float, float, float] | None = None
    ior: float | None = None
    transmission: float | None = None
    clearcoat: float | None = None
    emissive: tuple[float, float, float] | None = None

    # Internal state — excluded from equality + repr so two Vis objects
    # with the same identity + scalars compare equal regardless of
    # whether one has been lazy-fetched.
    _finish: str | None = field(default=None, compare=False, repr=False)
    _textures: dict[str, bytes] = field(default_factory=dict, compare=False, repr=False)
    _fetched: bool = field(default=False, compare=False, repr=False)

    def __post_init__(self) -> None:
        """Start every newly-constructed Vis with an empty cache.

        ``@dataclass`` init and ``dataclasses.replace(vis, ...)`` both
        assign every field including ``_textures`` / ``_fetched``. For
        ``replace(v, source="new")`` that means a new identity paired
        with stale cache bytes from the old identity — the same
        invalidation hazard ``__setattr__`` fixes for plain mutation.

        We zero here rather than fighting it in ``replace`` because:

        - Direct construction ``Vis(source="x", material_id="y")``
          already starts unfetched (no user ever passes cache via
          kwargs; tests populate after construction).
        - Pickling uses ``__dict__.update``, NOT ``__init__``, so
          ``pickle.loads(vis)`` preserves cache state by design.

        The only observable change: ``replace`` now starts unfetched.
        """
        super().__setattr__("_textures", {})
        super().__setattr__("_fetched", False)

    # ── Cache invalidation on identity mutation ──────────────────

    def __setattr__(self, name: str, value: Any) -> None:
        """Write-through to dataclass fields, clearing the lazy texture
        cache when identity changes to a *new* value.

        Assigning ``source``, ``material_id``, or ``tier`` after a fetch
        has populated ``_textures`` invalidates the cache — the next
        ``.textures`` access re-fetches for the new identity. Without
        this, assigning ``vis.tier = "2k"`` silently leaves the 1k
        bytes in ``_textures``.

        Short-circuit: a no-op assignment (new value equals current
        value) skips the invalidation. Otherwise ``vis.source = vis
        .source`` and ``vis.finish = vis.finish`` silently bust the
        cache for no reason.

        The ``"_fetched" in self.__dict__`` guard tolerates the
        dataclass-generated ``__init__`` where ``source`` is assigned
        before ``_textures`` / ``_fetched`` exist.
        """
        if name in _IDENTITY_FIELDS and "_fetched" in self.__dict__:
            # Compare before the write so we can detect a no-op.
            if getattr(self, name, _SENTINEL) == value:
                return
            super().__setattr__(name, value)
            # Invalidate via super() to avoid infinite recursion into
            # this same __setattr__ handler.
            super().__setattr__("_textures", {})
            super().__setattr__("_fetched", False)
            return
        super().__setattr__(name, value)

    # ── Identity helpers ─────────────────────────────────────────

    @property
    def has_mapping(self) -> bool:
        """True when this Vis points at a concrete mat-vis appearance.

        Requires all three identity components to be set —
        ``(source, material_id, tier)``. An explicit ``vis.tier = None``
        un-maps the Vis even if source + material_id are still populated,
        to match what the downstream client expects when we delegate.
        """
        return self.source is not None and self.material_id is not None and self.tier is not None

    @property
    def source_id(self) -> str | None:
        """Read-only convenience accessor: ``"{source}/{material_id}"``.

        Not deprecated — kept because the joined form is a useful lossless
        logging / identifier shape (mirrors Docker image refs). The
        **setter** raises because the identity is two fields in 3.1+;
        assign ``source`` and ``material_id`` directly, or switch via
        the ``finish`` setter. See docs/migration/v2-to-v3.md.
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
        """Switch to a named finish.

        Assigning ``source`` + ``material_id`` via the finish map
        triggers the usual identity-change invalidation, clearing any
        cached textures from the previous finish.
        """
        if name not in self.finishes:
            available = list(self.finishes.keys())
            raise ValueError(f"Unknown finish '{name}'. Available: {available}")
        entry = self.finishes[name]
        # Set identity first — __setattr__ clears the cache — then the
        # finish label. Order matters: _finish is not an identity field,
        # so setting it doesn't itself invalidate.
        self.source = entry["source"]
        self.material_id = entry["id"]
        self._finish = name

    # ── mat-vis-client: exposed, not wrapped (ADR-0002) ─────────

    def _identity_args(self) -> tuple[str, str, str]:
        """Return ``(source, material_id, tier)`` — the positional arg
        triple every mat-vis-client method takes.

        Callers are responsible for gating on ``has_mapping`` first;
        this helper doesn't check, so that delegates can surface a
        useful error from the client itself when identity is missing
        rather than silently returning a null.

        The helper exists so new delegation sugar doesn't drift across
        positional-vs-keyword call shapes — change the delegate target
        in one place and every sugar property follows.
        """
        return (self.source, self.material_id, self.tier)

    def set_identity(
        self,
        *,
        source: str | None = None,
        material_id: str | None = None,
        tier: str | None = None,
    ) -> None:
        """Update any subset of ``(source, material_id, tier)`` atomically.

        Consolidates multi-field identity updates into a single cache
        invalidation. Regular attribute assignment via ``__setattr__``
        would clear ``_textures`` + ``_fetched`` once per field — fine
        functionally (end state is correct) but wasteful and gives
        consumers a window where only one field has been updated.

        Used by ``Material(vis={"source": ..., "material_id": ...})``
        constructor path (core.py) so the Material is never observed
        in a half-assigned identity state.

        Pass ``None`` to leave a field unchanged. Pass an explicit
        value to update it — even if that value equals the current
        one, the no-op short-circuit in ``__setattr__`` handles it.
        """
        # Write directly via super() to avoid the per-field invalidation.
        # We'll clear the cache at the end, once, if anything changed.
        changed = False
        if source is not None and source != self.source:
            super().__setattr__("source", source)
            changed = True
        if material_id is not None and material_id != self.material_id:
            super().__setattr__("material_id", material_id)
            changed = True
        if tier is not None and tier != self.tier:
            super().__setattr__("tier", tier)
            changed = True
        if changed:
            super().__setattr__("_textures", {})
            super().__setattr__("_fetched", False)

    @property
    def client(self) -> MatVisClient:
        """The shared ``mat-vis-client`` singleton.

        Escape hatch for mat-vis-client methods not keyed by a material
        — tier enumeration, cache management, discovery before a
        material is picked. Material-keyed operations should prefer the
        dotted sugar on this Vis (``.textures``, ``.mtlx``,
        ``.channels``, ``.materialize``).

        **Note:** if you don't have a Material yet,
        ``pymat.vis.client()`` is the same singleton reached via a
        module-level function. Same object; different entry points so
        callers without a Material don't have to construct one to
        reach the client.
        """
        from pymat.vis import _shared_client

        return _shared_client()

    @property
    def mtlx(self) -> MtlxSource | None:
        """MaterialX document accessor — lazy, no network IO until used.

        Returns ``None`` if this Vis has no mapping::

            xml = material.vis.mtlx.xml()         # method call — triggers fetch
            material.vis.mtlx.export("./out")
            material.vis.mtlx.original            # upstream-author variant, or None

        Thin delegate for ``client.mtlx(source, material_id, tier=tier)``.

        Each access constructs a fresh ``MtlxSource`` — the object itself
        is cheap (no IO at construction); only ``.xml`` / ``.export(...)``
        hit the network.
        """
        if not self.has_mapping:
            return None
        src, mid, tier = self._identity_args()
        return self.client.mtlx(src, mid, tier=tier)

    # ── Textures + channels ──────────────────────────────────────

    @property
    def textures(self) -> dict[str, bytes]:
        """Channel → PNG bytes for this material at this tier.

        **Blocking**: first access triggers an HTTP fetch via the shared
        ``MatVisClient`` (range reads against the mat-vis release
        asset). Subsequent accesses read from the per-instance cache
        until identity changes.

        Returns empty dict if no mapping is set.
        """
        if not self.has_mapping:
            return {}

        if not self._fetched:
            self._fetch()

        return self._textures

    @property
    def channels(self) -> list[str]:
        """Available texture channel names for this material at this tier.

        **Blocking** on first access per source × tier (rowmap fetch);
        subsequent accesses hit the shared ``MatVisClient``'s in-memory
        rowmap cache — cheap, not cached on this ``Vis`` instance.
        (Unlike ``.textures``, which DOES cache per-instance because
        the payload is large PNG bytes, not a small list of strings.)
        """
        if not self.has_mapping:
            return []
        return self.client.channels(*self._identity_args())

    def materialize(self, output_dir: str | Path) -> Path | None:
        """Write a PNG for every channel to a directory. Returns the directory.

        Thin delegate for ``client.materialize(source, material_id, tier, out)``.
        Returns ``None`` if this Vis has no mapping.
        """
        if not self.has_mapping:
            return None
        return self.client.materialize(*self._identity_args(), output_dir)

    def resolve(self, channel: str, scalar: float | None = None) -> ResolvedChannel:
        """Resolve a channel: texture if available, scalar fallback."""
        tex = self.textures.get(channel)
        return ResolvedChannel(texture=tex, scalar=scalar)

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

        Returns candidates with ``{source, id, category, score, ...}``.
        Pass ``auto_set=True`` to set the top match on this Vis.
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
            # Assigning source + material_id triggers __setattr__ → cache clear
            self.source = top["source"]
            self.material_id = top["id"]

        return results

    # ── Internals ────────────────────────────────────────────────

    def _fetch(self) -> None:
        """Fetch textures via the vis client. Called lazily."""
        if not self.has_mapping:
            return

        # Thin delegate — matches the ADR-0002 principle.
        src, mid, tier = self._identity_args()
        textures = self.client.fetch_all_textures(src, mid, tier=tier)
        # Write via super() so we don't trip the identity-invalidation
        # guard (`_textures` and `_fetched` aren't identity fields, so
        # direct assignment would work too; using super() documents that
        # we're explicitly bypassing the cache-invalidation side effect).
        super().__setattr__("_textures", textures)
        super().__setattr__("_fetched", True)

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

    def get(self, name: str, default: Any = None) -> Any:
        """Get a PBR scalar with fallback to default.

        Parameter is ``name`` rather than ``field`` to avoid shadowing
        ``dataclasses.field`` imported at module scope — any future
        refactor that reaches for ``field(...)`` inside this method
        would otherwise silently grab the parameter instead.
        """
        val = getattr(self, name, None)
        if val is not None:
            return val
        if default is not None:
            return default
        return self._PBR_DEFAULTS.get(name)

    # ── TOML loader ──────────────────────────────────────────────

    @classmethod
    def from_toml(cls, vis_data: dict[str, Any]) -> Vis:
        """Construct from a TOML ``[vis]`` section.

        3.1 expects finishes as inline tables ``{source="...", id="..."}``.
        Bare-string values like ``"source/id"`` raise on load.
        """
        finishes_raw = vis_data.get("finishes", {})
        finishes: dict[str, FinishEntry] = {}
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
                    f"with keys `source` and `id`, got: {entry!r}"
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
