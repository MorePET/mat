"""Visual regression tests — headless Three.js rendering via ocp_vscode + Playwright.

Proves the full pipeline:
    pymat.Material → .vis.textures (mat-vis) → to_threejs adapter
    → build123d shape → ocp_vscode standalone → three-cad-viewer → screenshot

Requirements:
    pip install playwright ocp_vscode build123d
    python -m playwright install chromium

Skip with: MAT_VIS_SKIP_VISUAL=1 (default)
Run:   MAT_VIS_SKIP_VISUAL=0 pytest tests/test_visual_regression.py -v
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import pytest

SKIP_VISUAL = os.environ.get("MAT_VIS_SKIP_VISUAL", "1") == "1"
SKIP_HEADLESS = os.environ.get("MAT_VIS_SKIP_HEADLESS", "1") == "1"
OUTPUT_DIR = Path(__file__).parent / "visual_output"


@pytest.fixture(scope="module")
def standalone_server():
    """Start ocp_vscode standalone viewer in a background thread."""
    try:
        from ocp_vscode.standalone import Viewer
    except ImportError:
        pytest.skip("ocp_vscode not installed")

    port = 3998  # avoid conflict with default 3939
    viewer = Viewer({"port": port, "debug": False})

    thread = threading.Thread(target=viewer.start, daemon=True)
    thread.start()
    time.sleep(2)

    yield f"http://127.0.0.1:{port}"


@pytest.fixture(scope="module")
def browser():
    """Launch headless Chromium."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("playwright not installed")

    pw = sync_playwright().start()
    b = pw.chromium.launch(headless=True)
    yield b
    b.close()
    pw.stop()


def _screenshot(browser, url: str, name: str, wait_ms: int = 4000) -> Path:
    """Navigate to URL, wait for render, take screenshot."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / f"{name}.png"

    page = browser.new_page(viewport={"width": 800, "height": 600})
    page.goto(url)
    page.wait_for_timeout(wait_ms)
    page.screenshot(path=str(out))
    page.close()

    return out


@pytest.mark.skipif(SKIP_HEADLESS, reason="MAT_VIS_SKIP_HEADLESS=1 — needs ocp_vscode with built JS assets")
class TestFullPipeline:
    """End-to-end: Material → build123d shape → ocp_vscode → screenshot."""

    def test_steel_cube(self, standalone_server, browser):
        """Render a steel cube with PBR scalars (no textures)."""
        from build123d import Box
        from pymat import Material
        from ocp_vscode import show, set_port

        port = int(standalone_server.split(":")[-1])
        set_port(port)

        shape = Box(10, 10, 10)
        m = Material(name="Test Steel")
        m.vis.metallic = 1.0
        m.vis.roughness = 0.3
        m.vis.base_color = (0.8, 0.8, 0.8, 1.0)
        shape.material = m

        # Open browser FIRST so websocket connects, THEN show shape
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out = OUTPUT_DIR / "steel_cube.png"

        page = browser.new_page(viewport={"width": 800, "height": 600})
        page.goto(standalone_server)
        page.wait_for_timeout(2000)  # wait for websocket connect

        show(shape)
        page.wait_for_timeout(5000)  # wait for tessellation + render

        page.screenshot(path=str(out))
        page.close()

        assert out.exists()
        assert out.stat().st_size > 1000, "Screenshot too small — likely blank"
        print(f"Screenshot saved: {out} ({out.stat().st_size} bytes)")

    def test_wood_with_textures(self, standalone_server, browser):
        """Render a shape with mat-vis textures (color, normal maps)."""
        from build123d import Box
        from pymat import Material, vis
        from ocp_vscode import show, set_port

        port = int(standalone_server.split(":")[-1])
        set_port(port)

        results = vis.search(category="wood", limit=1)
        if not results:
            pytest.skip("No wood materials in mat-vis")

        shape = Box(20, 20, 5)
        m = Material(name="Test Wood")
        m.vis.roughness = 0.6
        m.vis.metallic = 0.0
        m.vis.base_color = (0.6, 0.4, 0.2, 1.0)
        m.vis.source_id = f"{results[0]['source']}/{results[0]['id']}"
        shape.material = m

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out = OUTPUT_DIR / "wood_plank.png"

        page = browser.new_page(viewport={"width": 800, "height": 600})
        page.goto(standalone_server)
        page.wait_for_timeout(2000)

        show(shape)
        page.wait_for_timeout(8000)  # longer for texture fetch + render

        page.screenshot(path=str(out))
        page.close()

        assert out.exists()
        assert out.stat().st_size > 1000
        print(f"Screenshot saved: {out} ({out.stat().st_size} bytes)")

    def test_glass_sphere_transmission(self, standalone_server, browser):
        """Render a transparent glass sphere."""
        from build123d import Sphere
        from pymat import Material
        from ocp_vscode import show, set_port

        port = int(standalone_server.split(":")[-1])
        set_port(port)

        shape = Sphere(10)
        m = Material(name="Test Glass")
        m.vis.roughness = 0.0
        m.vis.metallic = 0.0
        m.vis.base_color = (0.9, 0.95, 1.0, 0.3)
        m.vis.ior = 1.52
        m.vis.transmission = 0.9
        shape.material = m

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out = OUTPUT_DIR / "glass_sphere.png"

        page = browser.new_page(viewport={"width": 800, "height": 600})
        page.goto(standalone_server)
        page.wait_for_timeout(2000)

        show(shape)
        page.wait_for_timeout(5000)

        page.screenshot(path=str(out))
        page.close()

        assert out.exists()
        assert out.stat().st_size > 1000
        print(f"Screenshot saved: {out} ({out.stat().st_size} bytes)")


@pytest.mark.skipif(SKIP_VISUAL, reason="MAT_VIS_SKIP_VISUAL=1 (default)")
class TestAdapterOutput:
    """Verify adapter dict output without rendering (lighter, faster)."""

    def test_to_threejs_steel(self):
        """to_threejs produces valid MeshPhysicalMaterial dict."""
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
        """to_threejs includes base64 data URIs when textures available."""
        from pymat import Material, vis
        from pymat.vis.adapters import to_threejs

        results = vis.search(category="metal", limit=1)
        if not results:
            pytest.skip("No metals in mat-vis")

        m = Material(name="Textured Metal")
        m.vis.metallic = 1.0
        m.vis.roughness = 0.3
        m.vis.source_id = f"{results[0]['source']}/{results[0]['id']}"

        d = to_threejs(m)

        has_map = any(k in d for k in ("map", "normalMap", "roughnessMap", "metalnessMap"))

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        summary = {k: (v[:60] + "..." if isinstance(v, str) and len(v) > 60 else v) for k, v in d.items()}
        (OUTPUT_DIR / "metal_textured_threejs.json").write_text(json.dumps(summary, indent=2, default=str))

        if has_map:
            assert d[next(k for k in ("map", "normalMap") if k in d)].startswith("data:image/png;base64,")
