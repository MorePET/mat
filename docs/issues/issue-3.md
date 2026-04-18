---
type: issue
state: closed
created: 2026-03-22T15:41:22Z
updated: 2026-04-17T11:16:45Z
author: gumyr
author_url: https://github.com/gumyr
url: https://github.com/MorePET/mat/issues/3
comments: 8
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-04-18T04:24:34.579Z
---

# [Issue 3]: [Further build123d/ocp_vscode integration](https://github.com/MorePET/mat/issues/3)

Thank you for creating this project, adding a material system to build123d is one of the long standing roadmap items. `py-mat` could be the solution, an project independent of `build123d` but directly supported.

Recently @bernhard-42 added support for PBR into the ocp_vscode viewer (see: https://discordapp.com/channels/964330484911972403/964330777401770025/1483435846081187981)  which uses MaterialX materials which can be browsed at the 4 supported sources:

- https://ambientcg.com/list?type=material,
- https://matlib.gpuopen.com/main/materials/all,
- https://polyhaven.com/textures,
- https://physicallybased.info/

We're wondering if you would consider supporting this version of PBR which allows for things like texture maps for wood grain?  Possibly something like: `steel = bd.Material(name="steel", density=7.8, pbr=bd.Material.gpuopen.load("Brushed Steel"))`.

I would also hope that we could get to the point where one could add materials to build123d shapes by just setting the `material` attribute like: `my_thing.material = Material(name="Steel", density=7.8)`.

We're looking forward to collaborating with you.

Cheers, Roger


---

# [Comment #1]() by [gerchowl]()

_Posted on April 15, 2026 at 01:22 PM_

Hi @gumyr — thanks for opening this, and apologies for the slow response.

Short version: **yes, we'd love for py-materials to become the material layer for build123d.** Materials-as-data has been the library's reason for existing, and hooking into the primary Python-CAD ecosystem is the most useful thing it could be doing.

A few things have moved since you filed the issue:

- @bernhard-42 sent us [PR #6](https://github.com/MorePET/mat/pull/6) adding Python 3.10 support (merged), and as part of reviewing it we traced the `ocp_vscode` PBR work back to his [threejs-materials](https://github.com/bernhard-42/threejs-materials) library. It already does the heavy lifting for MaterialX: loaders for all four sources you mentioned, MaterialX graph baking, caching, and Three.js `MeshPhysicalMaterial` output. And we saw the example in `ocp_vscode` where `shape.material = PbrProperties.from_gpuopen(...)` already works, with a `FutureWarning` promising the type will change.
- So the natural next step is figuring out how py-materials and threejs-materials should fit together, with build123d as the canonical consumer via `shape.material`.

**@gumyr — one question for you**: how do you see the build123d side of this playing out? Are you thinking of `Shape.material` as a first-class attribute you'd add to build123d directly, or as a convention we document on the py-materials side? And would you lean toward build123d optionally installing py-materials, or staying fully decoupled so users bring their own? We're happy to implement whichever shape you prefer — just want to make sure we land on something that fits build123d's design taste.

**@bernhard-42 — pulling you in directly because you're the lynchpin here**: a few open questions before we commit to a direction.

1. How do you see the integration? The options we've been discussing range from py-materials depending on threejs-materials as an optional extra (keeps the two libraries independent), to absorbing threejs-materials into py-materials under a feature flag (single install, but a bigger footprint for users who only want physics properties and don't need PBR rendering). We want to go in whichever direction you think makes sense for threejs-materials' own roadmap.
2. Are you interested in maintaining threejs-materials as the PBR backend long-term? If yes, the optional-extra path is probably the cleanest — py-materials stays lean, threejs-materials stays the single source of truth for PBR loading. If you'd rather hand the PBR story off to py-materials, we can discuss merging.
3. What's your current thinking on offline-first behavior? A lot of py-materials' users are in CI pipelines, headless build farms, and air-gapped scientific environments where network downloads on first-use are painful. Does threejs-materials have (or could it grow) a no-network mode + explicit cache controls?

**An alternative worth considering**: we could bake the PBR code into py-materials directly (threejs-materials is Apache-2.0, fully compatible), with a feature flag so physics-only users stay lightweight and offline-first. Default install: no PBR, no texture libs, no network-touching code paths. `pip install py-materials[pbr]` (or similar) enables the full MaterialX story. This is essentially option 1 reframed, but with a single maintenance surface. The downside is it duplicates code you're already maintaining, which is why we'd rather not go this route unless you'd prefer we take the PBR work off your hands.

Whatever you two prefer, we're happy to do the implementation work on the py-materials side. The coordination question is really about how we want the three libraries (py-materials, threejs-materials, build123d) to relate over the long term.

Looking forward to figuring out the right shape of this with you both.

---

# [Comment #2]() by [bernhard-42]()

_Posted on April 15, 2026 at 03:20 PM_

@gerchowl 

**1 Integration**

I think py-materials and threejs-materials serve different purposes:
- py-materials provides physical properties of materials that can be used e.g. for further analysis or in manufacturing
- threejs-materials is a bridge between complex material definitions from MaterialX sources (directly supported and baked) and Blender (baked in Blender and exported as glTF)

The thinking in https://github.com/gumyr/build123d/pull/1270 that Roger (gumyr) and I discussed was the following:

`shape.material` should work similar to `shape.color`:
- `shape.color = "red"` gets resolved by build123d using the `Color` class to `Color(1.0, 0.0, 0.0)`
- `shape.material = "stainless"` gets resolved by build123d using the `Material` class to py-materials stainless material
 
With this simple assignment, build123d already has access to e.g. the density of a material useful for mass calculation, but also to all the other properties. 

But of course, with py-materials you can do more and I didn't want to replicate the py-materials functionality in build123d. So I think py-materials will be used by engineers to access or create materials and the interface to build123d needs to be easy. 

So the current proposal is 

```python
shape.material = Material(material: pymat.Material, pbr: threejs_materials.PbrProperties=None)
```

Afterwards `shape.material._material` is a py-materials object and the build123d class `Material` provides proxy properties to py-materials categories so that `shape.material.mechanical => shape.material._material.properties.mechanical`, ...)

If keyword arg `pbr` is set, `shape.material._pbr` is the threejs_material `PbrProperties` object else `None`.

As the protocol for OCP VSCode `shape.material.pbr` exists. The `Material` property `pbr` returns `self._pbr` if not `None`, else the conversion of py-materials `pbr` properties (less sophisticated but often sufficient) to `PbrProperties`.

What this means:
- build123d is decoupled from py-materials as long as the category properties are kept stable
- build123d is decoupled from threejs-materials as long as `shape.material.pbr` returns a `PbrProperties` object
- py-materials and threejs-materials are decoupled, but build123d translates py-materials pbr properties to `PbrProperties` if no extra pbr properties given.

Not saying that this is the right interfacing, but this is what I have implemented in the PR https://github.com/gumyr/build123d/pull/1270

Happy to discuss and change!

---

**2 Maintenace**

The reason for having built threejs-materials is the Studio mode of OCP VSCode. The output format and three-cad-viewer (the actual viewer Javascript component) are tightly linked: The UV calculation in ocp-tessellate (the triangulation routine that creates meshes from build123d/OCP objects) is reflected in three-cad viewer to properly apply textures, the dict names and structure is mirrored in three-cad-viewer, ... And bugs in rendering often need to be fixed in both, threejs-materials and three-cad-viewer.

As such, my plan was to maintain threejs-materials with a rendering only scope. 

**Should py-materials and threejs-materials be combined?**

Maybe not: There are material categories like liquids, gases, scintillators where my sources (MaterialX and Blender) don't have PBR properties. And there are materials important for CAD (e.g. different woods for laser cut objects) that are currently not in py-materials, but can be added by the user via custom py-materials materials.

```text
+------------------------+
|  py-materials PBR      |
|                        |
|  gas,        |---------+-------------
|  water,      |   alu,  |            |
|  ...         |  steel, |            |
|              |   ...   |            |
+--------------+---------+            |
               |  (wood, ...)         |
               |                      |
               |  threejs-materials   |
               +----------------------+
```

So my current thinking is:
- I keep the maintenance for threejs-materials as the translator for complex materials from MaterialX and Blender
- py-materials keeps its scope with the simple pbr definitions for its materials (maybe without textures to simplify)

With this users can rely on py-materials only to get both physical material properties and simple rendering properties. And if someone wants nice textured rendering materials, they can add threejs-materials `PbrProperties`.

So the proposal is that py-materials maintains the simple pbr properties for all materials in its database and I keep maintaining threejs-materials for complex material pbr definitions (and keep it in line with three-cad-viewer)

We just meet in the `Material` class of build123d

Again, open to discuss this

--- 

**3 Offline**

1) The `PbrProperties` are optional 
2) The baking in threejs-materials is done once and then cached in ~/.materialx-cache/

```text
❯ tree .materialx-cache/gpuopen_th_brown_fabric_leather_1k*
.materialx-cache/gpuopen_th_brown_fabric_leather_1k
├── color.png
├── normal.png
└── roughness.png
.materialx-cache/gpuopen_th_brown_fabric_leather_1k.json
```

with 

```json
❯ cat .materialx-cache/gpuopen_th_brown_fabric_leather_1k.json
{
  "id": "TH Brown Fabric Leather",
  "name": "TH Brown Fabric Leather",
  "source": "gpuopen",
  "url": "https://matlib.gpuopen.com/main/materials/all?id=2f568489-6b81-43ab-aa33-cc4f7e32fdce",
  "license": "MIT Public Domain",
  "values": {
    "color": [
      0.800000011920929,
      0.800000011920929,
      0.800000011920929
    ],
    "metalness": 0.0,
    "roughness": 1.0,
    "specularIntensity": 1.0,
    "specularColor": [
      1.0,
      1.0,
      1.0
    ],
    "ior": 1.5
  },
  "textures": {
    "color": "color.png",
    "roughness": "roughness.png",
    "normal": "normal.png"
  },
  "maps_dir": "gpuopen_th_brown_fabric_leather_1k"
}
```

This should be easy to provide for CI/CD in advance in the repo

--- 

**Summary**
It got long, but I tried to explain design and rationale of threejs-materials and how I think it should work with py-materials.
And, as I mentioned, I am absolutely open to discuss our cooperation

---

# [Comment #3]() by [bernhard-42]()

_Posted on April 15, 2026 at 03:22 PM_

Re 
> An alternative worth considering: we could bake the PBR code into py-materials 

The challenge can be the debugging of rendering issues. Sometimes the baker in threejs-materials has an issue, sometimes the rendering in three-cad-viewer, and sometimes both.

So my recommendation would be that I keep the maintenance of threejs-materials to simplify bug fixing in the rendering side

---

# [Comment #4]() by [bernhard-42]()

_Posted on April 15, 2026 at 03:27 PM_

I forgot, to be clear, in my PR build123d needs to import both

```python
from threejs_materials import PbrProperties
import pymat
from pymat import (
    MechanicalProperties,
    ThermalProperties,
    ElectricalProperties,
    OpticalProperties,
    ManufacturingProperties,
    ComplianceProperties,
    SourcingProperties,
)
```

`pymat` for type checking only (the category proxies) and `PbrProperties` to convert pymat `pbr` properties to `PbrProperties`

Both should be discussed whether they are the best way to integrate

---

# [Comment #5]() by [bernhard-42]()

_Posted on April 15, 2026 at 03:38 PM_

A bit of a side topic, but maybe you have an opinion about it:

The `materialx` and `openexr` dependency of threejs-materials needed for baking MaterialX are currently extra dependencies, since they are only available as binaries up to Python 3.13. On Linux and MacOS, pip install will compile them, but on Windows many users don't have a compiler installed.

What do you think is better:
- make them normal dependencies, failing to install on Windows 3.14 when no compiler is installed, but being at hand on any other platform
- or force every other platform to install 'threejs-materials[materialx]` (as it is implemented now)

---

# [Comment #6]() by [gerchowl]()

_Posted on April 15, 2026 at 03:57 PM_

Quick update on this thread: we hot-wired a proof of concept for one concrete case (a build123d \`Part\` carrying a \`pymat.Material\` with a \`threejs-materials\` PBR source, rendered in \`ocp_vscode\`). The goal was to surface the design trade-offs with real code rather than more prose, not to propose a final direction — everything below is exploratory and subject to revision based on your feedback.

## Visual proof

A 200×200 mm plate, \`part.material = pymat.Material(name=\"Walnut\", density=0.65, pbr_source=PbrProperties.from_gpuopen(\"Ivory Walnut Solid Wood\"))\`, rendered through \`ocp_vscode.show()\` with full MaterialX wood grain. The same \`part.material\` also answers \`.density\`, \`.molar_mass\`, \`.formula\`, etc. for physics queries. One object, two consumers, no duplication.

## Three draft PRs wire it together

| Repo | Draft PR | Gist |
|---|---|---|
| py-materials | [MorePET/mat#30](https://github.com/MorePET/mat/pull/30) | \`Material.pbr_source\` field + \`pymat.pbr.PbrSource\` Protocol + \`[pbr]\` optional extra that pulls \`threejs-materials[materialx]\`. ADR-0002 captures the design rationale + upgrade triggers. |
| build123d | [gumyr/build123d#1276](https://github.com/gumyr/build123d/pull/1276) | Type-widens \`Compound.material\` and \`Solid.material\` from \`str\` to \`str \| pymat.Material \| None\`. Backward compatible — the existing str tag usage for STEP/STL export metadata keeps working. TYPE_CHECKING-only import so build123d has no runtime py-materials dependency unless the user installs \`build123d[materials]\`. |
| ocp_vscode | [bernhard-42/vscode-ocp-cad-viewer#228](https://github.com/bernhard-42/vscode-ocp-cad-viewer/pull/228) | 1-conditional fix in \`_extract_materials_from_node\`: prefer \`node.material.pbr_source\` over the lossy field-by-field copy through the lite \`properties.pbr\` dataclass. Without this, non-metal materials (wood, bricks, tiles — anything whose visual identity lives in the color map) rendered flat white because the lite dataclass had no \`base_color_map\` field. |

Each PR is small, individually reviewable, and backward compatible. They're **draft** status on purpose — the goal is to hand you something concrete to react to, not to ship.

## Live example

End-to-end example at [gerchowl/build123d examples/pbr_material_pymat.py](https://github.com/gerchowl/build123d/blob/feature/pymat-material-integration/examples/pbr_material_pymat.py). The build123d fork has SHA-pinned \`[tool.uv.sources]\` + \`[materials]\` extra overrides so a single \`uv sync\` resolves all three PRs' branches at once.

Reproducing the wood render takes about 60 seconds if you use \`uv\`:

\`\`\`bash
git clone -b feature/pymat-material-integration \\
    https://github.com/gerchowl/build123d.git
cd build123d
uv sync --extra materials --extra ocp_vscode
uv run python examples/pbr_material_pymat.py --material wood --visual
\`\`\`

Cycle through \`--material wood / steel / bricks / tiles / gold / bronze\` — all pulled from the same gpuopen presets @bernhard-42 already uses in [\`vscode-ocp-cad-viewer/examples/material-object.py\`](https://github.com/bernhard-42/vscode-ocp-cad-viewer/blob/main/examples/material-object.py).

> **Note for pip / poetry / rye users**: \`[tool.uv.sources]\` is uv-specific, so the \`ocp_vscode\` fork override won't apply to non-uv installers. pyproject.toml includes a manual \`pip install\` command for that case.

## Design points worth your input

The PoC took opinionated positions on a few questions that are worth confirming before anyone treats this direction as settled:

1. **Absorption vs. optional extra** — went with the optional extra (py-materials depends on \`threejs-materials\` as \`[pbr]\`, not the other way around, and not a vendored copy). @bernhard-42, does that match your preference for \`threejs-materials\`' long-term autonomy? The alternative (absorbing the PBR work into py-materials under a feature flag) is still on the table; ADR-0002 describes the trade-offs.

2. **\`shape.material\` type widening vs. new attribute** — went with widening the existing \`str\` attribute on \`Compound\` / \`Solid\` rather than introducing a new name. @gumyr, there's a backward-compat collision here: the existing \`material: str = \"\"\` is currently used by STEP/STL exporters as an external tool tag. The type widen preserves every existing usage, but if you'd rather rename one of them (e.g. \`material_tag\` vs \`material_object\`) or take a different shape entirely, say so — happy to rework.

3. **Offline-first / caching** — @bernhard-42, is there a way for \`threejs-materials\` users to pre-populate the cache (e.g. for CI or air-gapped environments)? The PoC depends on the first \`from_gpuopen(...)\` call downloading textures; it'd be useful to know whether that flow already has controls or would need a small PR.

4. **Adapter architecture** — PR #228 on \`vscode-ocp-cad-viewer\` is the smallest possible change: prefer \`pbr_source\` when set, fall back to the existing field-by-field copy. An alternative would be lifting \`_extract_materials_from_node\` into a shared helper so \`tcv_screenshots\` and any other headless renderer can reuse it. I didn't go there because it's a bigger scope change; flagging it if you'd prefer that direction.

All of the above is negotiable. The PoC exists specifically to make the conversation grounded in real code.

cc @bernhard-42

---

# [Comment #7]() by [gerchowl]()

_Posted on April 15, 2026 at 05:50 PM_

@bernhard-42 — apologies on two fronts before anything else:

1. I missed all four of your detailed comments above when I posted the PoC summary. I should have refreshed the thread before acting. Not my finest moment of reading the room.
2. I also missed [gumyr/build123d#1270](https://github.com/gumyr/build123d/pull/1270) entirely. For context — when I wrote the PoC I thought we were starting a concrete discussion from scratch, not joining one that had been in-flight for 9 days with real code and Roger already engaged. The three exploratory PRs (MorePET/mat#30, gumyr/build123d#1276, bernhard-42/vscode-ocp-cad-viewer#228) were intended as **minimal-effort wiring** to visualize what an integration could look like, not as a proposal that competes with gumyr/build123d#1270.

Now that I've actually read gumyr/build123d#1270 in depth:

- Your design is cleaner on the decoupling story. `build123d.Material` as the wrapper class keeps py-materials and threejs-materials fully independent — they meet in build123d. Our approach spreads the concern by adding `Material.pbr_source` to py-materials itself, which couples it to a rendering optional-extra it didn't previously have.
- `shape.material = "brass"` (string → py-materials catalog lookup) is a genuinely nice ergonomic property that our type-widen approach doesn't have.
- The three ways of assigning `shape.material` in your PR (`"brass"` / `brass` / `Material(brass, pbr=PbrProperties.from_gpuopen(...))`) mirror the existing `shape.color` API well, which keeps build123d's surface learnable.
- The screenshot with three shader balls in gumyr/build123d#1270 is a great "this is what we're aiming at" artifact. We should probably borrow it as a reference image on the mat side too.

Happy to close our three PRs and redirect effort to helping land gumyr/build123d#1270 — docs, tests, review, whatever would be useful. The three branches stay available as reference but not as competing proposals.

One small concrete win that did happen through the PoC cycle: py-materials [PR #6](https://github.com/MorePET/mat/pull/6) (your contribution!) shipped and Python 3.10 support is now live. That was listed as an open blocker in gumyr/build123d#1270's description — that box can be ticked now.

---

## Forward design questions worth opening up

These are brainstorming, not proposals. Putting them on the table because gumyr/build123d#1270's scope discussion might be the right moment to consider them, and because they overlap with your own open question about the materialx/openexr dep strategy.

### 1. Could `mat` host the MaterialX integration too, to serve consumers beyond build123d?

The current shape has downstream users taking **two direct deps** if they want physics + PBR (`py-materials` + `threejs-materials`). That's fine for build123d because build123d's `Material` wrapper abstracts it, but any other consumer — a Blender plugin, a direct three.js web app, a future CAD viewer that isn't ocp_vscode, the Rust side of `rs-materials` for Monte Carlo rendering — would still face two installs and two cadences.

One direction worth exploring: **split `mat` into a small family of subpackages under a `mat-lib` umbrella**:

- `mat-phys` — current py-materials content (physics, chemistry, density, formula, molar mass). Zero rendering concern.
- `mat-vis` or `mat-x` — MaterialX/PBR support. Consumes threejs-materials' loaders initially, or could host its own.
- `mat-lib` — meta-package that bundles both.

Downstream users get **one direct dep** (`mat-lib` for full, `mat-phys` for physics-only, `mat-vis` for rendering-only), while internally the layering stays clean. The Rust side could mirror the same split (`rs-materials-phys`, `rs-materials-vis`).

This isn't about absorbing threejs-materials — your point about keeping threejs-materials' rendering maintenance separate (for the threejs-materials ↔ three-cad-viewer bug-fixing tightness) still lands. `mat-vis` would **depend on threejs-materials**, not replace it. You stay the owner of the rendering layer; mat-vis is just a packaging/API consolidation for downstream ergonomics.

### 2. Could `mat-vis` be a pre-baked data library?

Your open question about materialx/openexr being extras (no prebuilt wheels on Windows Python 3.14, users without compilers get a bad experience) is real and annoying. What if we sidestep it entirely?

Concept: **pre-bake all the MaterialX libraries we care about into a purely-data package.** Build-time pipeline runs on Linux (where materialx + openexr compile cleanly) and dumps a big JSON index + the flat PNG/EXR textures into a repo. Downstream consumers never touch the MaterialX SDK — they just read files.

Rough shape:

```
mat-vis-data/
  ├── ambientcg/
  │   ├── Rock064/
  │   │   ├── material.json
  │   │   ├── color.png
  │   │   ├── normal.png
  │   │   └── roughness.png
  │   └── ... (2000 materials)
  ├── gpuopen/
  │   ├── Ivory Walnut Solid Wood/
  │   │   └── ...
  ├── polyhaven/
  └── physicallybased/
```

Package consumers in Python, Rust, JS, etc. would just be thin readers. The Python consumer's API matches `threejs-materials.PbrProperties.from_gpuopen(...)` exactly so existing code doesn't need to change.

Trade-offs:

- **Pro**: materialx/openexr dep problem disappears. Windows 3.14 works. CI / air-gapped environments work offline by default. Consumers in any language work with the same data.
- **Pro**: licensing is clean — all four sources are CC0 or similar permissive; mat-vis-data can legally ship the baked textures.
- **Pro**: versioning becomes meaningful — users can pin to a known material snapshot instead of "whatever gpuopen.com has today".
- **Con**: bundle size. ambientcg alone is ~2000 materials × ~5 MB each = 10 GB. We'd either ship tiers (`mat-vis-data-small` with 1K textures only, `mat-vis-data-full` with everything), or host out-of-band via a lazy fetch-from-release-assets pattern.
- **Con**: texture libraries update. A weekly rebuild workflow re-bakes new materials (we already discussed something similar for the `physicallybased.info` JSON).
- **Con**: bakes the threejs-materials → texture pipeline output at a moment in time. If you later find a baker bug and fix it in threejs-materials, mat-vis-data would need a rebuild to pick it up. Semver-able.

This could be a win for threejs-materials too — your baker becomes the build-time tool that produces canonical data, and downstream users stop hitting the "oh no, materialx wheel" wall.

### 3. Could the PBR wiring from gumyr/build123d#1270 move into mat?

Related to (1) and (2): if `mat-vis` exists, the cleanest shape might be:

- `build123d.Material` stays thin — just the wrapper class that lives in build123d, exactly as gumyr/build123d#1270 defines it
- Any "register this material" / "look up by name" logic moves into `mat-vis` so the same catalog is reachable from non-build123d consumers
- The `shape.material = "brass"` string-lookup ergonomics become build123d-specific sugar over `mat.vis.load("brass")`

This is negotiable — I'm not proposing we change gumyr/build123d#1270's direction, just asking whether gumyr/build123d#1270's PBR bits could have a home in mat for reuse. If the answer is "no, they're too build123d-specific", that's a valid answer too.

### My take on your materialx/openexr question

If (2) above is viable, the question dissolves. If not, my lean would be: **keep them as optional extras** (status quo). The Windows 3.14 user hitting a compiler error is painful but recoverable (install in a 3.13 env, bake once, switch back). The macOS/Linux user who has to remember to add `[materialx]` to their install line hits the problem on every new project. Optional-with-clear-install-message is slightly worse for ~5% of users than required; required-with-silent-wheel-failure is much worse for that same 5%.

---

## Concrete next steps on our side

- gumyr/build123d#1276 is fixed (the `ocp-vscode` main-dep slip), and I'll leave a closing comment there once you're aligned on the direction for gumyr/build123d#1270.
- Happy to close our PRs and focus on helping land gumyr/build123d#1270. Docs, tests, screenshots for the tutorial, whatever's useful.
- The materialx-baked-data-library idea is something we can sketch on the mat side as a separate tracking issue (not as a prerequisite for gumyr/build123d#1270). Would be happy to prototype if there's interest.

Again, apologies for barreling in without reading everything first. Looking forward to aligning.

cc @gumyr @jdegenstein


---

# [Comment #8]() by [gerchowl]()

_Posted on April 17, 2026 at 11:16 AM_

Closing — the integration work on our side is done:

- `Material.vis` wired up with textures from mat-vis
- `to_threejs(material)` adapter produces MeshPhysicalMaterial dict
- `Material.vis.discover()` for finding matching appearances
- Vendored mat-vis client works end-to-end

Remaining coordination is on their repos:
- ocp_vscode: accept duck-typed `to_threejs()` instead of `isinstance(PbrProperties)`
- build123d#598: material system roadmap — they can consume `mat` directly

Tracked externally, not an action item for this repo.

