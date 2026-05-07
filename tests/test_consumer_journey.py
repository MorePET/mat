"""End-to-end consumer journey tests.

py-mat's downstream consumers (build123d, ocp_vscode, anyone reaching for
``pymat.vis.to_threejs``) hit a sequence of steps we never exercised as a
sequence: discovery → derivation → attachment → export → recovery from
typos. The unit tests cover each piece in isolation; this file walks the
journey from first to last so a breakage at *any* step in the sequence
surfaces here, not in a downstream PR review.

Bernhard's nine mat-vis issues (#280–#288) and py-mat #98 all stem from
this gap. Tests below pin the steps that work today and ``xfail`` the
ones that don't, with the gap reason on each.

No network: all texture-fetch points are mocked via ``mat_vis_client``'s
shared singleton, mirroring the pattern in ``tests/test_vis.py``.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

import pymat
from pymat import Material
from pymat.vis import (
    Vis,
    export_mtlx,
    to_gltf,
    to_threejs,
)

# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def fake_textures(monkeypatch):
    """Replace the shared mat-vis client with a fake that returns
    deterministic PNG bytes — keeps export / mtlx paths off the network."""
    import mat_vis_client as _client

    class FakeClient:
        manifest = {"release_tag": "fake", "tiers": {}}

        def fetch_all_textures(self, source, material_id, *, tier="1k"):
            return {"color": b"\x89PNG_fake_color", "roughness": b"\x89PNG_fake_rough"}

        def channels(self, source, material_id, tier):
            return ["color", "roughness"]

        def materialize(self, source, material_id, tier, out):
            return Path(out)

        def mtlx(self, source, material_id, *, tier="1k"):
            class _MtlxStub:
                def xml(self_inner):
                    return "<materialx version='1.39'/>"

                def export(self_inner, out):
                    return Path(out)

            return _MtlxStub()

    monkeypatch.setattr(_client, "_client", FakeClient())
    return FakeClient


# ============================================================================
# 1. DISCOVERY — user knows a name, doesn't know our registry keys
# ============================================================================


class TestDiscovery:
    """A consumer types a material name they have in their head. They
    should not need to know our registry keys (``s304``, ``a6061_T6``)
    to find what they want."""

    def test_subscript_resolves_human_name(self):
        """``pymat["Stainless Steel 304"]`` is the canonical entry for a
        consumer who's writing a script and has the name in their head."""
        m = pymat["Stainless Steel 304"]
        assert m.name == "Stainless Steel 304"

    def test_subscript_resolves_registry_key(self):
        """``pymat["s304"]`` works too — for users who learned the keys."""
        m = pymat["s304"]
        assert m.name == "Stainless Steel 304"

    def test_subscript_resolves_grade(self):
        """``pymat["304"]`` resolves by grade alone."""
        m = pymat["304"]
        assert m.name == "Stainless Steel 304"

    def test_contains_membership_check(self):
        """``"Stainless Steel 304" in pymat`` is the cheap pre-check
        before subscripting."""
        assert "Stainless Steel 304" in pymat
        assert "DefinitelyNotAMaterial" not in pymat

    def test_search_returns_materials(self):
        """``pymat.search("stainless")`` returns Material instances —
        not registry keys, not strings."""
        hits = pymat.search("stainless")
        assert hits  # non-empty
        assert all(isinstance(m, Material) for m in hits)

    def test_search_handles_typo(self):
        """One-edit typo still finds the material (issue #179)."""
        hits = pymat.search("stinless 304")
        names = [m.name for m in hits]
        assert "Stainless Steel 304" in names

    def test_unknown_material_offers_close_matches(self):
        """User asks for something we don't have but did mean a real
        one — error must show the close matches by *name*, not by
        UUID/registry-key. Closes mat-vis #286 spirit."""
        with pytest.raises(KeyError) as exc:
            pymat["Stinless Steel 304"]  # one-edit typo
        msg = str(exc.value)
        assert "Stinless Steel 304" in msg  # echoes the user input
        assert "Stainless Steel 304" in msg  # close match by name


# ============================================================================
# 2. DERIVATION — user wants a tweaked variant without corrupting registry
# ============================================================================


class TestDerivation:
    """Consumer wants a polished / rougher / recolored variant. The
    motivating bug (build123d #1270): mutating ``m.vis`` directly
    corrupts the registry singleton every other caller sees."""

    def test_override_returns_new_vis(self):
        steel = pymat["Stainless Steel 304"]
        polished = steel.vis.override(roughness=0.05, finish="polished")
        assert polished is not steel.vis
        assert isinstance(polished, Vis)

    def test_override_does_not_mutate_registry(self):
        """The headline contract — registry singleton is unchanged."""
        steel = pymat["Stainless Steel 304"]
        original_roughness = steel.vis.roughness
        original_finish = steel.vis.finish
        steel.vis.override(roughness=0.99, finish="polished")
        assert steel.vis.roughness == original_roughness
        assert steel.vis.finish == original_finish

    def test_with_vis_returns_independent_material(self):
        """Material.with_vis() is the safe handoff for "I want this
        material, with this Vis"."""
        steel = pymat["Stainless Steel 304"]
        custom = steel.with_vis(steel.vis.override(roughness=0.05))
        assert custom is not steel
        assert custom.vis is not steel.vis
        assert custom.vis.roughness == 0.05
        assert steel.vis.roughness != 0.05  # registry untouched

    def test_with_vis_preserves_physics_properties(self):
        """The derived Material must still be the same physical material —
        only the appearance changed."""
        steel = pymat["Stainless Steel 304"]
        custom = steel.with_vis(steel.vis.override(roughness=0.05))
        assert custom.density == steel.density
        assert custom.name == steel.name


# Cross-contamination is covered in tests/test_vis_override.py — not duplicated here.


# ============================================================================
# 3. ATTACHMENT — hand a Material to a CAD-like wrapper
# ============================================================================


class _FakeBuild123dPart:
    """Minimal stand-in for a build123d Part that just stores a material
    reference. The real build123d Part exposes ``.material`` the same way
    (see ``Material.apply_to`` in core.py and build123d#1270)."""

    def __init__(self, name: str):
        self.name = name
        self.material = None


class TestAttachment:
    """A consumer attaches a Material to a CAD object. We don't have
    build123d locally, but the data flow is what we need to pin."""

    def test_attach_material_to_part(self):
        part = _FakeBuild123dPart("housing")
        part.material = pymat["Stainless Steel 304"]
        assert part.material.name == "Stainless Steel 304"
        # Round-trip — Vis is reachable through the attached material
        assert part.material.vis.source == "ambientcg"

    def test_attach_derived_material(self):
        """Variant attaches the same way the registry instance does."""
        steel = pymat["Stainless Steel 304"]
        polished = steel.with_vis(steel.vis.override(finish="polished"))
        part = _FakeBuild123dPart("polished housing")
        part.material = polished
        # The wrapper sees the variant's appearance, not the registry's.
        assert part.material.vis.finish == "polished"

    def test_apply_to_helper(self):
        """``material.apply_to(part)`` is the documented build123d sugar —
        the round-trip must surface the material on ``.material``."""
        part = _FakeBuild123dPart("bracket")
        result = pymat["Stainless Steel 304"].apply_to(part)
        # apply_to either mutates `part.material` or returns the part with
        # it set; either way the caller can read it back.
        attached = getattr(result, "material", None) or part.material
        assert attached is not None
        assert attached.name == "Stainless Steel 304"


# ============================================================================
# 4. EXPORT — hand to renderer adapters
# ============================================================================


class TestExport:
    """Three.js / glTF / MaterialX adapters are the cross-tool handoff.
    Output must match each format's spec."""

    def test_to_threejs_shape(self, fake_textures):
        steel = pymat["Stainless Steel 304"]
        d = to_threejs(steel)
        # Three.js MeshPhysicalMaterial init dict — pin the keys we care about.
        assert d["type"] == "MeshPhysicalMaterial"
        assert "metalness" in d
        assert "roughness" in d
        assert isinstance(d["metalness"], (int, float))

    def test_to_threejs_picks_up_override(self, fake_textures):
        """A variant's override values flow through the adapter."""
        steel = pymat["Stainless Steel 304"]
        custom = steel.with_vis(steel.vis.override(roughness=0.7, metallic=0.0))
        d = to_threejs(custom)
        assert d["roughness"] == 0.7
        assert d["metalness"] == 0.0

    def test_to_gltf_shape(self, fake_textures):
        steel = pymat["Stainless Steel 304"]
        d = to_gltf(steel)
        # glTF 2.0 spec: the PBR block must be ``pbrMetallicRoughness``.
        assert "pbrMetallicRoughness" in d
        pbr = d["pbrMetallicRoughness"]
        assert "metallicFactor" in pbr
        assert "roughnessFactor" in pbr
        # Material name surfaces from the Material itself
        assert d.get("name") == "Stainless Steel 304"

    def test_to_gltf_basecolor_array_form(self, fake_textures):
        """glTF spec: baseColorFactor is a 4-float array, not a hex."""
        m = Material(name="test")
        m.vis.base_color = (0.5, 0.25, 0.75, 1.0)
        d = to_gltf(m)
        bc = d["pbrMetallicRoughness"].get("baseColorFactor")
        assert isinstance(bc, list) and len(bc) == 4

    def test_export_mtlx_writes_file(self, fake_textures):
        """``export_mtlx`` returns a Path to the .mtlx file on disk."""
        steel = pymat["Stainless Steel 304"]
        with tempfile.TemporaryDirectory() as out:
            path = export_mtlx(steel, Path(out))
            assert path.exists()
            assert path.suffix == ".mtlx"

    def test_vis_method_sugar_matches_module_form(self, fake_textures):
        """``material.vis.to_threejs()`` (method) and
        ``pymat.vis.to_threejs(material)`` (function) yield the same dict.
        Both are documented; both must agree."""
        steel = pymat["Stainless Steel 304"]
        custom = steel.with_vis(steel.vis.override(roughness=0.42))
        method_form = custom.vis.to_threejs()
        function_form = to_threejs(custom)
        # ``Vis.to_threejs()`` doesn't know the owning Material's name, but
        # all the PBR fields must agree.
        assert method_form["roughness"] == function_form["roughness"]
        assert method_form["metalness"] == function_form["metalness"]


# ============================================================================
# 5. ERROR JOURNEY — the user typos, gets a useful message
# ============================================================================


class TestErrorJourney:
    """A consumer makes mistakes. Errors must echo the user's input
    (so they can see what they typed) and offer human-readable
    alternatives — never internal UUIDs or registry keys when the
    user supplied a human name. Mat-vis #286 spirit."""

    def test_unknown_material_echoes_input(self):
        with pytest.raises(KeyError) as exc:
            pymat["TotallyMadeUpMaterial"]
        assert "TotallyMadeUpMaterial" in str(exc.value)

    def test_unknown_finish_lists_available(self):
        steel = pymat["Stainless Steel 304"]
        available = sorted(steel.vis.finishes.keys())
        assert len(available) >= 2, "fixture precondition — multi-finish material"
        with pytest.raises(ValueError) as exc:
            steel.vis.override(finish="mirror")
        msg = str(exc.value)
        assert "mirror" in msg  # echoes user input
        # All actual finish names appear, not just one — consumers need
        # the full list, not a sample.
        for name in available:
            assert name in msg, f"finish {name!r} missing from error: {msg}"

    def test_typo_kwarg_on_override_lists_valid_keys(self):
        """build123d-style consumer mistypes ``roughnes=`` — error must
        point at ``roughness`` so they can fix it."""
        steel = pymat["Stainless Steel 304"]
        with pytest.raises(TypeError) as exc:
            steel.vis.override(roughnes=0.5)
        msg = str(exc.value)
        assert "roughnes" in msg
        assert "roughness" in msg  # the right name surfaces

    def test_empty_string_lookup_rejected(self):
        with pytest.raises(KeyError, match="empty"):
            pymat[""]

    def test_no_uuid_leaks_in_typo_error(self):
        """Pin: no UUID-shaped strings in the human-name error path.
        Mat-vis #286 was about UUIDs leaking into UnknownMaterialError;
        py-mat's own KeyError for human-name lookup must not regress
        into the same shape."""
        import re

        with pytest.raises(KeyError) as exc:
            pymat["Stinless Steel 304"]  # close to a real name
        msg = str(exc.value)
        # Eight-four-four-four-twelve-hex UUID pattern
        uuid_pat = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
        assert not uuid_pat.search(msg), f"UUID leaked into user-facing error: {msg}"

    def test_unknown_tier_raises_at_assignment(self):
        """Closes the symmetry gap with ``Vis.finish=`` — the tier
        setter now validates against the manifest's tier list at
        assignment time so a typo (``vis.tier = "99k"``) echoes back to
        the consumer instead of surfacing deep inside mat-vis-client on
        the next ``.textures`` access. Mirrors the asymmetry Bernhard
        flagged in the broader build123d#1270 / mat-vis #280 thread."""
        steel = pymat["Stainless Steel 304"]
        with pytest.raises(ValueError, match="Unknown tier"):
            steel.vis.override(tier="99k")  # no such tier in the manifest


# ============================================================================
# 6. PUBLIC-IMPORT JOURNEY — every name a consumer needs is non-underscore
# ============================================================================


class TestPublicImports:
    """Pin the import paths a consumer should rely on. Nothing
    underscore-prefixed should be required to use the documented API.
    Closes py-mat #98 / mat-vis #282.

    Bare-import existence checks for ``Vis`` / ``VisDeltas`` /
    ``FinishEntry`` / ``Material`` / adapters live in
    ``tests/test_public_api_surface.py`` (canonical module-path +
    field-set freeze). This file pins only the consumer-visible
    *behavior* of those imports — the headline being that
    ``type(material.vis).__module__`` reads as the public path."""

    def test_vis_module_path_is_public(self):
        """``type(m.vis).__module__`` must read ``pymat.vis`` — not
        ``pymat.vis._model``. Closes py-mat #98 — Bernhard's complaint
        was that ``stainless.vis`` reported its class as living in a
        private module, pushing him toward the underscore path."""
        steel = pymat["Stainless Steel 304"]
        assert type(steel.vis).__module__ == "pymat.vis"

    def test_vis_importable_from_top_level_pymat(self):
        """``from pymat import Vis`` works — closes the trailing gap of
        py-mat #98 (which only fixed the canonical `pymat.vis.Vis` import
        path; this test pins the convenience top-level alias). The class
        bound at `pymat.Vis` must be the same object as `pymat.vis.Vis`,
        not a shim."""
        import pymat as p
        from pymat.vis import Vis as canonical_Vis

        assert hasattr(p, "Vis")
        assert p.Vis is canonical_Vis


# ============================================================================
# Cross-cutting: full journey, single test
# ============================================================================


class TestFullJourney:
    """The whole journey end-to-end in one test — guards against
    inter-step regressions where each unit test passes but the chain
    breaks at a seam."""

    def test_discover_derive_attach_export(self, fake_textures):
        # 1. Discover by human name
        steel = pymat["Stainless Steel 304"]

        # 2. Derive a polished variant without touching the registry
        polished_vis = steel.vis.override(finish="polished", roughness=0.08)
        polished = steel.with_vis(polished_vis)

        # 3. Attach to a notional CAD wrapper
        part = _FakeBuild123dPart("housing")
        part.material = polished

        # 4. Export to Three.js + glTF — both must reflect the override
        three = to_threejs(part.material)
        gltf = to_gltf(part.material)
        assert three["roughness"] == 0.08
        assert gltf["pbrMetallicRoughness"]["roughnessFactor"] == 0.08
        assert gltf["name"] == "Stainless Steel 304"

        # 5. Registry singleton untouched throughout — both axes of the
        # override must remain unchanged on the registry, not just one.
        assert steel.vis.roughness != 0.08
        assert steel.vis.finish != "polished"
