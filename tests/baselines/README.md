# Visual regression baselines

PNG reference images for `tests/test_visual_regression.py`. Each baseline
is the expected output of a specific headless Three.js render. CI compares
the freshly-rendered PNG against the committed baseline using an RMS
pixel-diff threshold (see `tests/_visual_compare.py`).

## Why baselines are optional

`assert_matches_baseline(...)` **soft-skips** when no baseline is committed
for a given name. The suite still runs (the "render is non-blank" check
via file size stays hard), baselines just aren't compared. This is
deliberate:

- Baselines generated on macOS-arm64 Chromium vs Ubuntu-x86 Chromium
  differ by a small but stable RMS; one set won't match both platforms.
- We want the test framework to be usable without a committed baseline
  so contributors can add new visual tests without a pre-generation
  ritual.

## When to generate or regenerate

1. **First time adding a render test** — run once on the target platform
   (usually CI's Ubuntu Chromium), commit the resulting PNG images.
2. **Intentional visual change** — e.g. updating `tests/visual_render.html`
   to tweak lighting, HDRI, or camera. Regenerate and commit with the
   change.
3. **Never** regenerate to "fix" a failing test without understanding
   what drifted. Diff the PNG images first.

## How to regenerate

Local (macOS / Linux with Chromium installed):

```bash
MAT_VIS_SKIP_VISUAL=0 MAT_VIS_UPDATE_BASELINES=1 \
    pytest tests/test_visual_regression.py -v -s
```

The `MAT_VIS_UPDATE_BASELINES=1` flag makes
`assert_matches_baseline(...)` write the actual render to this directory
instead of comparing. Commit the resulting PNG images.

CI (preferred for cross-platform stability):

1. Trigger the `Visual Regression` workflow via `workflow_dispatch`.
2. Download the `visual-regression-screenshots` artifact from the run.
3. Copy the relevant PNG images into `tests/baselines/` and commit.

## Tolerance

The current threshold is 8.0 RMS (0-255 per channel) — roughly 3%
per-pixel difference averaged across all components. See
`DEFAULT_RMS_TOLERANCE` in `tests/_visual_compare.py` and the
justification next to it.

Tighten per-test by passing `rms_tolerance=...` to `assert_matches_baseline`
if a particular scene renders deterministically enough to deserve a
stricter check.
