---
type: issue
state: open
created: 2026-04-17T23:15:33Z
updated: 2026-04-17T23:15:33Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/41
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-04-18T04:24:31.071Z
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
