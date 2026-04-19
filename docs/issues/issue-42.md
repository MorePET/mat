---
type: issue
state: open
created: 2026-04-18T15:45:50Z
updated: 2026-04-18T15:45:50Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/42
comments: 0
labels: enhancement, question
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-04-19T04:44:06.928Z
---

# [Issue 42]: [Discuss: JS/TS package for material physics data](https://github.com/MorePET/mat/issues/42)

## Context

The current language footprint of the materials data is:

| Language | Package         | Scope                                    |
|----------|-----------------|------------------------------------------|
| Python   | `py-materials`  | Physics, chemistry, formula, vis wiring  |
| Rust     | `rs-materials`  | Same physics + formula parsing           |
| JS/TS    | —               | (none for physics)                       |

The JS ecosystem already has the **visual** side covered via [threejs-materials](https://github.com/bernhard-42/threejs-materials) (PBR/MaterialX → `MeshPhysicalMaterial`). What's missing in JS is the **physics/chemistry** layer that py-mat owns — `density`, `melting_point`, `formula`, mechanical/thermal properties, etc.

## The question

Is there a real JS-side consumer that would benefit from native access to this data, vs. a backend roundtrip?

Plausible consumers:

- A web-based CAD viewer that wants to display "stainless 316L: 8.0 g/cm³" inline
- `ocp_vscode` (TS) wanting physics data client-side instead of just PBR
- A browser-based mass / thermal / cost calculator
- A material picker UI that filters on physical properties

If any of these become real, building `mat-js` is cheap. If none do, it's three parallel implementations to maintain across every schema change.

## Sketch of the implementation if greenlit

- New package `mat-js` (ESM + CJS), published to npm
- Embeds the same TOML data files (build-time JSON conversion, mirroring the `include_str!` pattern in `rs-materials`)
- Mirrors the `Material` / `*Properties` data classes from py-mat / rs-materials
- Slots into the existing release-please pipeline as a third package; the `npm` ecosystem in `dependabot.yml` becomes live instead of a no-op carryover

## Decision criteria

Build `mat-js` when **at least one** of these is true:

- [ ] A named consumer (internal or external) requests it with a concrete use case
- [ ] `ocp_vscode` or another viewer in the build123d/CAD ecosystem expresses interest
- [ ] An external contributor PRs a working prototype

Until then: **deferred — not blocked, not started.**

## Refs

- Discussion in conversation 2026-04-18 with @gerchowl
- Related: #3 (mat-vis-client integration paper trail)

Refs: #N/A
