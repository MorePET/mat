"""Red tests for Bernhard's mat-vis#311 / #313 user-surface issues.

Each test is xfail(strict=True), so a fix flips it to XPASS and CI
fails until the marker is removed — preventing accidental "fixed
but still marked xfail" regressions.

Issues:
- mat#220: Vis.scalars accessor missing — companion to .textures
- mat#221: Vis repr stays None after fetch — observability of lazy state
- mat#222: scalar-only sources (physicallybased / tier=None)

When a fix lands, remove the corresponding xfail marker and verify
the test passes. Then re-run Bernhard's literal repro from the
mat-vis issue end-to-end (forward-verify) before claiming closed —
mat-vis#287/#288 lesson.
"""

from __future__ import annotations

import pytest

from pymat.vis._model import Vis

# ── #220: Vis.scalars accessor ────────────────────────────────


class TestIssue220ScalarsAccessor:
    """Bernhard's mat-vis#311 'Scalars as first class citizens' sub-bullet.

    Closed by the dispatch refactor: ``Vis.scalars`` now delegates to
    ``client._scalars_for(source, material_id)`` (catalog-authored
    values) merged with explicit caller overrides.

    Acceptance from mat#220:
    - v.scalars returns dict for any successfully-fetched Vis
    - Returns AUTHORED values from mat_vis.pbr.*, not adapter-normalized
    - No-op ({}) for Vis without identity
    - Lazy: doesn't trigger texture fetch (scalars are in catalog)
    """

    def test_scalars_attribute_exists_on_vis(self):
        v = Vis()
        assert v.scalars == {}

    def test_scalars_returns_authored_pbr(self, monkeypatch):
        """Bernhard's literal snippet from mat-vis#311.

        ``v.scalars`` returns the authored PBR scalars from the catalog
        (via ``client.asset(...).scalars``), keyed by mat-vis adapter
        schema names.
        """

        class FakeAsset:
            scalars = {
                "roughness": 0.4,
                "metalness": 1.0,
                "ior": 1.5,
                "color_hex": "#cccccc",
            }
            textures: dict = {}

        class FakeClient:
            def fetch_all_textures(self, source, material_id, *, tier="1k"):
                return {"color": b"png", "normal": b"png", "roughness": b"png"}

            def asset(self, source, material_id, tier):
                return FakeAsset()

        import mat_vis_client as _client

        monkeypatch.setattr(_client, "_client", FakeClient())

        v = Vis(source="gpuopen", material_id="Aluminum Brushed", tier="1k")
        scalars = v.scalars
        assert isinstance(scalars, dict)
        # Keys per the catalog's mat_vis.pbr.* schema
        for key in ("roughness", "metalness", "ior", "color_hex"):
            assert key in scalars

    def test_scalars_does_not_trigger_texture_fetch(self, monkeypatch):
        """Lazy property: scalars come from the catalog (already loaded
        as part of identity lookup). Reading them must NOT trip the
        texture HTTP fetch."""
        called = {"fetch": 0}

        class FakeAsset:
            scalars = {"roughness": 0.4, "metalness": 1.0}
            textures: dict = {}

        class FakeClient:
            def fetch_all_textures(self, source, material_id, *, tier="1k"):
                called["fetch"] += 1
                return {"color": b"png"}

            def asset(self, source, material_id, tier):
                return FakeAsset()

        import mat_vis_client as _client

        monkeypatch.setattr(_client, "_client", FakeClient())

        v = Vis(source="gpuopen", material_id="Aluminum Brushed", tier="1k")
        _ = v.scalars
        assert called["fetch"] == 0


# ── #221: repr observability ──────────────────────────────────


@pytest.mark.xfail(
    strict=True,
    reason="mat#221: repr stays all-None after fetch — no fetched flag",
)
class TestIssue221ReprObservability:
    """Bernhard's mat-vis#311 'Inconsistent outputs' sub-bullet.

    Acceptance from mat#221:
    - Pre-fetch repr shows fetched=False
    - Post-fetch repr shows fetched=True plus scalars=/available_textures=
    - Override semantics unchanged
    """

    def test_pre_fetch_repr_shows_fetched_false(self):
        v = Vis(source="gpuopen", material_id="Aluminum Brushed", tier="1k")
        assert "fetched=False" in repr(v)

    def test_post_fetch_repr_shows_fetched_true(self, monkeypatch):
        class FakeClient:
            def fetch_all_textures(self, source, material_id, *, tier="1k"):
                return {"color": b"png", "normal": b"png", "roughness": b"png"}

        import mat_vis_client as _client

        monkeypatch.setattr(_client, "_client", FakeClient())

        v = Vis(source="gpuopen", material_id="Aluminum Brushed", tier="1k")
        v.textures  # trigger fetch  # noqa: B018

        r = repr(v)
        assert "fetched=True" in r
        # Bernhard's literal expectation includes a textures summary.
        assert "available_textures" in r or "scalars" in r

    def test_repr_changes_after_fetch(self, monkeypatch):
        """The whole point: repr must visibly differ pre/post fetch so
        the user has a signal that the lazy fetch happened."""

        class FakeClient:
            def fetch_all_textures(self, source, material_id, *, tier="1k"):
                return {"color": b"png"}

        import mat_vis_client as _client

        monkeypatch.setattr(_client, "_client", FakeClient())

        v = Vis(source="gpuopen", material_id="Aluminum Brushed", tier="1k")
        before = repr(v)
        v.textures  # noqa: B018
        after = repr(v)
        assert before != after


# ── #222: scalar-only sources (physicallybased) ───────────────


def _install_scalar_only_fake_client(monkeypatch):
    """FakeClient mirroring the real client's behavior: raises
    MaterialNotStagedError-style exceptions when tier doesn't match
    the source's manifest. This reproduces the actual physicallybased
    failure mode (not a permissive mock that silently returns {}).
    """

    class _NotStaged(Exception):
        pass

    class FakeClient:
        manifest = {
            "sources": {
                "physicallybased": {
                    "catalog": "physicallybased.json",
                    "tiers": {"scalar": {"complete": True}},
                },
                "gpuopen": {
                    "catalog": "gpuopen.json",
                    "tiers": {"1k": {"complete": True}},
                },
            }
        }

        def fetch_all_textures(self, source, material_id, *, tier="1k"):
            src_entry = self.manifest["sources"].get(source, {})
            available = list(src_entry.get("tiers", {}))
            if tier not in available:
                raise _NotStaged(
                    f"material {material_id!r} not staged at tier {tier!r}. Available: {available}"
                )
            if source == "physicallybased":
                return {}
            return {"color": b"png"}

    import mat_vis_client as _client

    fake = FakeClient()
    monkeypatch.setattr(_client, "_client", fake)
    return fake, _NotStaged


class TestIssue222ScalarOnlySources:
    """Bernhard's mat-vis#313 + #311 'Support physicallybased.info'.

    The pymat-side half of the cascade (mat-vis-side bake fix is
    tracked separately). Acceptance:
    - Vis("physicallybased", "Aluminum").to_threejs() returns valid dict
    - Vis("physicallybased", "Aluminum").textures returns {}
    - Vis("physicallybased", "Aluminum").scalars returns authored PBR

    Tests inject a fake client whose manifest mirrors the real
    physicallybased shape (only 'scalar' tier exists) AND raises like
    the real client when tier doesn't match. The fix must detect
    scalar-only sources at construction or fetch time and resolve
    tier→"scalar" without the user passing it explicitly.
    """

    def test_default_tier_resolves_to_scalar_for_scalar_only_source(self, monkeypatch):
        """No explicit tier → Vis must pick "scalar" from the manifest,
        not the dataclass default "1k"."""
        _install_scalar_only_fake_client(monkeypatch)
        v = Vis(source="physicallybased", material_id="Aluminum")
        assert v.tier == "scalar"

    def test_textures_returns_empty_for_scalar_only(self, monkeypatch):
        """No exception, just an empty texture dict."""
        _install_scalar_only_fake_client(monkeypatch)
        v = Vis(source="physicallybased", material_id="Aluminum")
        assert v.textures == {}

    def test_to_threejs_succeeds_for_scalar_only(self, monkeypatch):
        """Bernhard's exact repro from mat-vis#313."""
        _install_scalar_only_fake_client(monkeypatch)
        v = Vis(source="physicallybased", material_id="Aluminum")
        result = v.to_threejs()
        assert isinstance(result, dict)


# ── #222 regression guard (must keep passing — NOT xfail) ─────


def test_issue222_textured_source_default_unchanged(monkeypatch):
    """Non-regression guard for mat#222: textured sources still
    default to tier='1k'. Sits outside the xfail class because it
    must pass today AND after the fix lands.
    """
    _install_scalar_only_fake_client(monkeypatch)
    v = Vis(source="gpuopen", material_id="Aluminum Brushed")
    assert v.tier == "1k"
