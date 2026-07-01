"""Visual regression tests — headless Three.js rendering via Playwright.

Proves the full pipeline:
    pymat.Material → .vis → to_threejs → build123d export_gltf → Three.js render → screenshot

Uses a self-contained HTML viewer (tests/visual_render.html) that loads
Three.js from CDN + our exported glTF. No ocp_vscode needed.

Requirements:
    pip install playwright build123d
    python -m playwright install chromium

Skip with: MAT_VIS_SKIP_VISUAL=1 (default)
Run:   MAT_VIS_SKIP_VISUAL=0 pytest tests/test_visual_regression.py -v -s
"""

from __future__ import annotations

import http.server
import json
import os
import shutil
import threading
from pathlib import Path

import pytest

SKIP_VISUAL = os.environ.get("MAT_VIS_SKIP_VISUAL", "1") == "1"
OUTPUT_DIR = Path(__file__).parent / "visual_output"
RENDER_HTML = Path(__file__).parent / "visual_render.html"


@pytest.fixture(scope="module")
def file_server():
    """Serve test files (HTML + glTF) on localhost."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(OUTPUT_DIR), **kwargs)

        def log_message(self, *args):
            pass  # silence

    # Copy render HTML to output dir
    import shutil

    shutil.copy(RENDER_HTML, OUTPUT_DIR / "index.html")

    port = 8765
    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


@pytest.fixture(scope="module")
def browser():
    """Launch headless Chromium."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("playwright not installed")

    pw = sync_playwright().start()
    b = pw.chromium.launch(headless=True, args=["--use-gl=swiftshader"])
    yield b
    b.close()
    pw.stop()


def _render_and_screenshot(browser, server_url: str, glb_path: Path, name: str) -> Path:
    """Load a glTF in the Three.js viewer, wait for render, extract canvas."""
    import base64

    out = OUTPUT_DIR / f"{name}.png"

    page = browser.new_page(viewport={"width": 800, "height": 600})
    page.goto(f"{server_url}/index.html?gltf={glb_path.name}")

    # Wait for Three.js to signal render complete
    page.wait_for_function("window.__renderComplete === true", timeout=15000)
    page.wait_for_timeout(500)

    # Extract canvas content directly (more reliable than page screenshot)
    data_url = page.evaluate('document.querySelector("canvas").toDataURL("image/png")')
    png_bytes = base64.b64decode(data_url.split(",")[1])
    out.write_bytes(png_bytes)

    page.close()
    return out


@pytest.mark.skipif(SKIP_VISUAL, reason="MAT_VIS_SKIP_VISUAL=1 (default)")
class TestHeadlessRender:
    """Full pipeline: Material → glTF → Three.js headless → screenshot."""

    def test_steel_cube(self, file_server, browser):
        """Metallic steel cube with PBR scalars."""
        from build123d import Box, export_gltf

        from pymat import Material

        shape = Box(10, 10, 10)
        m = Material(name="Steel")
        m.vis.metallic = 1.0
        m.vis.roughness = 0.3
        m.vis.base_color = (0.8, 0.8, 0.8, 1.0)
        shape.material = m

        glb = OUTPUT_DIR / "steel_cube.glb"
        export_gltf(shape, str(glb))
        assert glb.exists()

        screenshot = _render_and_screenshot(browser, file_server, glb, "steel_cube")
        assert screenshot.exists()
        size = screenshot.stat().st_size
        assert size > 5000, f"Screenshot too small ({size} bytes) — likely blank"
        print(f"steel_cube: {size} bytes")

        from tests._visual_compare import assert_matches_baseline

        assert_matches_baseline(screenshot, "steel_cube")

    def test_red_sphere(self, file_server, browser):
        """Red dielectric sphere."""
        from build123d import Sphere, export_gltf

        from pymat import Material

        shape = Sphere(8)
        m = Material(name="Red Plastic")
        m.vis.metallic = 0.0
        m.vis.roughness = 0.5
        m.vis.base_color = (0.8, 0.1, 0.1, 1.0)
        shape.material = m

        glb = OUTPUT_DIR / "red_sphere.glb"
        export_gltf(shape, str(glb))

        screenshot = _render_and_screenshot(browser, file_server, glb, "red_sphere")
        assert screenshot.exists()
        size = screenshot.stat().st_size
        assert size > 5000, f"Screenshot too small ({size} bytes)"
        print(f"red_sphere: {size} bytes")

        from tests._visual_compare import assert_matches_baseline

        assert_matches_baseline(screenshot, "red_sphere")

    def test_gold_cylinder(self, file_server, browser):
        """Gold metallic cylinder."""
        from build123d import Cylinder, export_gltf

        from pymat import Material

        shape = Cylinder(5, 15)
        m = Material(name="Gold")
        m.vis.metallic = 1.0
        m.vis.roughness = 0.2
        m.vis.base_color = (1.0, 0.84, 0.0, 1.0)
        shape.material = m

        glb = OUTPUT_DIR / "gold_cylinder.glb"
        export_gltf(shape, str(glb))

        screenshot = _render_and_screenshot(browser, file_server, glb, "gold_cylinder")
        assert screenshot.exists()
        size = screenshot.stat().st_size
        assert size > 5000
        print(f"gold_cylinder: {size} bytes")

        from tests._visual_compare import assert_matches_baseline

        assert_matches_baseline(screenshot, "gold_cylinder")

    def test_glass_transmission(self, file_server, browser):
        """Transparent glass sphere."""
        from build123d import Sphere, export_gltf

        from pymat import Material

        shape = Sphere(10)
        m = Material(name="Glass")
        m.vis.metallic = 0.0
        m.vis.roughness = 0.0
        m.vis.base_color = (0.95, 0.95, 1.0, 0.3)
        m.vis.ior = 1.52
        m.vis.transmission = 0.9
        shape.material = m

        glb = OUTPUT_DIR / "glass_sphere.glb"
        export_gltf(shape, str(glb))

        screenshot = _render_and_screenshot(browser, file_server, glb, "glass_sphere")
        assert screenshot.exists()
        size = screenshot.stat().st_size
        assert size > 3000
        print(f"glass_sphere: {size} bytes")

    def test_multi_material_assembly(self, file_server, browser):
        """Assembly with different materials per part."""
        from build123d import Box, Compound, Cylinder, Pos, export_gltf

        from pymat import Material

        base = Box(20, 20, 3)
        m_base = Material(name="Wood Base")
        m_base.vis.metallic = 0.0
        m_base.vis.roughness = 0.7
        m_base.vis.base_color = (0.6, 0.4, 0.2, 1.0)
        base.material = m_base

        pin = Pos(0, 0, 10) * Cylinder(3, 14)
        m_pin = Material(name="Chrome Pin")
        m_pin.vis.metallic = 1.0
        m_pin.vis.roughness = 0.1
        m_pin.vis.base_color = (0.9, 0.9, 0.9, 1.0)
        pin.material = m_pin

        assembly = Compound(children=[base, pin])

        glb = OUTPUT_DIR / "assembly.glb"
        export_gltf(assembly, str(glb))

        screenshot = _render_and_screenshot(browser, file_server, glb, "assembly")
        assert screenshot.exists()
        size = screenshot.stat().st_size
        assert size > 5000
        print(f"assembly: {size} bytes")


@pytest.mark.skipif(SKIP_VISUAL, reason="MAT_VIS_SKIP_VISUAL=1 (default)")
class TestAdapterOutput:
    """Verify adapter dict output (no rendering needed)."""

    def test_to_threejs_scalars(self):
        from pymat import Material
        from pymat.vis.adapters import to_threejs

        m = Material(name="Steel")
        m.vis.metallic = 1.0
        m.vis.roughness = 0.3
        m.vis.base_color = (0.8, 0.8, 0.8, 1.0)

        d = to_threejs(m)
        assert d["metalness"] == 1.0
        assert d["roughness"] == 0.3

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / "steel_threejs.json").write_text(json.dumps(d, indent=2, default=str))

    def test_to_threejs_with_textures(self):
        from pymat import Material, vis
        from pymat.vis.adapters import to_threejs

        results = vis.search(category="metal", limit=1)
        if not results:
            pytest.skip("No metals in mat-vis")

        m = Material(name="Textured Metal")
        m.vis.metallic = 1.0
        m.vis.roughness = 0.3
        m.vis.source = results[0]["source"]
        m.vis.material_id = results[0]["id"]

        d = to_threejs(m)
        has_map = any(k in d for k in ("map", "normalMap", "roughnessMap", "metalnessMap"))

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        summary = {
            k: (v[:60] + "..." if isinstance(v, str) and len(v) > 60 else v) for k, v in d.items()
        }
        (OUTPUT_DIR / "metal_textured_threejs.json").write_text(
            json.dumps(summary, indent=2, default=str)
        )

        if has_map:
            assert d[next(k for k in ("map", "normalMap") if k in d)].startswith(
                "data:image/png;base64,"
            )


# ────────────────────────────────────────────────────────────────────
# mat-vis #285 multi-material grid — comprehensive matrix
# https://github.com/MorePET/mat-vis/issues/285
# ────────────────────────────────────────────────────────────────────


# Textured-source 24-material grid. Each entry: (label, source,
# material_id). Texture-scale + colour overrides from the original
# repro are not represented here — they're per-instance render state
# on the build123d side, not py-mat Vis attributes (see py-mat #93 /
# the texture_scale discussion in build123d#1270).
TEXTURED_REGRESSION_GRID: list[tuple[str, str, str]] = [
    ("car_red", "gpuopen", "Car Paint"),
    ("car_green", "gpuopen", "Car Paint"),
    ("bronze", "gpuopen", "Bronze Oxydized"),
    ("chrome", "gpuopen", "Chrome"),
    ("glass", "gpuopen", "Glass"),
    ("red_wine", "gpuopen", "Red Wine"),
    ("gold", "gpuopen", "Gold"),
    ("carbon_coat", "gpuopen", "Carbon biColor Coat"),
    ("steel", "gpuopen", "Stainless Steel Brushed"),
    ("alu", "gpuopen", "Aluminum Brushed"),
    ("bricks", "gpuopen", "TH: Large Red Bricks"),
    ("leather", "gpuopen", "TH: Brown Fabric Leather"),
    ("alu_corr", "gpuopen", "Aluminum Corrugated"),
    ("alu_hexagon", "gpuopen", "Aluminum Hexagon"),
    ("perforated", "gpuopen", "Perforated Metal"),
    ("wood", "gpuopen", "Ivory Walnut Solid Wood"),
    ("tiles", "gpuopen", "Iberian Blue Ceramic Tiles"),
    ("tiles2", "gpuopen", "Tiles Black Long Variative"),
    ("brass_scratched", "ambientcg", "Metal 007"),
    ("carbon", "ambientcg", "Fabric 004"),
    ("plates", "ambientcg", "Metal Plates 006"),
    ("floor", "gpuopen", "Adelie Brown Luxury Flooring"),
    ("plank", "polyhaven", "Plank Flooring 03"),
    ("rock_wall", "polyhaven", "Rock Wall 16"),
]

# Scalar-only physicallybased.info entries. No textures — just authored
# PBR scalars. The original mat-vis #285 repro snippet only includes
# acryl from this source; the broader set below exercises the scalar
# path more fully so regressions on physicallybased aren't hidden
# behind a single material.
SCALAR_ONLY_REGRESSION_GRID: list[tuple[str, str]] = [
    ("acryl", "Plastic (Acrylic)"),
    ("alu_pbr", "Aluminum"),
    ("gold_pbr", "Gold"),
    ("iron_pbr", "Iron"),
    ("copper_pbr", "Copper"),
]

# Tiers offered by the mat-vis substrate — pulled from client.tiers().
# 'scalar' is the catch-all for sources that don't ship texture maps
# (physicallybased.info). The KTX2 tiers ship Basis-encoded textures
# instead of PNG.
TIERS_TEXTURED = ["1k", "512", "256", "ktx2-1k", "ktx2-512"]
TIERS_SCALAR = ["scalar"]

# Default-grey-plastic fingerprint per mat-vis #285 — the recipe a
# regressed gpuopen baker emits when authored .mtlx scalars never made
# it into the rowmap. If 25 materials all match this, the substrate
# data has not been re-baked with the fix from PR mat-vis#294.
_DEFAULT_GREY_INTS = {0xCCCCCC}
_DEFAULT_GREY_HEX = {"#cccccc", "#CCCCCC"}


def _is_default_grey(scalars: dict) -> bool:
    return (
        scalars.get("metalness") in (0.0, None)
        and scalars.get("roughness") in (0.5, None)
        and (
            scalars.get("color") in _DEFAULT_GREY_INTS
            or scalars.get("color") in _DEFAULT_GREY_HEX
            or scalars.get("color") is None
        )
    )


# ── 1. Adapter structure — textured sources × tiers ─────────────


@pytest.mark.skipif(SKIP_VISUAL, reason="MAT_VIS_SKIP_VISUAL=1 (default)")
class TestMatVis285_AdapterStructure_Textured:
    """Per-tier × per-adapter structural validation of the textured
    portion of the mat-vis #285 regression grid.

    Catches API drift in either direction: an adapter dropping a key
    from its output, a tier silently disappearing from the substrate,
    or the scalar regression documented in mat-vis #285.

    The scalar assertion (≥5 of 24 materials emit non-default scalars)
    is the headline #285 catch — strict-xfail until the substrate
    re-bakes with the fix from PR mat-vis#294.
    """

    @pytest.mark.parametrize("adapter", ["to_threejs", "to_gltf"])
    @pytest.mark.parametrize("tier", TIERS_TEXTURED)
    @pytest.mark.xfail(
        reason=(
            "mat-vis #285: gpuopen baker drops authored .mtlx scalars; "
            "most metals render with default scalars (metalness=0.0, "
            "roughness=0.5, color=#cccccc). PR mat-vis#294 fixed the "
            "baker code; test flips green when substrate re-bakes and "
            "py-mat's >=mat-vis-client constraint pulls in the new release."
        ),
        strict=True,
    )
    def test_textured_adapter_structure_at_tier(self, adapter: str, tier: str) -> None:
        from pymat.vis import Vis, to_gltf, to_threejs

        adapter_fn = {"to_threejs": to_threejs, "to_gltf": to_gltf}[adapter]
        non_default = 0
        skipped: list[str] = []

        for label, source, material_id in TEXTURED_REGRESSION_GRID:
            try:
                v = Vis(source=source, material_id=material_id, tier=tier)
                out = adapter_fn(v)
            except Exception as exc:
                skipped.append(f"{label}: {type(exc).__name__}")
                continue

            assert isinstance(out, dict), (
                f"{adapter}({label}) must return dict, got {type(out).__name__}"
            )
            # Adapter-specific shape check
            if adapter == "to_threejs":
                assert out.get("type") == "MeshPhysicalMaterial", (
                    f"{label}: to_threejs missing/wrong 'type', got {out.get('type')!r}"
                )
            else:  # to_gltf
                assert "pbrMetallicRoughness" in out, (
                    f"{label}: to_gltf missing 'pbrMetallicRoughness' block"
                )

            # Scalar fingerprint check: gather the relevant scalars in a
            # uniform shape regardless of which adapter we used.
            if adapter == "to_threejs":
                scalars = {
                    "metalness": out.get("metalness"),
                    "roughness": out.get("roughness"),
                    "color": out.get("color"),
                }
            else:
                pbr = out.get("pbrMetallicRoughness", {})
                scalars = {
                    "metalness": pbr.get("metallicFactor"),
                    "roughness": pbr.get("roughnessFactor"),
                    "color": pbr.get("baseColorFactor"),
                }

            if not _is_default_grey(scalars):
                non_default += 1

        assert non_default >= 5, (
            f"only {non_default}/{len(TEXTURED_REGRESSION_GRID) - len(skipped)} textured "
            f"materials at tier={tier} via {adapter} have non-default scalars "
            f"(skipped={len(skipped)} due to substrate cache misses) — "
            "mat-vis #285 baker regression"
        )


# ── 2. Adapter structure — scalar-only physicallybased ──────────


@pytest.mark.skipif(SKIP_VISUAL, reason="MAT_VIS_SKIP_VISUAL=1 (default)")
class TestMatVis285_AdapterStructure_Scalar:
    """The physicallybased.info path is scalar-only — no texture maps,
    just authored PBR scalars. Closed by py-mat #222 (PR #225) which
    auto-resolves ``tier`` to ``"scalar"`` for sources whose manifest
    only ships a scalar tier and short-circuits ``Vis._fetch`` to
    skip texture fetching. Upstream mat-vis #313 stays open as the
    substrate-path fix; py-mat consumers no longer hit the symptom.
    """

    @pytest.mark.parametrize("adapter", ["to_threejs", "to_gltf"])
    @pytest.mark.parametrize("label,material_id", SCALAR_ONLY_REGRESSION_GRID)
    def test_scalar_only_adapter(self, adapter: str, label: str, material_id: str) -> None:
        from pymat.vis import Vis, to_gltf, to_threejs

        adapter_fn = {"to_threejs": to_threejs, "to_gltf": to_gltf}[adapter]
        v = Vis(source="physicallybased", material_id=material_id)
        out = adapter_fn(v)

        assert isinstance(out, dict)
        if adapter == "to_threejs":
            assert out.get("type") == "MeshPhysicalMaterial"
            # Scalar-only materials must surface at least the canonical
            # PBR scalars; texture maps are absent by definition.
            assert any(k in out for k in ("metalness", "roughness", "color")), (
                f"{label}: no PBR scalars in to_threejs output"
            )
        else:
            assert "pbrMetallicRoughness" in out


# ── 3. KTX2 tier byte-shape ─────────────────────────────────────


@pytest.mark.skipif(SKIP_VISUAL, reason="MAT_VIS_SKIP_VISUAL=1 (default)")
class TestMatVis285_Ktx2Bytes:
    """At ``tier='ktx2-1k'``, texture bytes must be KTX2-encoded — not
    PNG. Catches a substrate regression where the KTX2 path silently
    falls back to PNG (consumers expecting Basis transcoding break).

    The KTX2 magic header is the 12 bytes ``«KTX 20»\\r\\n\\x1a\\n`` —
    a simple bytes-prefix check is enough to distinguish it from PNG
    (``\\x89PNG\\r\\n\\x1a\\n``).
    """

    KTX2_MAGIC = b"\xabKTX 20\xbb\r\n\x1a\n"

    def test_ktx2_tier_returns_ktx2_bytes(self) -> None:
        from pymat.vis import Vis

        # Pick a known textured material; ambientcg's Metal 007 is in
        # the regression grid and the catalog ships it across tiers.
        v = Vis(source="ambientcg", material_id="Metal 007", tier="ktx2-1k")
        textures = v.textures
        if not textures:
            pytest.skip("no textures returned at ktx2-1k (substrate cache miss)")

        # Pick any channel with bytes
        sample_key = next(iter(textures))
        sample_bytes = textures[sample_key]
        assert isinstance(sample_bytes, bytes)
        assert sample_bytes.startswith(self.KTX2_MAGIC), (
            f"texture channel {sample_key!r} at tier=ktx2-1k did not start with "
            f"KTX2 magic header — first 12 bytes: {sample_bytes[:12]!r}"
        )


# ── 4. MaterialX export ─────────────────────────────────────────


@pytest.mark.skipif(SKIP_VISUAL, reason="MAT_VIS_SKIP_VISUAL=1 (default)")
class TestMatVis285_MtlxExport:
    """``Vis.mtlx.export(dir)`` writes a self-contained .mtlx package:
    a MaterialX XML document plus PNG channel files. Validates the XML
    structure without running an actual MaterialX renderer.

    Doesn't exercise visual fidelity — that's a downstream concern
    for renderers (USD, Maya, Blender). Just structural integrity.
    """

    def test_mtlx_export_produces_parseable_xml(self, tmp_path) -> None:
        import xml.etree.ElementTree as ET

        from pymat.vis import Vis

        v = Vis(source="ambientcg", material_id="Metal 007", tier="1k")
        try:
            mtlx_path = v.mtlx.export(tmp_path)
        except Exception as exc:
            pytest.skip(f"mtlx export not available / cache miss: {exc}")

        assert mtlx_path.exists(), f"export returned {mtlx_path} but file missing"
        assert mtlx_path.suffix == ".mtlx"

        tree = ET.parse(mtlx_path)
        root = tree.getroot()
        # MaterialX root element is <materialx version="...">
        assert root.tag.endswith("materialx") or root.tag == "materialx", (
            f"root element should be <materialx>, got <{root.tag}>"
        )

        # At minimum: one <surfacematerial> defining the material itself
        surfacematerials = [e for e in root.iter() if e.tag.endswith("surfacematerial")]
        assert surfacematerials, "no <surfacematerial> nodes in mtlx export"

        # If textures are present, they must be referenced via <image>
        # nodes whose file= attribute points at a real PNG sibling.
        images = [e for e in root.iter() if e.tag.endswith("image")]
        for img in images:
            file_attr = img.get("file") or img.findtext(".//*[@name='file']")
            if file_attr:
                # Resolve relative to the mtlx path
                tex_path = mtlx_path.parent / file_attr
                assert tex_path.exists(), (
                    f"<image file={file_attr!r}> references missing file at {tex_path}"
                )


# ── 5. Visual grid — programmatic Three.js scene via to_threejs ─


@pytest.mark.skipif(SKIP_VISUAL, reason="MAT_VIS_SKIP_VISUAL=1 (default)")
class TestMatVis285_Visual:
    """Renders the regression grid via headless Three.js, **bypassing
    build123d's glTF exporter entirely**. Material specs come from
    ``pymat.vis.to_threejs(vis)`` per material; the JS-side viewer
    instantiates ``THREE.MeshPhysicalMaterial`` directly. Sphere
    geometry is created in JS (not exported from build123d).

    This isolates py-mat's substrate → adapter → renderer pipeline
    so the artifact reflects py-mat's surface only — not build123d's
    glTF-export gap (separate concern; py-mat is purely upstream of
    that).

    Output: one PNG per (tier × scene) combination, plus a sidecar
    JSON with the materials' scalars + texture key presence — small
    enough to read; texture data URIs stripped.

    Strict-xfail today; flips green when mat-vis ships PR
    mat-vis#294's baker fix and the substrate is re-baked.
    """

    GRID_COLS = 5

    # Per-param xfail: textured tiers remain strict-xfail until the
    # mat-vis #285 substrate re-bake ships; the scalar-only path was
    # closed by py-mat #225 (#222 fix), so its param is just expected
    # to pass.
    _TEXTURED_XFAIL = pytest.mark.xfail(
        reason=(
            "mat-vis #285: textured-scene PNG renders default-grey because "
            "the substrate emits default scalars. Strict-xfail until "
            "upstream re-bakes the substrate with PR mat-vis#294's baker fix."
        ),
        strict=True,
    )

    @pytest.mark.parametrize(
        "scene_kind,tier",
        [
            pytest.param("textured", "1k", marks=_TEXTURED_XFAIL),
            pytest.param("textured", "512", marks=_TEXTURED_XFAIL),
            pytest.param("textured", "256", marks=_TEXTURED_XFAIL),
            ("scalar", "scalar"),  # passes — closed by #225 (#222 fix)
        ],
    )
    def test_grid_renders_at_tier(self, file_server, browser, scene_kind: str, tier: str) -> None:
        from pymat.vis import Vis, to_threejs

        # Build the spec list
        items = []
        if scene_kind == "textured":
            for idx, (label, source, material_id) in enumerate(TEXTURED_REGRESSION_GRID):
                row = idx // self.GRID_COLS
                col = idx % self.GRID_COLS
                v = Vis(source=source, material_id=material_id, tier=tier)
                items.append({"label": label, "row": row, "col": col, "threejs": to_threejs(v)})
        else:  # scalar
            for idx, (label, material_id) in enumerate(SCALAR_ONLY_REGRESSION_GRID):
                row = idx // self.GRID_COLS
                col = idx % self.GRID_COLS
                v = Vis(source="physicallybased", material_id=material_id)
                items.append({"label": label, "row": row, "col": col, "threejs": to_threejs(v)})

        spec_path = OUTPUT_DIR / f"mat_vis_285_grid_{scene_kind}_{tier}.spec.json"
        # Write the full spec WITH texture data URIs (the renderer needs them)
        spec_path.write_text(json.dumps({"tier": tier, "kind": scene_kind, "items": items}))

        # Persist a stripped sidecar (no inline texture URIs) for
        # human review of what each ball reports
        stripped = []
        for it in items:
            sc = dict(it["threejs"])
            for k in list(sc.keys()):
                if isinstance(sc[k], str) and len(sc[k]) > 200:
                    sc[k] = f"<stripped {len(sc[k])} chars>"
            stripped.append(
                {"label": it["label"], "row": it["row"], "col": it["col"], "scalars": sc}
            )
        (OUTPUT_DIR / f"mat_vis_285_grid_{scene_kind}_{tier}.scalars.json").write_text(
            json.dumps(stripped, indent=2, default=str)
        )

        # Render via the programmatic JS viewer
        viewer_html = Path(__file__).parent / "visual_grid_render.html"
        shutil.copy(viewer_html, OUTPUT_DIR / "grid.html")

        url = f"{file_server}/grid.html?spec={spec_path.name}"
        page = browser.new_page(viewport={"width": 1600, "height": 1200}, device_scale_factor=2)
        page.goto(url, timeout=180_000)
        page.wait_for_function("() => window.__renderComplete === true", timeout=300_000)
        page.wait_for_timeout(8_000)  # let textures settle

        # canvas.toDataURL bypasses Playwright's slow compositor screenshot
        data_url = page.evaluate("() => document.querySelector('canvas').toDataURL('image/png')")
        png = OUTPUT_DIR / f"mat_vis_285_grid_{scene_kind}_{tier}.png"
        import base64

        png.write_bytes(base64.b64decode(data_url.split(",", 1)[1]))
        page.close()

        assert png.stat().st_size > 5_000, (
            f"render too small ({png.stat().st_size} bytes) — likely blank canvas"
        )

        # The actual #285 assertion mirrors the structure tests: at
        # least 5 textured materials must have non-default scalars.
        # Scalar-only scene asserts no MaterialNotStagedError surfaced
        # (handled implicitly — if it had, items list would be empty).
        if scene_kind == "textured":
            non_default = sum(1 for it in items if not _is_default_grey(it["threejs"]))
            assert non_default >= 5, (
                f"only {non_default}/{len(items)} textured materials have non-default "
                f"scalars at tier={tier} — mat-vis #285 regression. See "
                f"mat_vis_285_grid_textured_{tier}.png + .scalars.json artifacts."
            )
        else:
            assert items, "scalar scene produced no items — physicallybased path broken"
