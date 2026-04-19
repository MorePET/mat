---
type: issue
state: closed
created: 2026-04-17T23:15:33Z
updated: 2026-04-19T01:00:17Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/41
comments: 1
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-04-19T04:44:07.277Z
---

# [Issue 41]: [Visual regression tests: headless Three.js rendering via ocp_vscode + Playwright](https://github.com/MorePET/mat/issues/41)

## Context

The adapter pipeline (pymat → mat-vis textures → to_threejs →
ocp_vscode → three-cad-viewer) is tested at the data level (field
names, base64 encoding). But there's no test that the rendered
output actually looks correct.

## Architecture

```
Python test:
  Material("stainless") → to_threejs() → ocp_vscode standalone

Playwright (headless Chrome):
  → navigate to localhost → three-cad-viewer renders with WebGL
  → captureCanvas() → screenshot PNG

CI:
  compare to baseline → pass/fail
```

three-cad-viewer has built-in screenshot:
- `getImage("screenshot")` in `src/core/viewer.ts`
- `captureCanvas()` in `src/ui/display.ts`

ocp_vscode has standalone Flask server mode.

## Proof-of-concept

`tests/test_visual_regression.py` exists with the framework:
- `TestVisualRegression` — validates adapter JSON output
- `TestHeadlessScreenshot` — placeholder for full Playwright wiring

## Remaining work

- [ ] Wire ocp_vscode standalone server startup in test fixture
- [ ] Playwright page navigation + `show(shape)` command
- [ ] Wait for WebGL render completion (Three.js `onAfterRender`)
- [ ] Screenshot capture + baseline comparison
- [ ] CI workflow with Playwright GitHub Action
- [ ] Baseline images for: metal cube, wood plank, glass sphere,
      textured vs scalar-only, KTX2 vs PNG (when available)
- [ ] Pixel-diff threshold (allow minor antialiasing variance)

## Dependencies

```
pip install playwright ocp_vscode build123d
python -m playwright install chromium
```

## Refs

- `tests/test_visual_regression.py` — existing proof-of-concept
- three-cad-viewer screenshot API: `src/core/viewer.ts:4344`
- ocp_vscode standalone: `ocp_vscode/standalone.py`
---

# [Comment #1]() by [gerchowl]()

_Posted on April 19, 2026 at 12:30 AM_

## Last two checkboxes: pixel-diff + baselines

Landed on \`feature/73-mat-vis-client-0.5\` as \`b6f6cce\`:

- \`tests/_visual_compare.py\` — PIL-based RMS comparator with 8.0 default tolerance (calibrated: absorbs Chromium AA drift across macOS/Ubuntu, catches material-renders-as-grey regressions with Δ ≈ 50+).
- \`tests/test_visual_compare.py\` — 12 unit tests for the comparator. Run without Playwright.
- \`tests/test_visual_regression.py\` — steel_cube / red_sphere / gold_cylinder now call \`assert_matches_baseline()\` after their 'non-blank' checks.
- \`tests/baselines/README.md\` — documents regeneration workflow (local \`MAT_VIS_UPDATE_BASELINES=1\` + CI artifact-download path).
- \`.github/workflows/visual-regression.yml\` — adds \`update_baselines\` boolean \`workflow_dispatch\` input that flips the run to write-mode.

Remaining: **commit actual baseline PNGs**. Gated on running the workflow once on CI Ubuntu Chromium so the baselines match CI's rendering environment. Blocks on:
- Branch push + PR open (CI doesn't run on unpushed branches)
- First successful run of the workflow → download artifact → commit PNGs

Until baselines are committed, \`assert_matches_baseline\` soft-skips with a clear message pointing at the regeneration workflow. The framework is usable without a pre-generation ritual.

Test count: 280 passing (+12 comparator units).

