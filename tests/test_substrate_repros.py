"""Literal repros from filed mat-vis upstream issues — kept as strict
xfails until upstream ships fixes.

Catches the verification gap where py-mat's own tests pass cleanly but
the substrate's actual behavior is broken from a consumer's vantage
(see build123d#1270 #issuecomment-4396717XXX). Each test class wraps a
specific filed issue's repro snippet; when the upstream fix lands and
``mat-vis-client`` ships a release that py-mat picks up, the test
``XPASS``es and the strict marker fires — reminder to drop the xfail.

Network-dependent: hits real mat-vis substrate. Skip with
``MAT_VIS_SKIP_LIVE=1``. Transient CDN failures are turned into
``pytest.skip`` so a flaky upstream doesn't mask real regressions.
"""

from __future__ import annotations

import os
import re
from contextlib import contextmanager
from urllib.error import HTTPError

import pytest

SKIP_LIVE = os.environ.get("MAT_VIS_SKIP_LIVE", "0") == "1"

try:
    from mat_vis_client import HTTPFetchError, NetworkError

    _TYPED_FETCH_ERRORS: tuple[type[Exception], ...] = (HTTPFetchError, NetworkError)
except ImportError:  # pragma: no cover
    _TYPED_FETCH_ERRORS = ()


@contextmanager
def _skip_on_upstream_outage():
    """Mirror of ``test_e2e_vis._skip_on_upstream_outage``. Kept local
    here so this file can be read as a self-contained "filed-issue
    repros" record without cross-test-file imports."""
    try:
        yield
    except HTTPError as exc:
        if 500 <= exc.code < 600:
            pytest.skip(f"mat-vis CDN outage: {exc.code} {exc.reason}")
        raise
    except _TYPED_FETCH_ERRORS as exc:
        code = getattr(exc, "code", "?")
        pytest.skip(f"mat-vis CDN outage (typed): {type(exc).__name__} code={code}")


pytestmark = pytest.mark.skipif(SKIP_LIVE, reason="MAT_VIS_SKIP_LIVE=1")


# ────────────────────────────────────────────────────────────────────
# mat-vis #285 — gpuopen baking returns default scalars
# https://github.com/MorePET/mat-vis/issues/285
# ────────────────────────────────────────────────────────────────────


class TestMatVis285_GpuopenBakingScalars:
    """Several gpuopen materials return default PBR scalars
    (``metalness=0.0``, ``roughness=0.5``, ``color=0xCCCCCC``,
    ``ior=1.5``, ``transmission=0.0``) instead of the values authored
    in the source ``.mtlx``. Visually these render as flat grey
    plastic — see Bernhard's screenshot pair in the issue.

    The repro-shaped contract: two distinct gpuopen metals must NOT
    return identical default scalars. ``Aluminum Brushed`` and
    ``Bronze Oxydized`` should differ in at least one of {metalness,
    color, roughness} once the baker preserves authored scalars.
    """

    def test_gpuopen_metals_have_distinct_scalars(self):
        from pymat.vis import Vis

        with _skip_on_upstream_outage():
            alu = Vis(source="gpuopen", material_id="Aluminum Brushed", tier="1k").to_threejs()
            bronze = Vis(source="gpuopen", material_id="Bronze Oxydized", tier="1k").to_threejs()

        # Default-grey-plastic fingerprint: metalness=0.0, roughness=0.5,
        # color=0xCCCCCC. If both materials match this, the baker is
        # emitting defaults rather than preserved scalars.
        DEFAULT_GREY = 0xCCCCCC
        alu_default = (
            alu.get("metalness") == 0.0
            and alu.get("roughness") == 0.5
            and alu.get("color") in (DEFAULT_GREY, "#cccccc", "#CCCCCC")
        )
        bronze_default = (
            bronze.get("metalness") == 0.0
            and bronze.get("roughness") == 0.5
            and bronze.get("color") in (DEFAULT_GREY, "#cccccc", "#CCCCCC")
        )
        assert not (alu_default and bronze_default), (
            f"both materials emit baker-default scalars — alu={alu}, bronze={bronze}"
        )


# ────────────────────────────────────────────────────────────────────
# mat-vis #311 — client.materials() returns IDs/UUIDs, not webpage names
# https://github.com/MorePET/mat-vis/issues/311
# ────────────────────────────────────────────────────────────────────


class TestMatVis311_MaterialNames:
    """``client.materials(source, tier)`` should return human-readable
    names (or a {id: name} mapping), not raw IDs / UUIDs. For gpuopen
    today it returns 36-char UUIDs that no user will recognize.

    Tested via the gpuopen path because the UUID format is the
    sharpest assertion (regex match). ambientCG and polyhaven also
    have ID-like outputs but the bound between "ID" and "name" is
    fuzzier there.
    """

    UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

    @pytest.mark.xfail(
        reason=(
            "mat-vis #311: client.materials('gpuopen', '1k') returns "
            "raw UUIDs instead of webpage-visible names. Will flip to "
            "passing when the client returns names (or {uuid: name}) "
            "for human selection."
        ),
        strict=True,
    )
    def test_gpuopen_listing_is_not_uuids(self):
        from mat_vis_client import get_client

        client = get_client()
        with _skip_on_upstream_outage():
            entries = client.materials("gpuopen", "1k")

        assert entries, "no gpuopen materials returned"
        sample = entries[: min(10, len(entries))]
        uuid_count = sum(1 for e in sample if self.UUID_RE.match(str(e)))
        assert uuid_count == 0, (
            f"{uuid_count}/{len(sample)} gpuopen entries are bare UUIDs "
            f"(e.g. {sample[0]!r}) — users select by webpage names, not UUIDs"
        )


# ────────────────────────────────────────────────────────────────────
# mat-vis #313 — Vis("physicallybased", X).to_threejs() raises
# https://github.com/MorePET/mat-vis/issues/313
# ────────────────────────────────────────────────────────────────────


class TestMatVis313_PhysicallybasedAccess:
    """``Vis(source='physicallybased', material_id='Aluminum').to_threejs()``
    must not raise. mat-vis #313 was the upstream symptom (substrate
    path treated physicallybased like a textured source); py-mat #222
    closed the consumer-facing manifestation by auto-resolving
    ``tier`` to ``"scalar"`` when the source's manifest only ships a
    scalar tier, then short-circuiting the texture fetch in
    ``Vis._fetch``.

    The test passes today thanks to the py-mat-side handling. The
    upstream issue stays open until mat-vis ships a release that
    unbreaks the substrate path natively — but consumers don't see
    that bug anymore because we route around it.
    """

    def test_physicallybased_aluminum_to_threejs(self):
        from pymat.vis import Vis

        with _skip_on_upstream_outage():
            v = Vis(source="physicallybased", material_id="Aluminum")
            # Auto-resolution should land tier on "scalar" without the
            # caller asking — the whole point of #222's fix.
            assert v.tier == "scalar", f"tier auto-resolution failed: {v.tier!r}"
            out = v.to_threejs()

        # Just assert it doesn't raise + returns a usable dict — the
        # specific values are the substrate's call.
        assert isinstance(out, dict)
        assert out.get("type") == "MeshPhysicalMaterial"
