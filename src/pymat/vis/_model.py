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
    # ``Unpack`` is in stdlib ``typing`` from 3.11; pull from
    # ``typing_extensions`` (transitive dep, always available in
    # type-check contexts) so 3.10 type-checking also works.
    from mat_vis_client import MatVisClient, MtlxSource
    from typing_extensions import Unpack


class FinishEntry(TypedDict):
    """A single entry in the ``Vis.finishes`` map.

    Mirrors mat-vis-client's ``(source, material_id)`` positional args —
    see ADR-0002 for the rationale for carrying identity as two fields
    rather than a single slashed string.
    """

    source: str
    id: str


class VisDeltas(TypedDict, total=False):
    """Typed kwargs accepted by :meth:`Vis.override`.

    Used by static type checkers (pyright, mypy) via ``Unpack`` per PEP
    692. Surfaces every valid override key as IDE completion and flags
    typos like ``roughnes=`` at edit time, not runtime.

    All keys are optional (``total=False``) — that's the override
    contract. To "leave a field unchanged", *omit* the key. Runtime
    validation of unknown kwargs lives in :meth:`Vis.override`; this
    TypedDict is purely a typing layer and has no runtime effect.

    Identity fields (``source``, ``material_id``, ``tier``) are typed
    as bare ``str`` here even though the underlying ``Vis`` field is
    ``str | None``. Reason: ``override`` routes identity through
    :meth:`Vis.set_identity`, which interprets ``None`` as "leave
    unchanged" rather than "clear" — so passing ``None`` would silently
    no-op. Typing the kwarg as ``str`` enforces the kwargs idiom (omit
    to leave alone) and keeps the type-checker contract honest.

    Scalar fields (``roughness``, ``metallic``, …) keep the ``| None``
    union — ``None`` is a legitimate reset value there (passes through
    ``setattr`` directly).

    The ``finish`` key is a sugar — not a Vis field but a property
    setter that looks up in the ``finishes`` map and reassigns
    identity. Treated separately by ``override``'s body.
    """

    source: str
    material_id: str
    tier: str
    finishes: dict[str, FinishEntry]
    roughness: float | None
    metallic: float | None
    base_color: tuple[float, float, float, float] | None
    ior: float | None
    transmission: float | None
    clearcoat: float | None
    emissive: tuple[float, float, float] | None
    finish: str  # sugar — looks up in finishes map, reassigns identity


# Identity fields whose mutation invalidates the lazy texture cache.
# Kept as a module-level constant so `__setattr__` can check membership
# in O(1) without re-allocating a set each call.
_IDENTITY_FIELDS = frozenset({"source", "material_id", "tier"})

# Sentinel for the no-op short-circuit in __setattr__ — distinguishes
# "attribute not present yet" from "attribute is None" when comparing
# the old value against the incoming one.
_SENTINEL: Any = object()


def _rgba_to_hex(rgba: list[float] | tuple[float, ...] | None) -> str | None:
    """Convert [r, g, b, a?] in 0-1 range to '#RRGGBB'. Alpha dropped."""
    if rgba is None:
        return None
    r, g, b = (int(round(max(0.0, min(1.0, c)) * 255)) for c in rgba[:3])
    return f"#{r:02x}{g:02x}{b:02x}"


def _validate_tier(value: str | None) -> None:
    """Reject an obviously-bogus ``tier`` assignment with a clear message.

    Mirrors the ``Vis.finish=`` setter (which raises ``ValueError`` with
    the available finish list). Without this, ``vis.tier = "99k"``
    silently succeeds and the failure surfaces deep inside
    mat-vis-client on first ``.textures`` access — the consumer never
    sees the offending input echoed back. Closes the gap pinned by
    ``tests/test_error_messages.py::TestVisTierUnknown`` and
    ``tests/test_consumer_journey.py::TestErrorJourney::
    test_unknown_tier_raises_at_assignment`` (both consumer-flagged
    via [mat-vis #280](https://github.com/MorePET/mat-vis/issues/280)
    territory — error messages that fire in the wrong layer / without
    user-given input echoed).

    Validation policy:

    - ``None`` is allowed — un-mapping a Vis is a documented operation.
    - The set of valid tiers comes from ``client.tiers()`` (reads the
      cached mat-vis manifest; no network call after the first fetch).
    - If the client / manifest is unreachable (offline, corrupted
      cache, future-version migration), validation is skipped silently
      rather than blocking the assignment. Worse to break offline
      workflows than to leave a typo unflagged — the lazy-fetch path
      will still raise on the eventual ``.textures`` access, just
      without the at-assignment-site echo this helper provides.
    """
    if value is None:
        return
    try:
        from mat_vis_client import get_client

        valid = get_client().tiers()
    except Exception:
        # Permissive fallback — see policy in docstring above.
        return
    if value not in valid:
        raise ValueError(
            f"Unknown tier {value!r}. Available: {sorted(valid)}. "
            "Set vis.tier = None to un-map, or pick one of the listed tiers."
        )


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

    Material-keyed delegates (ADR-0002)::

        steel.vis.textures["color"]  # {channel: PNG bytes} — lazy-fetched
        steel.vis.channels           # list of channel names
        steel.vis.mtlx.xml()         # MaterialX XML (method since 0.5)
        steel.vis.materialize(out)   # dump PNG files to disk

    External renderers consume the material via ``pymat.vis.to_threejs``::

        import pymat
        d = pymat.vis.to_threejs(steel)   # MeshPhysicalMaterial init dict

    **Don't mutate the Vis on a registry Material.** Materials reached
    via ``pymat["..."]`` or category imports (``from pymat import
    stainless``) are *shared instances* — the same object every caller
    in the process sees. Writing ``steel.vis.finish = "polished"`` on
    one of those leaks into every other consumer.

    The safe path: derive an independent copy via :meth:`override`,
    attach it to a fresh Material via :meth:`Material.with_vis`::

        polished_vis = steel.vis.override(finish="polished", roughness=0.05)
        steel_polished = steel.with_vis(polished_vis)

    Materials *you* construct directly (``Material(name="custom",
    vis={...})``) are not shared and can be mutated freely.

    Assigning ``source``, ``material_id``, or ``tier`` invalidates the
    lazy texture cache automatically — the next ``.textures`` access
    will re-fetch for the new identity.
    """

    # Identity — matches mat-vis-client's (source, material_id, tier)
    # positional-arg signature (ADR-0002).
    source: str | None = None
    material_id: str | None = None
    tier: str | None = "1k"
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
        self._auto_resolve_tier_from_manifest()

    def _auto_resolve_tier_from_manifest(self) -> None:
        """Reconcile ``tier`` against the source's manifest tier list.

        The dataclass default of ``"1k"`` matches the textured-source
        majority (gpuopen / ambientcg / polyhaven) but is wrong for
        scalar-only sources like ``physicallybased`` which only ship
        a ``"scalar"`` tier. Without this resolution, the call
        ``Vis(source="physicallybased", material_id="Aluminum")`` lands
        with ``tier="1k"`` and the next ``.textures`` access raises
        ``MaterialNotStagedError`` deep inside mat-vis-client without
        the user ever asking for ``"1k"``. Closes #222 / mat-vis #313.

        Resolution policy:

        - If source / material_id aren't both set: skip (incomplete identity).
        - If the configured ``tier`` IS in the source's manifest tier list:
          keep it (user's choice respected).
        - Else if a single canonical fallback exists (currently ``"scalar"``
          for sources whose tier list contains it): silently swap to it.
        - Else: leave ``tier`` alone — fetch will raise with the offending
          input echoed (better than guessing wrong).

        Permissive on errors: if the client / manifest is unreachable
        (offline, corrupted cache, future-version migration), skip — same
        policy as ``_validate_tier``. Worse to break offline workflows than
        to leave a tier mismatch unresolved; the lazy-fetch path will still
        surface the issue at ``.textures`` access time.
        """
        if self.source is None or self.material_id is None:
            return
        try:
            from mat_vis_client import get_client

            manifest = get_client().manifest
        except Exception:
            return

        source_entry = (manifest.get("sources") or {}).get(self.source)
        if not source_entry:
            return  # Unknown source — let fetch surface the error
        available_tiers = list((source_entry.get("tiers") or {}).keys())
        if not available_tiers:
            return
        if self.tier in available_tiers:
            return  # User's tier choice is valid for this source
        # Tier mismatch — fall back to a canonical option if there's a
        # clear winner. ``"scalar"`` is the canonical scalar-only tier;
        # if it's the only one available, use it. Otherwise, leave
        # alone (better an explicit error at fetch than a silent guess).
        if "scalar" in available_tiers:
            super().__setattr__("tier", "scalar")

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
            # Validate user-supplied tier values at the assignment site so
            # the offending input is echoed back to the caller (rather than
            # surfacing deep inside mat-vis-client on the next fetch).
            # Source / material_id stay free-form — the universe of valid
            # values there is open-ended (gpuopen names, ambientcg ids,
            # future sources) and any check here would lag the upstream
            # catalog. Tier is a closed set per the mat-vis manifest, so
            # validation pays its way.
            if name == "tier":
                _validate_tier(value)
            super().__setattr__(name, value)
            # Invalidate via super() to avoid infinite recursion into
            # this same __setattr__ handler.
            super().__setattr__("_textures", {})
            super().__setattr__("_fetched", False)
            return
        super().__setattr__(name, value)

    # ── Repr (mat#221: surface lazy state without touching field semantics) ─

    def __repr__(self) -> str:
        """Custom ``__repr__`` overlaying lazy/fetched state on top of
        the dataclass field summary.

        The dataclass-generated repr correctly shows caller-supplied
        fields (identity + override channels: ``roughness``,
        ``metallic``, ``base_color``, ...). What it can't show is
        whether a fetch has happened or what the catalog returned —
        Bernhard's mat#221 surprise that "all fields are None even
        though ``to_threejs()`` succeeded."

        This repr keeps the field section verbatim (so explicit
        overrides stay observable as ``metallic=0.7``) and appends:

        - ``fetched=True/False`` — texture fetch state
        - ``scalars=`` — sparse catalog + override view (only when
          fetched, to avoid index IO during repr)
        - ``available_textures=`` — channel keys actually staged

        Field semantics are unchanged: dataclass slots remain the
        override channel; resolved values surface via :attr:`scalars`.
        Two namespaces, two purposes — the repr just makes both
        legible at a glance.
        """
        from dataclasses import fields as _fields

        # Field section — same as the auto-repr would produce, honoring
        # ``field(repr=False)`` on private cache slots.
        field_parts = [f"{f.name}={getattr(self, f.name)!r}" for f in _fields(self) if f.repr]

        # Lazy-state suffix — cheap when unfetched (just the flag);
        # touches ``self.scalars`` (catalog dict lookup, no HTTP) only
        # post-fetch when the index is already hot.
        suffix = [f"fetched={self._fetched}"]
        if self._fetched:
            scalars = self.scalars
            if scalars:
                suffix.append(f"scalars={scalars!r}")
            if self._textures:
                suffix.append(f"available_textures={sorted(self._textures)!r}")

        return f"{type(self).__name__}({', '.join(field_parts + suffix)})"

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
        # Tier is validated up-front (parallel to __setattr__) so callers
        # going through ``set_identity`` get the same at-assignment-site
        # echo on a bogus tier as direct ``vis.tier = ...`` assignment.
        changed = False
        if source is not None and source != self.source:
            super().__setattr__("source", source)
            changed = True
        if material_id is not None and material_id != self.material_id:
            super().__setattr__("material_id", material_id)
            changed = True
        if tier is not None and tier != self.tier:
            _validate_tier(tier)
            super().__setattr__("tier", tier)
            changed = True
        if changed:
            super().__setattr__("_textures", {})
            super().__setattr__("_fetched", False)

    def override(self, **deltas: "Unpack[VisDeltas]") -> Vis:  # noqa: F821 — TYPE_CHECKING only
        """Return a new ``Vis`` with the given deltas applied; ``self``
        is unchanged.

        Use this when deriving a tweaked variant from a base Vis —
        typically the registry instance returned by ``pymat["..."]``.
        The registry instance is shared across all callers, so direct
        mutation corrupts every other consumer of the same material::

            steel = pymat["Stainless Steel 304"]
            polished = steel.vis.override(roughness=0.3, finish="polished")
            # steel.vis is unchanged; polished is independent.

        For helper functions that build delta dicts at runtime, type
        them as :class:`VisDeltas` (importable from ``pymat.vis``) —
        IDE completion + mypy strict-mode static checks come for free.

        Note: ``override`` is the runtime mirror of TOML grade override
        (children inherit parent properties unless overridden). It is
        NOT a flat field substitution like ``dataclasses.replace`` —
        the ``finishes`` map is deep-copied (including caller-supplied
        deltas), ``finish=`` is a special-cased lookup that flips
        identity via the finishes map, and identity changes invalidate
        the texture cache atomically.

        Identity deltas (``source`` / ``material_id`` / ``tier``) route
        through :meth:`set_identity` for atomic invalidation. The
        ``_finish`` label is cleared only when ``source`` or
        ``material_id`` change without an explicit ``finish=`` —
        finishes pin (source, material_id), not tier, so a tier-only
        change preserves the finish label.

        ``finish=`` runs LAST against the new (deep-copied) finishes
        map, so ``override(finishes={...}, finish="x")`` resolves
        ``x`` in the replaced map.

        Unknown kwargs raise ``TypeError`` — catches typos like
        ``roughnes=0.5`` that ``dataclasses.replace`` would accept
        silently.
        """
        from copy import deepcopy
        from dataclasses import fields

        # Public dataclass fields (excludes _textures, _fetched, _finish)
        # plus the ``finish`` property — the canonical override surface.
        valid_fields = {f.name for f in fields(self) if not f.name.startswith("_")}
        valid_keys = valid_fields | {"finish"}
        unknown = set(deltas) - valid_keys
        if unknown:
            raise TypeError(
                f"Vis.override() got unexpected kwargs: {sorted(unknown)}. "
                f"Valid keys: {sorted(valid_keys)}"
            )

        new = deepcopy(self)

        # ``finish`` is a property setter (not a field) and must be
        # applied LAST so it resolves against the new instance's
        # (deep-copied) finishes map.
        finish_delta = deltas.pop("finish", None)

        # Identity-pair updates: route through set_identity for atomic
        # cache invalidation. Compute "finish-invalidating change" from
        # ``source``/``material_id`` only — tier doesn't pin which
        # finish entry is selected (#103). Computed before set_identity
        # writes so a no-op (same value) doesn't trigger the clear.
        identity_keys = _IDENTITY_FIELDS & deltas.keys()
        finish_invalidating_keys = identity_keys & {"source", "material_id"}
        finish_invalidating = any(deltas[k] != getattr(new, k) for k in finish_invalidating_keys)
        if identity_keys:
            # Pop identity values explicitly so each kwarg keeps its
            # declared type (the comprehension form widens to ``object``
            # because the TypedDict has heterogeneous field types).
            id_kwargs: dict[str, Any] = {k: deltas.pop(k) for k in list(identity_keys)}
            new.set_identity(**id_kwargs)

        for k, v in deltas.items():
            # Caller-supplied ``finishes=`` must be deep-copied — storing
            # by reference breaks the docstring promise and diverges from
            # ``merge_from_toml`` semantics (#104).
            if k == "finishes":
                v = deepcopy(v)
            setattr(new, k, v)

        # Identity moved (source/material_id) without an explicit
        # finish= → the inherited _finish label is now stale.
        if finish_invalidating and finish_delta is None:
            object.__setattr__(new, "_finish", None)

        if finish_delta is not None:
            new.finish = finish_delta

        return new

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

    # ── Scalars + render adapters ───────────────────────────────
    #
    # Two states ``Vis`` can be in for rendering: (a) identity → catalog
    # scalars from mat-vis VisAsset, with caller overrides on top; (b)
    # no identity → caller fields with ``_PBR_DEFAULTS`` fallback so
    # the dumb adapter has a complete dict to emit.
    #
    # Public ``Vis.scalars`` is sparse — only authored / explicitly-set
    # keys, no defaults. ``_render_scalars()`` adds the defaults
    # fallback for the no-identity render path; ``Vis.textures``
    # already returns ``{}`` for no-identity, so render adapters call
    # it directly.

    def _catalog_scalars(self) -> dict[str, Any]:
        """Catalog-authored PBR scalars from mat-vis. ADR-0002 Principle 3
        thin delegate.

        Preferred path: ``client.asset(source, material_id, tier).scalars``
        (mat-vis-client 0.7+ / mat-vis #93). Falls back to the legacy
        ``client._scalars_for(source, material_id)`` for 0.6.x. Both
        return the same shape; ``asset(...).scalars`` is the public
        contract going forward.

        Returns ``{}`` for no-identity Vis or when the client lacks
        both surfaces (e.g. test mocks that only stub ``fetch_all_textures``).
        Lazy / no HTTP fetch — the catalog index is loaded once.
        """
        if not self.has_mapping:
            return {}
        client = self.client
        if hasattr(client, "asset"):
            try:
                return client.asset(*self._identity_args()).scalars
            except AttributeError:
                pass  # asset() exists but returned object lacks .scalars (test mocks)
        if hasattr(client, "_scalars_for"):
            return client._scalars_for(self.source, self.material_id)
        return {}

    def _explicit_scalars(self) -> dict[str, Any]:
        """Caller-supplied PBR overrides only — None fields dropped.

        Maps pymat field names to mat-vis adapter keys (``metallic`` →
        ``metalness``, ``base_color`` RGBA → ``color_hex`` string).
        Layered on top of catalog scalars so ``vis.metallic = 0.7``
        wins over the authored catalog value.
        """
        out: dict[str, Any] = {}
        if self.metallic is not None:
            out["metalness"] = self.metallic
        if self.roughness is not None:
            out["roughness"] = self.roughness
        if self.base_color is not None:
            out["color_hex"] = _rgba_to_hex(self.base_color)
        if self.ior is not None:
            out["ior"] = self.ior
        if self.transmission is not None:
            out["transmission"] = self.transmission
        if self.clearcoat is not None:
            out["clearcoat"] = self.clearcoat
        if self.emissive is not None:
            out["emissive"] = self.emissive
        return out

    def _scalars_with_defaults(self) -> dict[str, Any]:
        """Caller-overrides with ``_PBR_DEFAULTS`` fallback — for the
        no-identity render path where there's no catalog to read.
        Preserves the historical "all-defaults grey plastic" shape
        for TOML-only / chemistry-only materials.
        """
        return {
            "metalness": self.get("metallic"),
            "roughness": self.get("roughness"),
            "color_hex": _rgba_to_hex(self.get("base_color")),
            "ior": self.get("ior"),
            "transmission": self.get("transmission"),
            "clearcoat": self.get("clearcoat"),
            "emissive": self.get("emissive"),
        }

    @property
    def scalars(self) -> dict[str, Any]:
        """PBR scalars dict in mat-vis adapter schema. Sparse: only
        keys with authored / explicit values; no defaults fallback
        (use ``to_threejs()`` for the all-defaults render shape).

        For a Vis with mat-vis identity: catalog-authored values from
        the source's ``mat_vis.pbr.*`` block, with explicit caller
        overrides merged on top. For a Vis without identity: only the
        caller's explicit overrides (``{}`` if none).

        Lazy: the has_mapping case touches ``VisAsset.scalars`` which
        is itself lazy + cached. Reading ``.scalars`` does NOT trigger
        a texture HTTP fetch.

        Closes mat#220.
        """
        return {**self._catalog_scalars(), **self._explicit_scalars()}

    def _render_scalars(self) -> dict[str, Any]:
        """Scalars dict for render adapters: defaults overlaid by
        catalog overlaid by explicit caller overrides. Always returns
        the full 7-key shape so the dumb mat-vis adapter has something
        complete to emit — sparse output would leave Three.js falling
        through to *its* defaults (which may differ from ours).

        Layering: ``_PBR_DEFAULTS`` < catalog < explicit overrides.
        ``Vis.scalars`` (the public sparse view) drops the defaults;
        only render adapters need the floor.
        """
        return {
            **self._scalars_with_defaults(),
            **self._catalog_scalars(),
            **self._explicit_scalars(),
        }

    def to_threejs(self) -> dict[str, Any]:
        """Three.js ``MeshPhysicalMaterial`` parameter dict.

        Dispatches via :meth:`_render_scalars` — catalog scalars +
        caller overrides for identity-bearing Vis, caller fields +
        ``_PBR_DEFAULTS`` otherwise. Color format, scalar
        normalization, and texture encoding all live in mat-vis-client.
        """
        from mat_vis_client.adapters import to_threejs as _adapter

        return _adapter(self._render_scalars(), self.textures)

    def to_gltf(self, *, name: str | None = None) -> dict[str, Any]:
        """glTF 2.0 material dict. ``name=`` populates the node's
        ``name`` field (left empty when unset on a standalone Vis;
        the module-level ``pymat.vis.to_gltf(material)`` form fills
        it from ``material.name`` automatically).
        """
        from mat_vis_client.adapters import to_gltf as _adapter

        result = _adapter(self._render_scalars(), self.textures)
        result["name"] = name if name is not None else ""
        return result

    def export_mtlx(self, output_dir: str | Path, *, name: str | None = None) -> Path:
        """Export as a MaterialX .mtlx file + PNG textures on disk.
        ``name=`` sets the filename stem; defaults to ``"material"``.
        """
        from mat_vis_client.adapters import export_mtlx as _adapter

        mat_name = name if name is not None else "material"
        safe_name = mat_name.replace(" ", "_").replace("/", "_") or "material"
        return _adapter(
            self._render_scalars(),
            self.textures,
            Path(output_dir),
            material_name=safe_name,
        )

    # ── Browse / candidates (mat-vis search() delegate, #230) ───

    def candidates(
        self,
        *,
        category: str | None = None,
        roughness: float | None = None,
        metalness: float | None = None,
        roughness_range: tuple[float, float] | None = None,
        metalness_range: tuple[float, float] | None = None,
        source: str | None = None,
        tier: str = "1k",
        limit: int = 10,
    ) -> list[Any]:
        """Find catalog appearances matching this material's properties.

        Auto-populates the search query from this Vis's own PBR
        scalars when ``roughness=`` / ``metalness=`` aren't supplied.
        Returns ``list[Match]`` (mat-vis #359) — each entry is a
        dict-subclass with ``.ref`` / ``.id`` / ``.source`` / ``.mat_vis``
        attributes plus full dict-key access. Hand to
        :meth:`with_match` to apply, or to ``client.asset(...)`` to
        fetch directly.

        ``vis.candidates()`` does not trigger any HTTP texture fetches
        — search reads the per-source index only.
        """
        from mat_vis_client import search

        return search(
            category=category,
            roughness=roughness if roughness is not None else self.roughness,
            metalness=metalness if metalness is not None else self.metallic,
            roughness_range=roughness_range,
            metalness_range=metalness_range,
            source=source,
            tier=tier,
            limit=limit,
        )

    def with_match(self, match: Any) -> Vis:
        """Return a new ``Vis`` with this Match's identity (source,
        material_id, tier). Original Vis unchanged.

        ``match`` is a Match (mat-vis #359) or any dict-shaped index
        entry with ``source`` / ``id`` keys. ``tier`` is taken from
        ``match["available_tiers"][0]`` when present (preferring
        ``"1k"``); otherwise the calling Vis's current tier carries
        over.

        Immutable companion to :meth:`set_identity`: useful when
        composing from a candidates list without mutating shared
        registry instances::

            picked = steel.with_vis(steel.vis.with_match(matches[0]))
        """
        src = match["source"]
        mid = match["id"]
        tiers = list(match.get("available_tiers") or [])
        if tiers:
            new_tier = "1k" if "1k" in tiers else tiers[0]
        else:
            new_tier = self.tier
        return self.override(source=src, material_id=mid, tier=new_tier)

    def discover(
        self,
        *,
        category: str | None = None,
        roughness: float | None = None,
        metallic: float | None = None,
        limit: int = 5,
        auto_set: bool = False,
    ) -> list[Any]:
        """Search mat-vis for appearances matching this material's scalars.

        .. deprecated:: 3.x
           Use :meth:`candidates` (Match-typed return, auto-derives
           query from this Vis) and :meth:`with_match` for immutable
           assignment from the result. Will be removed in 4.x.
        """
        import warnings

        warnings.warn(
            "Vis.discover() is deprecated; use Vis.candidates() to browse "
            "and Vis.with_match(m) for immutable identity assignment. "
            "discover()'s auto_set= mutation will be removed in 4.x.",
            DeprecationWarning,
            stacklevel=2,
        )
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
        """Fetch textures via the vis client. Called lazily.

        Scalar-only sources (currently ``physicallybased``, identified
        by ``tier == "scalar"``) ship no texture maps — only authored
        PBR scalars in their catalog entry. The ``fetch_all_textures``
        path raises ``MaterialNotStagedError`` for them; we short-
        circuit with an empty texture dict instead. The scalars are
        already on the ``Vis`` (loaded from TOML or set explicitly);
        downstream adapters fall back to ``Vis._PBR_DEFAULTS`` for
        anything still ``None``. Closes #222 / mat-vis #313.
        """
        if not self.has_mapping:
            return

        # Thin delegate — matches the ADR-0002 principle.
        src, mid, tier = self._identity_args()
        if tier == "scalar":
            # No texture fetch for scalar-only sources. Mark fetched so
            # the lazy property doesn't keep re-trying every access.
            super().__setattr__("_textures", {})
            super().__setattr__("_fetched", True)
            return

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
    def merge_from_toml(cls, base: Vis | None, vis_data: dict[str, Any]) -> Vis:
        """Inherit from ``base`` (parent's Vis), then overlay TOML overrides.

        Rules:

        - If ``base`` is None and ``vis_data`` is empty → fresh ``Vis()``.
        - If ``base`` is provided, start with ``deepcopy(base)`` so the child
          inherits identity, finishes, scalars, and the ``_finish`` pick.
        - If ``vis_data`` is provided, overlay its keys on top:
            * ``finishes`` (if set) replaces the inherited map. This is the
              semantically correct call: a grade that declares *any* finishes
              wants its own set, not a concatenation.
            * ``default`` (if set) picks a starting finish from the merged
              map and writes ``source``/``material_id``/``_finish`` from it,
              matching ``from_toml`` behavior.
            * Any PBR scalar in ``vis_data`` overwrites the inherited value.
            * Bare ``source`` / ``material_id`` / ``tier`` keys overwrite
              directly (supports TOML that pins identity without finishes).
        - Cache fields (``_textures``, ``_fetched``) are zeroed by
          ``Vis.__post_init__`` regardless.

        Used by the TOML loader so grades inherit parent vis without needing
        to re-declare identity + scalars. Closes #88.
        """
        from copy import deepcopy

        if base is None:
            return cls.from_toml(vis_data or {})

        merged = deepcopy(base)

        if not vis_data:
            return merged

        if "finishes" in vis_data:
            # Re-route through from_toml just for the finishes validation
            # path — it raises on the 3.0 slashed-string form + malformed
            # entries, and we want to keep that guard.
            finishes_only = {"finishes": vis_data["finishes"]}
            if "default" in vis_data:
                finishes_only["default"] = vis_data["default"]
            fresh = cls.from_toml(finishes_only)
            merged.finishes = fresh.finishes
            # If the TOML picked a new default finish, apply it (which will
            # flip source/material_id/_finish through Vis's setters).
            if fresh._finish is not None:
                object.__setattr__(merged, "_finish", fresh._finish)
                merged.source = fresh.source
                merged.material_id = fresh.material_id

        for field_name in ("source", "material_id", "tier"):
            if field_name in vis_data:
                setattr(merged, field_name, vis_data[field_name])

        for fname in cls._PBR_SCALAR_FIELDS:
            if fname in vis_data:
                val = vis_data[fname]
                if isinstance(val, list):
                    val = tuple(val)
                setattr(merged, fname, val)

        return merged

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
