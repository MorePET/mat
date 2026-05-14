"""Standalone CLI to render the mat-vis #285 regression grids.

Pytest-free counterpart to ``test_visual_regression.TestMatVis285_Visual``.
Useful for visual inspection without running the full suite or its
assertions — handy when iterating on the renderer or comparing tiers.

Uses ``tests/visual_grid_render.html`` (sphere grid). The shader_ball
geometry variant of this render lives in ``mat-vis/bake/preview/`` now.

Usage:
    uv run python tests/render_bernhard_grid.py
    uv run python tests/render_bernhard_grid.py --out /tmp/grid --tier 512
    uv run python tests/render_bernhard_grid.py --kinds scalar
"""

from __future__ import annotations

import argparse
import base64
import http.server
import json
import shutil
import sys
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path

TESTS_DIR = Path(__file__).parent
RENDERER_HTML = TESTS_DIR / "visual_grid_render.html"

sys.path.insert(0, str(TESTS_DIR))
from test_visual_regression import (  # noqa: E402
    SCALAR_ONLY_REGRESSION_GRID,
    TEXTURED_REGRESSION_GRID,
)

GRID_COLS = 5


@contextmanager
def _file_server(serve_dir: Path, port: int = 8771):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(serve_dir), **kwargs)

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()


def _build_items_textured(tier: str) -> list[dict]:
    from pymat.vis import Vis, to_threejs

    items = []
    for idx, (label, source, material_id) in enumerate(TEXTURED_REGRESSION_GRID):
        try:
            v = Vis(source=source, material_id=material_id, tier=tier)
            tj = to_threejs(v)
            items.append(
                {
                    "label": label,
                    "row": idx // GRID_COLS,
                    "col": idx % GRID_COLS,
                    "threejs": tj,
                }
            )
            keys = sorted(k for k in tj if k != "type")
            print(f"  OK row={idx // GRID_COLS} col={idx % GRID_COLS}  {label:24s} keys={keys}")
        except Exception as e:
            print(
                f"  -- row={idx // GRID_COLS} col={idx % GRID_COLS}  {label:24s} "
                f"SKIP: {type(e).__name__}: {str(e)[:60]}"
            )
    return items


def _build_items_scalar() -> list[dict]:
    from pymat.vis import Vis, to_threejs

    items = []
    for idx, (label, material_id) in enumerate(SCALAR_ONLY_REGRESSION_GRID):
        try:
            v = Vis(source="physicallybased", material_id=material_id)
            tj = to_threejs(v)
            items.append(
                {
                    "label": label,
                    "row": idx // GRID_COLS,
                    "col": idx % GRID_COLS,
                    "threejs": tj,
                }
            )
            keys = sorted(k for k in tj if k != "type")
            print(f"  OK {label:12s} keys={keys}")
        except Exception as e:
            print(f"  -- {label:12s} SKIP: {type(e).__name__}: {str(e)[:60]}")
    return items


def _render(
    spec: dict, label: str, out_dir: Path, tmp: Path, server_url: str, browser
) -> Path:
    spec_path = tmp / f"spec_{label}.json"
    spec_path.write_text(json.dumps(spec))

    page = browser.new_page(viewport={"width": 1600, "height": 1200}, device_scale_factor=2)
    page.on("console", lambda m: print(f"      [page-{m.type}]: {m.text[:200]}"))
    page.on("pageerror", lambda e: print(f"      [page-error]: {e}"))

    url = f"{server_url}/grid.html?spec={spec_path.name}"
    page.goto(url, timeout=180_000)
    page.wait_for_function("() => window.__renderComplete === true", timeout=300_000)
    page.wait_for_timeout(8_000)  # let textures settle

    data_url = page.evaluate("() => document.querySelector('canvas').toDataURL('image/png')")
    out = out_dir / f"grid_{label}.png"
    out.write_bytes(base64.b64decode(data_url.split(",", 1)[1]))
    page.close()
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=TESTS_DIR / "visual_output" / "standalone",
        help="Output directory for rendered PNGs (default: tests/visual_output/standalone)",
    )
    parser.add_argument(
        "--tier",
        default="1k",
        help="Texture tier for the textured grid (default: 1k)",
    )
    parser.add_argument(
        "--kinds",
        nargs="+",
        choices=["textured", "scalar"],
        default=["textured", "scalar"],
        help="Which grids to render (default: both)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8771,
        help="Local HTTP server port (default: 8771)",
    )
    args = parser.parse_args(argv)

    if not RENDERER_HTML.exists():
        print(f"FATAL: renderer not found at {RENDERER_HTML}", file=sys.stderr)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)

    items_tex: list[dict] = []
    items_sca: list[dict] = []
    if "textured" in args.kinds:
        print(f"# Building textured {args.tier} spec...")
        items_tex = _build_items_textured(args.tier)
    if "scalar" in args.kinds:
        print("\n# Building scalar spec...")
        items_sca = _build_items_scalar()

    if not items_tex and not items_sca:
        print("FATAL: no items in either spec", file=sys.stderr)
        return 1

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("FATAL: playwright not installed (uv pip install playwright)", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        shutil.copy(RENDERER_HTML, tmp / "grid.html")

        with _file_server(tmp, port=args.port) as server_url, sync_playwright() as pw:
            print("\n# Spawning Chromium...")
            browser = pw.chromium.launch(headless=True, args=["--use-gl=swiftshader"])

            if items_tex:
                spec = {"tier": args.tier, "kind": "textured", "items": items_tex}
                label = f"textured_{args.tier}"
                print(f"\n# Rendering textured grid ({len(items_tex)} items)...")
                out = _render(spec, label, args.out, tmp, server_url, browser)
                print(f"  -> {out}  ({out.stat().st_size // 1024}KB)")

            if items_sca:
                spec = {"tier": "scalar", "kind": "scalar", "items": items_sca}
                print(f"\n# Rendering scalar grid ({len(items_sca)} items)...")
                out = _render(spec, "scalar", args.out, tmp, server_url, browser)
                print(f"  -> {out}  ({out.stat().st_size // 1024}KB)")

            browser.close()

    print(f"\n# PNGs at: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
