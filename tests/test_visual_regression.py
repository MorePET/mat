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
