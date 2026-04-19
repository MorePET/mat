"""Pixel-diff helper for headless Three.js visual regression tests.

Why pixel-diff not hash-equality:

Three.js rendered via SwiftShader on Ubuntu CI vs macOS local produces
subtly different pixel output — sub-pixel AA, floating-point rounding in
the reflection envmap, even Chromium minor-version updates. A raw byte
hash compare would fail on every CI run. Pixel-diff with an RMS
tolerance absorbs the platform-level noise while still catching real
regressions (color channels drifting, a whole material rendering as
grey because textures didn't load, etc.).

Why PIL not numpy:

PIL is already in the dev-extras transitive (Playwright pulls it for
its tracing/screenshots). numpy is a heavier dep that we don't need
for plain RMS.

Workflow:

    # First time, or after intentional visual change: generate baselines
    MAT_VIS_UPDATE_BASELINES=1 pytest tests/test_visual_regression.py -v -s

    # Regular CI run: compare against committed baselines
    MAT_VIS_SKIP_VISUAL=0 pytest tests/test_visual_regression.py -v -s

See issue #41 for the wider context.
"""

from __future__ import annotations

import math
import os
from pathlib import Path

from PIL import Image

# Root baseline directory. Tests store / load PNG images by logical name
# (e.g. "steel_cube") and this module resolves to .../tests/baselines/<name>.png.
BASELINE_DIR = Path(__file__).parent / "baselines"

# Default RMS tolerance, scaled to 0..255 per channel.
#
# Empirically (macOS-arm64 Chromium 0.xxx vs Ubuntu-x86 Chromium 0.yyy)
# the same PBR scene renders with an RMS of ~3–6 per channel. Set the
# default above that so the suite doesn't go flaky on browser-minor
# bumps, but low enough that a material rendering as default-grey
# instead of gold (Δ ≈ 50+) lights up.
DEFAULT_RMS_TOLERANCE = 8.0


def _update_mode() -> bool:
    """True when baselines should be (re)generated instead of compared."""
    return os.environ.get("MAT_VIS_UPDATE_BASELINES", "0") == "1"


def _rms(a_pixels, b_pixels) -> float:
    """Root-mean-square difference over all pixel components, 0..255 scale.

    Both inputs are flat sequences of integers (PIL's tobytes() or
    getdata() output). Assumes same length + same mode.
    """
    n = len(a_pixels)
    if n == 0:
        return 0.0
    sq_sum = 0
    for a, b in zip(a_pixels, b_pixels):
        d = a - b
        sq_sum += d * d
    return math.sqrt(sq_sum / n)


def _load_rgb(path: Path) -> tuple[Image.Image, tuple[int, int]]:
    """Load a PNG as RGB (drop alpha) — alpha channel isn't stable
    across platforms for renders with transparent backgrounds."""
    img = Image.open(path).convert("RGB")
    return img, img.size


def assert_matches_baseline(
    actual_path: Path,
    name: str,
    *,
    rms_tolerance: float = DEFAULT_RMS_TOLERANCE,
) -> None:
    """Compare a freshly-rendered PNG against its committed baseline.

    - In ``MAT_VIS_UPDATE_BASELINES=1`` mode, copies the actual render
      to ``BASELINE_DIR/<name>.png`` and returns. Useful for first-time
      generation and for committing visual changes deliberately.
    - Otherwise, loads the baseline (skips if absent — baselines are
      optional, not required for the test to run) and compares via
      RMS. Fails the test if RMS exceeds ``rms_tolerance``.

    ``rms_tolerance`` is in the 0..255-per-channel space. See module
    docstring for calibration notes.
    """
    baseline_path = BASELINE_DIR / f"{name}.png"

    if _update_mode():
        BASELINE_DIR.mkdir(parents=True, exist_ok=True)
        actual_bytes = actual_path.read_bytes()
        baseline_path.write_bytes(actual_bytes)
        return

    if not baseline_path.exists():
        # No baseline committed yet — that's a soft-skip. The test
        # already asserts the screenshot is non-blank via file size;
        # baseline comparison kicks in once someone commits one.
        import pytest

        pytest.skip(
            f"No committed baseline at {baseline_path.relative_to(BASELINE_DIR.parent.parent)}. "
            f"Generate with: MAT_VIS_UPDATE_BASELINES=1 pytest <this file>"
        )
        return

    actual_img, actual_size = _load_rgb(actual_path)
    baseline_img, baseline_size = _load_rgb(baseline_path)

    assert actual_size == baseline_size, (
        f"{name}: render size {actual_size} != baseline size {baseline_size}. "
        f"Regenerate baselines if viewport changed intentionally."
    )

    rms = _rms(list(actual_img.tobytes()), list(baseline_img.tobytes()))
    assert rms <= rms_tolerance, (
        f"{name}: pixel RMS {rms:.2f} exceeds tolerance {rms_tolerance:.2f}. "
        f"Visual regression — diff the images in tests/visual_output/ + "
        f"tests/baselines/ to see what drifted. "
        f"If the change is intentional, regenerate via "
        f"MAT_VIS_UPDATE_BASELINES=1 pytest ..."
    )
