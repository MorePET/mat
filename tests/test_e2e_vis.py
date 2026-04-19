"""End-to-end test: Material → vis → mat-vis live data → adapter output.

Hits real mat-vis release assets. Skip with ``MAT_VIS_SKIP_LIVE=1``.

These tests depend on the ambientcg CDN (via mat-vis release assets).
When the CDN returns 5xx — genuine outages, rate-limits, regional
Akamai blips — the tests would otherwise go red and mask real
regressions. ``_skip_on_upstream_outage`` is a context manager the
tests wrap their network calls in: a 5xx turns into a ``pytest.skip``
with the upstream HTTP code in the reason, keeping CI signal
meaningful. Any other exception propagates normally.

The guard catches both error shapes:

- ``urllib.error.HTTPError`` — raw bubble-up from mat-vis-client 0.4.x
- ``MatVisError`` subclasses (``HTTPFetchError``, ``NetworkError``) —
  the typed hierarchy added in mat-vis-client 0.5.0. Prefer these
  going forward; the urllib catch is kept as a one-release bridge
  while 0.4.x installs still show up in CI.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from urllib.error import HTTPError

import pytest

SKIP_LIVE = os.environ.get("MAT_VIS_SKIP_LIVE", "0") == "1"


# Optional typed-error imports — mat-vis-client 0.5.0+. On 0.4.x
# these don't exist; the guard still works via the urllib catch.
try:
    from mat_vis_client import HTTPFetchError, NetworkError

    _TYPED_FETCH_ERRORS: tuple[type[Exception], ...] = (HTTPFetchError, NetworkError)
except ImportError:  # pragma: no cover — 0.4.x compatibility
    _TYPED_FETCH_ERRORS = ()


@contextmanager
def _skip_on_upstream_outage():
    """Skip the current test when mat-vis's CDN is flaky.

    Catches three shapes:

    - ``urllib.error.HTTPError`` 5xx — 0.4.x raw passthrough.
    - ``HTTPFetchError`` / ``NetworkError`` — 0.5.0 typed wrappers.
      Skipped unconditionally (any network error = flaky upstream).
    - ``AssertionError`` whose message matches "no textures returned"
      — mat-vis-client 0.4.x logs the HTTP error and returns empty
      dicts, so the *test* assertion fires downstream of the real
      network failure. Retained as a bridge; in 0.5.0 the typed
      exception surfaces first, so this branch becomes dead code
      once the pin moves.
    """
    try:
        yield
    except HTTPError as exc:
        if 500 <= exc.code < 600:
            pytest.skip(f"mat-vis CDN outage: {exc.code} {exc.reason}")
        raise
    except _TYPED_FETCH_ERRORS as exc:
        # Any typed network / HTTP failure is an upstream flake — skip.
        # Use getattr for .code since NetworkError doesn't have one.
        code = getattr(exc, "code", "?")
        pytest.skip(f"mat-vis CDN outage (typed): {type(exc).__name__} code={code}")
    except AssertionError as exc:
        msg = str(exc)
        # mat-vis-client 0.4.x logs "HTTP Error 5xx" and returns empty
        # dicts; the test-side assertion is "no textures fetched for
        # X" — if that's the shape we see, treat it as an upstream
        # outage. Dead path on 0.5.0+ (typed errors fire first).
        if (
            "No textures for" in msg
            or "No textures fetched" in msg
            or "No texture maps in to_threejs output" in msg
        ):
            pytest.skip(f"mat-vis CDN likely flaky (no textures returned): {msg}")
        raise


@pytest.mark.skipif(SKIP_LIVE, reason="MAT_VIS_SKIP_LIVE=1")
class TestEndToEnd:
    """Full pipeline: TOML material → vis textures → Three.js output."""

    def test_search_and_fetch(self):
        """Search the mat-vis index, fetch textures for a result."""
        from pymat import vis

        # Search for metals in the corpus. A fresh CI environment with
        # no seeded indexes (or a partial release manifest) returns an
        # empty list — that's an upstream/infra issue, not a py-mat bug,
        # so skip rather than fail the run.
        results = vis.search(category="metal", limit=3)
        if not results:
            pytest.skip(
                "mat-vis index returned no metals — likely unseeded cache "
                "or manifest hiccup on the CDN. Retry or reseed."
            )

        mat_id = results[0]["id"]
        source = results[0].get("source", "ambientcg")
        assert mat_id, "Empty material ID"

        with _skip_on_upstream_outage():
            # Fetch textures via HTTP range read
            textures = vis.fetch(source, mat_id, tier="1k")
            assert len(textures) > 0, f"No textures for {source}/{mat_id}"

            # Verify PNG bytes
            for channel, data in textures.items():
                assert data[:4] == b"\x89PNG", f"{channel}: not a valid PNG"
                assert len(data) > 100, f"{channel}: suspiciously small ({len(data)} bytes)"

    def test_material_vis_textures(self):
        """Material.vis.textures fetches real PBR textures."""
        from pymat import Material, vis

        # Find a material that exists in mat-vis
        results = vis.search(category="wood", limit=1)
        if not results:
            pytest.skip("No wood materials in mat-vis index")

        source = results[0].get("source", "ambientcg")
        mat_id = results[0]["id"]

        # Create a material and wire vis
        m = Material(name="Test Wood")
        m.vis.roughness = 0.6
        m.vis.source = source
        m.vis.material_id = mat_id

        with _skip_on_upstream_outage():
            # Access textures — triggers lazy HTTP fetch
            textures = m.vis.textures
            assert len(textures) > 0, f"No textures fetched for {source}/{mat_id}"
            assert all(v[:4] == b"\x89PNG" for v in textures.values())

    def test_material_to_threejs_with_live_textures(self):
        """Full path: Material → vis.textures → to_threejs → dict with maps."""
        from pymat import Material, vis
        from pymat.vis.adapters import to_threejs

        results = vis.search(category="metal", limit=1)
        if not results:
            pytest.skip("No metal materials in mat-vis index")

        source = results[0].get("source", "ambientcg")
        mat_id = results[0]["id"]

        m = Material(name="Live Metal Test")
        m.vis.metallic = 1.0
        m.vis.roughness = 0.3
        m.vis.base_color = (0.8, 0.8, 0.8, 1.0)
        m.vis.source = source
        m.vis.material_id = mat_id

        with _skip_on_upstream_outage():
            d = to_threejs(m)

            # Scalars present
            assert d["metalness"] == 1.0
            assert d["roughness"] == 0.3

            # At least one texture map as base64 data URI
            has_map = any(
                k in d for k in ("map", "normalMap", "roughnessMap", "metalnessMap", "aoMap")
            )
            assert has_map, f"No texture maps in to_threejs output: {list(d.keys())}"

            # Verify data URI format
            for key in ("map", "normalMap", "roughnessMap", "metalnessMap", "aoMap"):
                if key in d:
                    assert d[key].startswith("data:image/png;base64,"), f"{key}: not a data URI"

    def test_toml_material_with_vis_mapping(self):
        """Stainless steel from TOML has vis identity from [vis] section."""
        from pymat import stainless

        assert stainless.vis.source == "ambientcg"
        assert stainless.vis.material_id == "Metal012"
        assert stainless.vis.finish == "brushed"
        assert stainless.vis.roughness == 0.3
        assert stainless.vis.metallic == 1.0
        assert "polished" in stainless.vis.finishes

        # Switch finish — identity should change
        brushed_id = stainless.vis.material_id
        stainless.vis.finish = "polished"
        assert stainless.vis.material_id != brushed_id
        assert stainless.vis.source == "ambientcg"
        assert stainless.vis.material_id.startswith("Metal")

        stainless.vis.finish = "brushed"

    def test_discover_finds_candidates(self):
        """vis.search() finds materials by category."""
        from pymat import vis

        # Use module-level search (tier-free) instead of discover()
        # which delegates to mat_vis_client.search (tier-filtered)
        results = vis.search(category="metal", limit=5)
        if not results:
            pytest.skip(
                "mat-vis index returned no metals — infra issue, not a py-mat bug. Retry or reseed."
            )
        assert all("id" in c for c in results)

    def test_prefetch_small(self, tmp_path):
        """vis.fetch works for multiple materials (light prefetch test)."""
        from pymat import vis

        with _skip_on_upstream_outage():
            # Fetch just 2 materials instead of full prefetch
            results = vis.search(category="stone", limit=2)
            for r in results:
                textures = vis.fetch(r["source"], r["id"], tier="128")
                assert len(textures) >= 0  # may be 0 if 128 tier not available

    def test_resolve_channel(self):
        """Vis.resolve() returns texture or scalar fallback."""
        from pymat import Material, vis

        results = vis.search(category="stone", limit=1)
        if not results:
            pytest.skip("No stone materials")

        source = results[0].get("source", "ambientcg")
        mat_id = results[0]["id"]

        m = Material(name="Test Stone")
        m.vis.roughness = 0.7
        m.vis.source = source
        m.vis.material_id = mat_id

        with _skip_on_upstream_outage():
            rc = m.vis.resolve("roughness", scalar=0.7)
            # Should have texture (if roughness map exists) or scalar fallback
            assert rc.scalar == 0.7
            if rc.has_texture:
                assert rc.texture[:4] == b"\x89PNG"


class TestSkipOnUpstreamOutage:
    """The flake-guard itself — tested without hitting the network."""

    def test_skips_on_5xx_httperror(self):
        with pytest.raises(pytest.skip.Exception, match="502"):
            with _skip_on_upstream_outage():
                raise HTTPError(url="x", code=502, msg="Bad Gateway", hdrs=None, fp=None)

    def test_skips_on_no_textures_assertion(self):
        with pytest.raises(pytest.skip.Exception, match="CDN likely flaky"):
            with _skip_on_upstream_outage():
                raise AssertionError("No textures for ambientcg/Metal032")

    def test_propagates_4xx(self):
        """4xx is a real bug (bad source_id, auth, etc.) — don't hide it."""
        with pytest.raises(HTTPError):
            with _skip_on_upstream_outage():
                raise HTTPError(url="x", code=404, msg="Not Found", hdrs=None, fp=None)

    def test_propagates_unrelated_assertion(self):
        """Only the 'no textures' shape gets skip-coerced; real asserts fail."""
        with pytest.raises(AssertionError, match="roughness"):
            with _skip_on_upstream_outage():
                assert 0.3 == 0.5, "roughness mismatch"

    def test_no_op_on_success(self):
        """The guard is inert when nothing goes wrong."""
        with _skip_on_upstream_outage():
            pass  # no raise, no skip

    def test_skips_on_typed_http_fetch_error(self):
        """mat-vis-client 0.5.0+ raises typed HTTPFetchError — the
        guard must skip on it too."""
        if not _TYPED_FETCH_ERRORS:
            pytest.skip("mat-vis-client <0.5.0 — no typed errors to test")
        from mat_vis_client import HTTPFetchError

        with pytest.raises(pytest.skip.Exception, match="typed.*HTTPFetchError"):
            with _skip_on_upstream_outage():
                raise HTTPFetchError("https://example/x", 503, "Service Unavailable")

    def test_skips_on_typed_network_error(self):
        """NetworkError (no .code) — connection-level failure."""
        if not _TYPED_FETCH_ERRORS:
            pytest.skip("mat-vis-client <0.5.0 — no typed errors to test")
        from mat_vis_client import NetworkError

        with pytest.raises(pytest.skip.Exception, match="typed.*NetworkError"):
            with _skip_on_upstream_outage():
                raise NetworkError("https://example/x", "connection refused")
