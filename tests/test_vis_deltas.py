"""Tests for the ``VisDeltas`` TypedDict (#108).

``VisDeltas`` is the static-typing surface for ``Vis.override(**deltas)``
kwargs (PEP 692 ``Unpack``). It has no runtime behavior — the override
runtime validation is in ``Vis.override`` itself — so these tests pin:

- the TypedDict is importable from the public surface
- it stays in sync with the ``Vis`` field set + ``finish`` property
- a runtime-constructed dict matching the schema works as **deltas
  (round-trip via ``Vis.override(**delta_dict)``)
"""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import pytest

from pymat.vis import Vis, VisDeltas
from pymat.vis._model import FinishEntry


class TestPublicSurface:
    def test_visdeltas_importable_from_pymat_vis(self):
        """``from pymat.vis import VisDeltas`` works."""
        assert VisDeltas is not None

    def test_visdeltas_is_typeddict(self):
        """``VisDeltas`` is a TypedDict with all keys optional."""
        # TypedDict subclasses expose __total__ (False for total=False)
        assert getattr(VisDeltas, "__total__", True) is False

    def test_finishentry_importable_too(self):
        """``FinishEntry`` (used inside VisDeltas) is also exposed."""
        assert FinishEntry is not None

    def test_vis_re_exported(self):
        """``Vis`` itself is now reachable from ``pymat.vis``."""
        from pymat.vis._model import Vis as _ModelVis

        assert Vis is _ModelVis


class TestVisDeltasMirrorsVisFields:
    """``VisDeltas`` must enumerate every public Vis field + ``finish``.
    If a future PR adds (or removes) a Vis field but forgets to update
    VisDeltas, this test breaks loudly."""

    def test_all_public_vis_fields_in_visdeltas(self):
        public_fields = {f.name for f in fields(Vis) if not f.name.startswith("_")}
        delta_keys = set(VisDeltas.__annotations__)
        # Every public Vis field must appear in VisDeltas
        missing = public_fields - delta_keys
        assert not missing, f"Vis fields missing from VisDeltas: {missing}"

    def test_finish_property_in_visdeltas(self):
        """``finish=`` is a property setter, not a field — must be in
        the TypedDict explicitly."""
        assert "finish" in VisDeltas.__annotations__

    def test_no_extra_keys_in_visdeltas(self):
        """VisDeltas should not contain keys that aren't real override
        targets (private fields, methods, etc.)."""
        public_fields = {f.name for f in fields(Vis) if not f.name.startswith("_")}
        valid_extras = {"finish"}  # the property setter
        delta_keys = set(VisDeltas.__annotations__)
        extras = delta_keys - public_fields - valid_extras
        assert not extras, f"VisDeltas has unknown keys: {extras}"


class TestRuntimeRoundTrip:
    """A dict matching the VisDeltas schema can be unpacked into
    ``override(**)`` and produces the expected result."""

    def test_unpack_partial_deltas_dict(self):
        v = Vis(source="ambientcg", material_id="Metal012", roughness=0.3)
        deltas: VisDeltas = {"roughness": 0.7, "metallic": 0.5}
        v2 = v.override(**deltas)
        assert v2.roughness == 0.7
        assert v2.metallic == 0.5
        assert v.roughness == 0.3  # unchanged

    def test_unpack_with_finish(self):
        v = Vis(
            source="ambientcg",
            material_id="Metal012",
            finishes={
                "brushed": {"source": "ambientcg", "id": "Metal012"},
                "polished": {"source": "ambientcg", "id": "Metal049A"},
            },
        )
        deltas: VisDeltas = {"finish": "polished", "roughness": 0.05}
        v2 = v.override(**deltas)
        assert v2._finish == "polished"
        assert v2.material_id == "Metal049A"
        assert v2.roughness == 0.05

    def test_unpack_identity_change(self):
        v = Vis(source="ambientcg", material_id="Metal012")
        deltas: VisDeltas = {"source": "polyhaven", "material_id": "metal_01"}
        v2 = v.override(**deltas)
        assert v2.source == "polyhaven"
        assert v2.material_id == "metal_01"

    def test_unpack_empty_deltas(self):
        v = Vis(source="ambientcg", material_id="Metal012", roughness=0.3)
        deltas: VisDeltas = {}
        v2 = v.override(**deltas)
        assert v2 == v
        assert v2 is not v


class TestIdentityFieldsTypedAsStr:
    """``VisDeltas.source``/``material_id`` are typed as ``str`` (no
    ``| None``) even though the underlying Vis field is ``str | None``.

    Reason: ``override`` routes identity through ``set_identity``, which
    interprets ``None`` as "leave unchanged" — so passing ``source=None``
    would silently no-op, not clear the field. Typing the kwarg as
    bare ``str`` enforces the kwargs idiom (omit to leave alone) and
    keeps the type-checker contract honest. Pin both the TypedDict
    annotation and the runtime no-op behavior so a future "let users
    pass None to clear" change has to update everything in lockstep.
    """

    def test_visdeltas_source_typed_as_str(self):
        # ``from __future__ import annotations`` means values are stored
        # as forward references — compare the rendered forward-ref arg
        # string. Bare ``str`` (not a union with None).
        anns = VisDeltas.__annotations__
        for field_name in ("source", "material_id", "tier"):
            ann = anns[field_name]
            ann_str = ann.__forward_arg__ if hasattr(ann, "__forward_arg__") else str(ann)
            assert ann_str == "str", f"{field_name}: expected 'str', got {ann_str!r}"

    def test_runtime_source_none_is_silent_noop(self):
        """If a user disregards the type and passes ``source=None`` at
        runtime, identity is left unchanged (matches set_identity
        semantics). Documents the lying-type the typing fix prevents
        statically."""
        v = Vis(source="ambientcg", material_id="Metal012", tier="1k")
        # Bypass type checker — this is the runtime path
        v2 = v.override(**{"source": None})  # type: ignore[typeddict-item]
        assert v2.source == "ambientcg"  # NOT cleared


class TestPyTypedMarkerShipped:
    """PEP 561 marker — without ``py.typed`` mypy refuses to read
    annotations and the whole ``Unpack[VisDeltas]`` effort delivers
    zero value to mypy users."""

    def test_py_typed_present_in_package(self):
        import pymat

        pkg_dir = Path(pymat.__file__).parent
        marker = pkg_dir / "py.typed"
        assert marker.exists(), (
            f"PEP 561 marker missing at {marker}. Without it, mypy "
            f"strict-mode users get no benefit from VisDeltas typing."
        )


class TestRuntimeIsTypingOnly:
    """``Unpack[VisDeltas]`` is wrapped in ``if TYPE_CHECKING:`` —
    confirm there's no runtime side effect: the actual signature is
    still ``**deltas: Any``, kwarg validation is still done by
    ``override``'s body, unknown kwargs still raise ``TypeError``."""

    def test_unknown_kwarg_still_raises(self):
        """The TypedDict doesn't enforce at runtime — the override
        body's ``valid_keys`` check does. Unchanged from 3.7.0."""
        v = Vis(source="x", material_id="y")
        with pytest.raises(TypeError, match="roughnes"):
            v.override(roughnes=0.5)  # typo

    def test_typing_extensions_only_imported_under_type_checking(self):
        """``typing_extensions`` is imported only inside ``if
        TYPE_CHECKING:`` — must not be a runtime dependency. If a
        future refactor accidentally promotes the import, this test
        won't catch it (TYPE_CHECKING is False at runtime, so the
        import never runs in either case), but the assertion below
        documents intent."""
        import pymat.vis._model as model

        # The Unpack name should NOT exist as a module-level attr at runtime.
        assert not hasattr(model, "Unpack"), (
            "Unpack leaked out of TYPE_CHECKING block — would force "
            "typing_extensions as a runtime dep"
        )
