#!/usr/bin/env python3
"""Render per-material PBR previews for the catalog.

Loops every material that has `vis.has_mapping`, picks a shape based on
category (cube for solids, sphere for fluids), and renders a light +
dark themed PNG via headless Three.js (Playwright + SwiftShader).

Output: docs/catalog/<category>/previews/<key>_<shape>_<theme>.png

Requires:
    pip install -r scripts/requirements-curation.txt
    python -m playwright install chromium

Usage:
    python scripts/generate_previews.py              # full regen
    python scripts/generate_previews.py --only stainless,copper
    python scripts/generate_previews.py --changed-only  # read git diff
"""

from __future__ import annotations

import argparse
import base64
import http.server
import json
import logging
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pymat import _CATEGORY_BASES, load_all
from pymat.vis.adapters import to_threejs

log = logging.getLogger("previews")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VIEWER_HTML = PROJECT_ROOT / "tests" / "material_preview.html"
CATALOG_ROOT = PROJECT_ROOT / "docs" / "catalog"

# Shape per category — cube reads as "solid", sphere reads as "fluid"
_SHAPE_BY_CATEGORY = {
    "metals": "cube",
    "plastics": "cube",
    "ceramics": "cube",
    "electronics": "cube",
    "scintillators": "cube",
    "liquids": "sphere",
    "gases": "sphere",
}
_THEMES = ("light", "dark")


@contextmanager
def _file_server(serve_dir: Path, port: int = 8767):
    """Serve `serve_dir` over HTTP on localhost; yield the base URL."""

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


def _walk_hierarchy(mats):
    """Yield (category, path, material) — Hierarchical walk with category tag."""
    for category, bases in _CATEGORY_BASES.items():
        for base_key in bases:
            mat = mats.get(base_key)
            if mat is None:
                continue

            def walk(m, p):
                yield category, p, m
                for ck, cm in getattr(m, "_children", {}).items():
                    yield from walk(cm, f"{p}.{ck}")

            yield from walk(mat, base_key)


def _changed_material_keys() -> set[str]:
    """Parse `git diff` to find TOMLs that changed, return the root keys."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "origin/main...HEAD", "--", "src/pymat/data/"],
            check=True,
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
    except subprocess.CalledProcessError:
        return set()
    # Any changed TOML → render every material in that category.
    # More precise diffing (which [key.vis] block changed) requires parsing
    # the unified diff — out of scope for this pass.
    categories = {Path(p).stem for p in result.stdout.strip().splitlines() if p}
    keys: set[str] = set()
    for cat in categories:
        keys.update(_CATEGORY_BASES.get(cat, []))
    return keys


def _render_one(
    page,
    server_url: str,
    key: str,
    shape: str,
    theme: str,
    material_json_path: Path,
    out_path: Path,
) -> bool:
    """Render a single preview; return True on success."""
    url = (
        f"{server_url}/material_preview.html"
        f"?shape={shape}&theme={theme}&material={material_json_path.name}"
    )
    page.goto(url)
    try:
        page.wait_for_function("window.__renderComplete === true", timeout=15_000)
    except Exception as exc:
        log.warning("render timeout for %s (%s/%s): %s", key, shape, theme, exc)
        return False
    # Extra settle time for async texture decoding
    page.wait_for_timeout(200)
    data_url = page.evaluate('document.querySelector("canvas").toDataURL("image/png")')
    png_bytes = base64.b64decode(data_url.split(",", 1)[1])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(png_bytes)
    return True


def generate(only: set[str] | None = None) -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.error("playwright not installed. See scripts/requirements-curation.txt")
        return 1

    mats = load_all()
    targets = []
    for category, path, m in _walk_hierarchy(mats):
        if not m.vis.has_mapping:
            continue
        base = path.split(".")[0]
        if only is not None and base not in only and path not in only:
            continue
        targets.append((category, path, m))

    if not targets:
        log.info("No materials to render (empty `only` filter or nothing with vis.has_mapping)")
        return 0

    log.info(
        "Rendering %d materials x %d themes = %d images",
        len(targets),
        len(_THEMES),
        len(targets) * len(_THEMES),
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        shutil.copy(VIEWER_HTML, tmp / "material_preview.html")

        with _file_server(tmp) as server_url, sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=["--use-gl=swiftshader"])
            page = browser.new_page(viewport={"width": 512, "height": 512})
            try:
                rendered = 0
                counter = 0
                for category, path, m in targets:
                    # Flattened key for file output — uses underscores for
                    # dotted paths so filesystems stay happy.
                    leaf_key = path.replace(".", "_")
                    shape = _SHAPE_BY_CATEGORY.get(category, "cube")

                    # Write a fresh material file with a unique name so the
                    # headless browser can't cache it across iterations.
                    counter += 1
                    material_json = tmp / f"material_{counter}.json"
                    material_json.write_text(json.dumps(to_threejs(m)))

                    for theme in _THEMES:
                        out = (
                            CATALOG_ROOT / category / "previews" / f"{leaf_key}_{shape}_{theme}.png"
                        )
                        t0 = time.time()
                        ok = _render_one(
                            page, server_url, leaf_key, shape, theme, material_json, out
                        )
                        if ok:
                            rendered += 1
                            log.info(
                                "  %s (%s, %s) %.1fs", leaf_key, shape, theme, time.time() - t0
                            )
                log.info("Rendered %d/%d", rendered, len(targets) * len(_THEMES))
            finally:
                browser.close()

    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="Comma-separated list of material keys")
    parser.add_argument(
        "--changed-only",
        action="store_true",
        help="Only re-render materials in TOMLs changed vs origin/main",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )

    only: set[str] | None = None
    if args.only:
        only = set(args.only.split(","))
    elif args.changed_only:
        only = _changed_material_keys()
        if not only:
            log.info("No TOML changes detected vs origin/main — nothing to render")
            return 0
        log.info("Changed materials: %s", ", ".join(sorted(only)))

    sys.exit(generate(only))


if __name__ == "__main__":
    main()
