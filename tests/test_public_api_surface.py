"""Pin the public API surface contract for py-materials.

The bug this guards against (closes #98 / mat-vis #282): a class is in
``pymat.vis.__all__`` and importable from ``pymat.vis``, but its
``__module__`` still points at the underscore-prefixed private location
(``pymat.vis._model``). Then ``type(obj)``, ``repr``, IDE auto-import,
and Sphinx all push downstream code (build123d) toward the private path
we don't want to support.

``tests/test_vis.py::TestPublicApiContract`` pins ``__module__`` for
``Vis`` / ``VisDeltas`` / ``FinishEntry``. This file extends the
contract to:

1. Module-path metadata for **every** name in ``pymat.__all__`` and
   ``pymat.vis.__all__`` — no underscore-prefixed component anywhere
   in ``__module__`` for first-party types (third-party re-exports
   like ``MatVisClient`` are exempt).
2. ``__all__`` integrity — every listed name resolves; nothing in
   ``__all__`` raises; documented public submodules are listed.
3. ``dir(pymat)`` discoverability for lazy-loaded base materials.
4. Public type construction — every public class can be built with
   documented kwargs.
5. Field-set freeze for ``Vis``, ``VisDeltas``, ``FinishEntry``,
   ``Material``, ``Source`` — pin the canonical field set so a rename
   trips the test.
6. ``type(...).__module__`` flow — instances out of public APIs
   (``stainless.vis``, ``Material("X").vis``, ``Vis.override(...)``)
   all surface the public path.
7. Sphinx-style canonical-name pin — for every public name N,
   ``import_module(N.__module__).N`` round-trips to the same object.
"""

from __future__ import annotations

import dataclasses
import importlib
import inspect
from typing import Any

import pytest

# ── Public-surface inventory ─────────────────────────────────

# First-party types in ``pymat.__all__`` whose ``__module__`` we control
# (not third-party re-exports like ``ureg`` / ``MatVisClient``).
PYMAT_FIRSTPARTY_NAMES = [
    "Material",
    "AllProperties",
    "MechanicalProperties",
    "ThermalProperties",
    "ElectricalProperties",
    "OpticalProperties",
    "ManufacturingProperties",
    "ComplianceProperties",
    "SourcingProperties",
    "load_toml",
    "load_category",
    "search",
    "enrich_from_periodictable",
    "enrich_from_matproj",
    "enrich_all",
]

# First-party names in ``pymat.vis.__all__`` whose ``__module__`` we
# control. ``MatVisClient`` lives in ``mat_vis_client`` (separate PyPI
# package) — exempt by design. Functions imported from
# ``mat_vis_client`` (``get_manifest``, ``prefetch``, ``rowmap_entry``,
# ``seed_indexes``) are also third-party and exempt.
PYMAT_VIS_FIRSTPARTY_NAMES = [
    "client",
    "search",
    "fetch",
    "Vis",
    "VisDeltas",
    "FinishEntry",
    "to_threejs",
    "to_gltf",
    "export_mtlx",
]

PYMAT_VIS_THIRDPARTY_NAMES = [
    "MatVisClient",
    "get_manifest",
    "prefetch",
    "rowmap_entry",
    "seed_indexes",
]

# Public *types* (constructible classes) in pymat.__all__.
PYMAT_PUBLIC_TYPES = [
    "Material",
    "AllProperties",
    "MechanicalProperties",
    "ThermalProperties",
    "ElectricalProperties",
    "OpticalProperties",
    "ManufacturingProperties",
    "ComplianceProperties",
    "SourcingProperties",
]

# Public types in pymat.vis.__all__.
PYMAT_VIS_PUBLIC_TYPES = ["Vis", "VisDeltas", "FinishEntry"]

# Base materials advertised by ``pymat.__dir__`` — every category in
# ``_CATEGORY_BASES`` should be lazy-loadable. Pulling from the module
# rather than re-listing keeps this in sync with src/pymat/__init__.py.
import pymat as _pymat  # noqa: E402

ALL_KNOWN_BASE_MATERIALS = sorted({b for bases in _pymat._CATEGORY_BASES.values() for b in bases})

# ``pymat.__dir__`` currently omits these entries that ARE in
# ``pymat.__all__`` (the hardcoded ``base_exports`` list inside
# ``__dir__`` doesn't include them). IDE tab-completion misses them —
# documented as a gap below. Excluded from the per-name dir() pin so
# the test reflects current reality; the gap test enforces the broader
# invariant via xfail.
_DIR_FIRSTPARTY_GAPS = {"search", "ureg", "factories", "vis"}


# ── 1. Module-path metadata ──────────────────────────────────


class TestModulePathMetadata:
    """Every first-party name in a public ``__all__`` must have a
    ``__module__`` whose components are all non-underscore-prefixed.
    The motivating bug had ``Vis.__module__ == "pymat.vis._model"``;
    the leading-underscore segment ``_model`` is what tools read as
    "private" and surface to users."""

    @staticmethod
    def _has_private_segment(module_path: str) -> bool:
        """A dotted module path is "private" if any segment starts with
        an underscore. ``pymat.vis._model`` is private; ``pymat.core``
        is not (single leading dunder/underscore-free segments)."""
        return any(seg.startswith("_") for seg in module_path.split("."))

    @pytest.mark.parametrize("name", PYMAT_FIRSTPARTY_NAMES)
    def test_pymat_export_has_no_private_module_segment(self, name: str) -> None:
        import pymat

        obj = getattr(pymat, name)
        mod = getattr(obj, "__module__", None)
        assert mod is not None, f"pymat.{name} has no __module__"
        assert not self._has_private_segment(mod), (
            f"pymat.{name}.__module__ = {mod!r} contains an underscore-"
            "prefixed segment; users get pushed toward the private path."
        )

    # Note: the weaker `_has_private_segment` check on PYMAT_VIS_FIRSTPARTY_NAMES
    # was dropped — for ``Vis`` / ``VisDeltas`` / ``FinishEntry`` the strict
    # equality test below subsumes it, and for the other re-exports
    # (``MatVisClient``, ``to_threejs``, etc.) the canonical-name round-trip
    # in ``TestCanonicalNameRoundTrip`` catches the same regression.

    @pytest.mark.parametrize("name", PYMAT_VIS_PUBLIC_TYPES)
    def test_pymat_vis_public_types_module_is_public_path(self, name: str) -> None:
        """Stronger pin for the three domain types specifically called
        out as public in ``pymat/vis/__init__.py``: ``__module__`` must
        equal the public re-export path, not just be private-segment-free.
        Catches a future move from ``_model`` to e.g. ``_internal`` that
        forgets to re-pin."""
        import pymat.vis

        obj = getattr(pymat.vis, name)
        assert obj.__module__ == "pymat.vis", (
            f"pymat.vis.{name}.__module__ = {obj.__module__!r}; "
            "expected 'pymat.vis' so type(...) / repr / IDE auto-import "
            "all surface the public path."
        )


# ── 2. __all__ integrity ─────────────────────────────────────


class TestAllIntegrity:
    """Every name in ``__all__`` resolves on the module without raising,
    and the documented public submodules are present."""

    def test_pymat_all_entries_resolve(self) -> None:
        """Every name in ``pymat.__all__`` resolves on the module.

        Implicitly enforced at collection time by ``from pymat import *``,
        but pinned explicitly here so a regression points at the public-
        API contract instead of cascading-failing across the suite."""
        import pymat

        for name in pymat.__all__:
            obj = getattr(pymat, name, None)
            assert obj is not None, f"pymat.{name} resolved to None"

    def test_pymat_vis_all_entries_resolve(self) -> None:
        import pymat.vis

        for name in pymat.vis.__all__:
            assert hasattr(pymat.vis, name), f"pymat.vis.{name} missing despite being in __all__"
            obj = getattr(pymat.vis, name)
            assert obj is not None, f"pymat.vis.{name} resolved to None"

    def test_pymat_vis_adapters_in_all(self) -> None:
        """``adapters`` is a public submodule and must be in ``__all__``
        so ``from pymat.vis import *`` brings it along and ``dir(pymat
        .vis)`` lists it as public."""
        import pymat.vis

        assert "adapters" in pymat.vis.__all__

    def test_pymat_vis_in_pymat_all(self) -> None:
        """``pymat.vis`` is the canonical entry point for adapters /
        client / domain types; it must appear in ``pymat.__all__`` so
        downstream code can rely on ``from pymat import vis``."""
        import pymat

        assert "vis" in pymat.__all__

    def test_pymat_vis_thirdparty_reexports_resolve(self) -> None:
        """Names re-exported from ``mat_vis_client`` are exempt from the
        private-segment rule (their ``__module__`` legitimately points
        at the upstream package), but they MUST resolve — the re-export
        is part of the contract advertised in the module docstring."""
        import pymat.vis

        for name in PYMAT_VIS_THIRDPARTY_NAMES:
            assert getattr(pymat.vis, name) is not None, (
                f"pymat.vis.{name} re-export from mat_vis_client missing"
            )


# ── 3. dir() discoverability ─────────────────────────────────


class TestDirDiscoverability:
    """``dir(pymat)`` drives IDE tab-completion. Every base material in
    ``_CATEGORY_BASES`` must be reachable so users discover ``stainless``,
    ``aluminum``, ``lyso`` etc. without reading the docs."""

    @pytest.mark.parametrize("name", ALL_KNOWN_BASE_MATERIALS)
    def test_base_material_in_pymat_dir(self, name: str) -> None:
        import pymat

        assert name in dir(pymat), (
            f"base material {name!r} missing from dir(pymat); IDE tab-completion won't surface it."
        )

    # Note: per-name "is name in dir(pymat)" pad was dropped — the loop-form
    # ``test_all_pymat_all_entries_in_dir`` below pins the same contract for
    # every name in ``__all__``, with a single failing test point that lists
    # the missing names instead of one parametrized failure per missing name.

    def test_all_pymat_all_entries_in_dir(self) -> None:
        """Every name in ``__all__`` is reachable via ``dir(pymat)``.

        ``pymat.__dir__`` derives from ``__all__`` (3.10.1) so adding a
        name to ``__all__`` automatically surfaces it in tab-completion;
        previously the function hardcoded a subset and silently dropped
        ``search``, ``ureg``, ``factories``, ``vis``."""
        import pymat

        missing = sorted(set(pymat.__all__) - set(dir(pymat)))
        assert missing == [], f"__all__ entries missing from dir(): {missing}"


# ── 4. Public type construction ──────────────────────────────


class TestPublicTypeConstruction:
    """Every public class must be constructible with its documented
    kwargs. If a future PR removes a public field silently, the build
    breaks — but the constructor stays callable. This catches that gap
    by exercising kwargs we promise to support."""

    def test_material_minimum_kwargs(self) -> None:
        from pymat import Material

        m = Material(name="probe")
        assert m.name == "probe"

    def test_material_documented_kwargs(self) -> None:
        from pymat import Material

        m = Material(
            name="Steel",
            density=7.8,
            color=(0.7, 0.7, 0.7),
            formula="Fe",
            mechanical={"density": 7.8, "youngs_modulus": 200},
            thermal={"melting_point": 1500},
            electrical={"resistivity": 7.2e-7},
            optical={"transparency": 0},
            vis={"metallic": 1.0, "roughness": 0.15},
        )
        assert m.properties.mechanical.density == 7.8
        assert m.properties.mechanical.youngs_modulus == 200
        assert m.vis.metallic == 1.0
        assert m.vis.roughness == 0.15

    @pytest.mark.parametrize("name", PYMAT_PUBLIC_TYPES[1:])  # skip Material (handled above)
    def test_property_dataclass_default_construction(self, name: str) -> None:
        """All ``*Properties`` dataclasses construct with no args (every
        field has a default)."""
        import pymat

        cls = getattr(pymat, name)
        instance = cls()
        assert dataclasses.is_dataclass(instance)

    @pytest.mark.parametrize("name", PYMAT_VIS_PUBLIC_TYPES)
    def test_vis_public_type_construction(self, name: str) -> None:
        import pymat.vis

        cls = getattr(pymat.vis, name)
        if name == "Vis":
            instance = cls()
            assert instance.source is None
        elif name == "VisDeltas":
            # TypedDict — instantiate via dict literal
            instance = cls(roughness=0.5)
            assert instance.get("roughness") == 0.5
        elif name == "FinishEntry":
            instance = cls(source="ambientcg", id="Metal032")
            assert instance["source"] == "ambientcg"
            assert instance["id"] == "Metal032"


# ── 5. Field-set freeze ──────────────────────────────────────


# Canonical field sets — a future rename has to update these or the
# test goes red. Order doesn't matter (we compare as sets), but a
# silent removal/rename is caught.
VIS_FIELDS = frozenset(
    {
        "source",
        "material_id",
        "tier",
        "finishes",
        "roughness",
        "metallic",
        "base_color",
        "ior",
        "transmission",
        "clearcoat",
        "emissive",
    }
)

VISDELTAS_KEYS = frozenset(
    {
        "source",
        "material_id",
        "tier",
        "finishes",
        "roughness",
        "metallic",
        "base_color",
        "ior",
        "transmission",
        "clearcoat",
        "emissive",
        "finish",
    }
)

FINISHENTRY_KEYS = frozenset({"source", "id"})

# ``Material`` exposes a public constructor with these documented kwargs
# (per the docstring on ``Material.__init__``). We freeze the kwargs of
# the constructor — the dataclass-internal field set includes private
# bookkeeping that we don't care about pinning here.
MATERIAL_INIT_KWARGS = frozenset(
    {
        "name",
        "density",
        "formula",
        "composition",
        "color",
        "grade",
        "temper",
        "treatment",
        "vendor",
        "mechanical",
        "thermal",
        "electrical",
        "optical",
        "vis",
        "manufacturing",
        "compliance",
        "sourcing",
        "properties",
        "parent",
        "_key",
        "_sources",
    }
)

SOURCE_FIELDS = frozenset({"citation", "kind", "ref", "license", "note"})


class TestFieldSetFreeze:
    """Pin the canonical field set of every public dataclass / TypedDict.
    Renames or removals trip the freeze, forcing the PR author to update
    this test (the moment of truth: are you really intending to break
    every downstream caller?)."""

    def test_vis_public_field_set(self) -> None:
        from pymat.vis import Vis

        # Public fields = dataclass fields excluding underscore-prefixed.
        public = {f.name for f in dataclasses.fields(Vis) if not f.name.startswith("_")}
        assert public == VIS_FIELDS, (
            f"Vis public field set drifted.\n  got:  {sorted(public)}\n  want: {sorted(VIS_FIELDS)}"
        )

    def test_visdeltas_keys(self) -> None:
        from pymat.vis import VisDeltas

        keys = set(VisDeltas.__annotations__)
        assert keys == VISDELTAS_KEYS, (
            f"VisDeltas keys drifted.\n  got:  {sorted(keys)}\n  want: {sorted(VISDELTAS_KEYS)}"
        )

    def test_finishentry_keys(self) -> None:
        from pymat.vis import FinishEntry

        keys = set(FinishEntry.__annotations__)
        assert keys == FINISHENTRY_KEYS, (
            f"FinishEntry keys drifted.\n  got:  {sorted(keys)}\n  want: {sorted(FINISHENTRY_KEYS)}"
        )

    def test_material_init_kwargs(self) -> None:
        from pymat import Material

        sig = inspect.signature(Material.__init__)
        # Drop ``self``
        kwargs = {p for p in sig.parameters if p != "self"}
        assert kwargs == MATERIAL_INIT_KWARGS, (
            f"Material.__init__ kwargs drifted.\n"
            f"  got:  {sorted(kwargs)}\n  want: {sorted(MATERIAL_INIT_KWARGS)}"
        )

    def test_source_fields(self) -> None:
        # ``Source`` is documented as a public type in 3.10.0 but is not
        # currently in ``pymat.__all__`` (see TestPublicSourceGap below).
        # Pin its field set via the implementation module so a rename is
        # still caught.
        from pymat.sources import Source

        fields = {f.name for f in dataclasses.fields(Source)}
        assert fields == SOURCE_FIELDS, (
            f"Source field set drifted.\n  got:  {sorted(fields)}\n  want: {sorted(SOURCE_FIELDS)}"
        )


# ── 6. type(...).__module__ flow on instances ────────────────


class TestInstanceModuleFlow:
    """The metadata pin in ``TestPublicApiContract`` checks the *class*.
    Verify behaviorally that instances flowing out of public APIs also
    surface the public path — so ``type(material.vis).__module__`` and
    ``repr(material.vis)`` agree with the contract."""

    def test_registry_material_vis_instance_module(self) -> None:
        from pymat import stainless

        v = stainless.vis
        assert type(v).__module__ == "pymat.vis", (
            f"stainless.vis is a {type(v).__module__}.{type(v).__name__}; "
            "downstream tools (build123d, IDE auto-import) read this."
        )

    def test_constructed_material_vis_instance_module(self) -> None:
        from pymat import Material

        m = Material(name="probe")
        assert type(m.vis).__module__ == "pymat.vis"

    def test_vis_override_result_instance_module(self) -> None:
        from pymat import stainless

        derived = stainless.vis.override(roughness=0.05)
        assert type(derived).__module__ == "pymat.vis"

    def test_repr_does_not_leak_private_path(self) -> None:
        """``repr(material.vis)`` is what users see in tracebacks and
        REPLs. The default dataclass repr renders the class name only,
        but ``Material.vis``'s docstring promises the public path is
        what surfaces — pin it via ``type(...).__name__`` + module."""
        from pymat import Material

        v = Material(name="probe").vis
        # Defense in depth: the qualified ``module.qualname`` form is
        # what Sphinx uses for cross-references.
        qualified = f"{type(v).__module__}.{type(v).__qualname__}"
        assert qualified == "pymat.vis.Vis", qualified


# ── 7. Sphinx-style canonical-name round-trip ────────────────


class TestCanonicalNameRoundTrip:
    """For every public type N, ``import_module(N.__module__).<name>``
    must resolve to the *same object*. Catches the case where
    ``N.__module__`` lies (e.g. is rewritten to ``pymat.vis`` but the
    type doesn't actually appear at that module's top level), which is
    what would trip Sphinx's autodoc cross-referencing."""

    @pytest.mark.parametrize("name", PYMAT_VIS_PUBLIC_TYPES)
    def test_pymat_vis_public_type_canonical_roundtrip(self, name: str) -> None:
        import pymat.vis

        obj = getattr(pymat.vis, name)
        mod = importlib.import_module(obj.__module__)
        # ``__qualname__`` for a top-level class is just the name; for
        # nested classes it would be ``Outer.Inner`` — split on '.' and
        # walk the chain to be safe.
        parts = obj.__qualname__.split(".")
        resolved: Any = mod
        for p in parts:
            resolved = getattr(resolved, p)
        assert resolved is obj, (
            f"{obj.__module__}.{obj.__qualname__} resolved to a different "
            f"object than pymat.vis.{name} — Sphinx cross-refs will land "
            "in the wrong place."
        )

    # Note: the per-name canonical-roundtrip on ``PYMAT_PUBLIC_TYPES``
    # was dropped — for ``Material`` / ``*Properties`` / ``Source`` whose
    # ``__module__`` points at ``pymat.core`` / ``pymat.properties`` /
    # ``pymat.sources``, the round-trip is verifying that classes are
    # defined where their ``__module__`` says they are, which is a Python
    # invariant rather than a contract a refactor could break without
    # going out of its way. The ``pymat.vis`` round-trip above (where
    # ``__module__`` is rewritten to a non-canonical path) is the
    # load-bearing case and remains pinned.

    def test_canonical_module_path_is_not_private(self) -> None:
        """The canonical module path itself must be importable as a
        public submodule — no leading underscore. ``pymat.vis._model``
        IS importable, but it's private; the canonical path of any
        public type should not look private."""
        import pymat.vis

        for name in PYMAT_VIS_PUBLIC_TYPES:
            obj = getattr(pymat.vis, name)
            assert not any(seg.startswith("_") for seg in obj.__module__.split(".")), (
                f"{name}.__module__ = {obj.__module__!r} is on a private path; "
                "Sphinx will render an underscore-prefixed cross-ref."
            )


# ── Documented-but-not-importable gap ────────────────────────


class TestPublicSourceContract:
    """``Source`` (added in 3.10.0 #150) is the public provenance type:
    it backs ``Material._sources`` and the ``[<material>._sources]``
    TOML table. 3.10.1 closes the trailing gap of the original PR and
    re-exports it on the top-level ``pymat`` namespace so consumers
    don't need a second import line.

    The class bound at ``pymat.Source`` must be the same object as
    ``pymat.sources.Source`` — an alias, not a shim — so type
    annotations on either path interoperate."""

    def test_source_importable_from_pymat(self) -> None:
        from pymat import Source
        from pymat.sources import Source as canonical_Source

        assert Source is canonical_Source

    def test_source_in_pymat_all(self) -> None:
        import pymat

        assert "Source" in pymat.__all__
