# 0004 — Optical transport: wavelength curves, the surface-finish catalogue, and the substance/assembly line

**Status:** Accepted
**Issues:** [#243](https://github.com/MorePET/mat/issues/243)
**Input:** `docs/briefs/strata-optical-requirements.md` (strata light-module, 2026-08-14), strata ADR-089, gerchowl/strata#1050
**Supersedes nothing.** Extends ADR-0003 (schema foundation) into the wavelength axis.

## Context

strata — a Rust Monte Carlo PET engine — samples scintillation light
monochromatically at the emission peak, hardcodes a 200 mm absorption length,
and has no vocabulary for "the crystal is wrapped in ESR". It filed a brief
asking py-mat to own the *substance* physics and the *named surface-finish
catalogue*, and asking it explicitly **not** to own geometry, per-face
assignments, SiPM configuration, or sampling tables.

The brief's separation-of-concerns table is the contract under discussion. This
ADR accepts most of it, corrects three factual claims about py-mat, and narrows
the boundary in two places where the brief asks py-mat to hold something that,
by the brief's own reasoning, is not a material fact.

## Decisions

### 1. The line: py-mat owns substances and measured interfaces; not assemblies

Accepted, with the wording sharpened:

| Layer | Owns |
|---|---|
| **py-mat** | What a substance **is** — n(λ), attenuation, emission, decay, yield, with provenance and uncertainty. And what a **measured interface** is: a named, cited entry describing a crystal-face/reflector/coupling triple that somebody put on a goniometer. |
| **strata** | What was **built** (which face carries which finish), and **how it is simulated** (model choice, toggles, bounce caps, PDE, sampling tables). |

The operative test is not "is it about light?" but **"did someone measure it, and
does the number survive moving the part?"** A LUT for polished-ESR-with-grease
survives being moved between scanners. `sigma_alpha = 0.1` chosen to make a
model fit does not — it is a knob, and knobs are strata's.

This test is what produces the two narrowings below.

### 2. The surface-finish catalogue belongs in py-mat — as its own type (answers Q1, Q2)

**Q1 — does it belong here at all?** Yes. A measured interface is citable,
reusable, and meaningless without the substances it joins. It has the same
lifecycle as a material property: someone measures it, publishes it, and it
stays true. Splitting it into a third repo would put a citation boundary in the
middle of one physical story (LYSO's n, ESR's reflectivity, and the reflectance
of the interface between them are one narrative), and would create a repo whose
only job is to depend on this one.

**But a `Surface` is not a `Material`.** It has no density, no formula, no
composition, no mass. Modelling it as a `Material` would put objects into
`pymat.materials`, `search()`, and `mass_from_volume_mm3()` for which those
operations are nonsense, and would make `Material` mean two things. So:

- New frozen dataclass `pymat.surfaces.Surface`.
- New registry `pymat.surfaces`, mirroring the `pymat.materials` contract from
  #228 (Mapping + callable + filterable).
- Shares `Source`, `Absent`, and `WavelengthCurve` with materials — the
  provenance and curve primitives are about *values*, not about *materials*, and
  are reused verbatim.
- Inheritance works the same way (parent table → child overlay), because the
  catalogue is naturally 3 treatments × 7 wrappings and hand-repeating the
  family citation 21 times is how citations rot.

**Q2 — `surfaces.toml`, or nested under the material?** Top-level
`surfaces.toml`, not nested. An interface is a relation between two substances;
nesting it under one of them forces an arbitrary choice of owner and duplicates
every entry across every crystal it could touch. ESR-with-grease would appear
under `lyso`, `bgo`, `gagg`, … as separate copies that drift.

### 3. The catalogue holds interfaces whose optical numbers are **measured and cited** — a narrowing

Geant4's `G4OpticalSurfaceFinish` enum has 39 values. They are not all the same
kind of thing:

- **6 analytic UNIFIED/GLISUR finishes** (`polished`, `ground`,
  `polishedfrontpainted`, …) — no data file. These are *model selections*
  parameterised by `sigma_alpha`. Not measured, not citable, no provenance to
  carry. **These are strata's**, and the catalogue deliberately omits them.
- **24 LBNL LUT enum members**, of which **21 ship measured `.dat` files**
  (Janecek & Moses 2010). The other 3 (`polishedair`, `etchedair`, `groundair`)
  are bare-surface enum members with no measured data — named in a comment in
  `surfaces.toml`, deliberately **not** given entries, because an entry with no
  measurement behind it is exactly the uncited value this repo exists to prevent.
- **9 DAVIS LUT surfaces** (Roncali & Cherry 2013; Roncali/Stockhoff 2017;
  Stockhoff 2017) — all measured.

So the catalogue ships the **21 LBNL + 9 DAVIS** LUT entries, each carrying its
exact `G4OpticalSurfaceFinish` spelling, its LUT family, the
`G4RealSurface-2.2` data set it comes from, and a DOI.

**The test is measurement, not LUT-backing.** A `lut` entry is one shape a
measured interface can take; it is not the only one. An entry qualifies when
the optical numbers it carries — a reflectance scalar or spectrum — are
measured and citable. So `model = "diffuse"` and `model = "specular"` entries
belong here too, provided their `reflectivity` / `reflectivity_spectrum` has a
source. A pressed-BaSO4 reflector or an aluminium wrap is exactly as measured
as a Janecek goniometer sweep; it simply produces `R(λ)` rather than an angular
table, and the `Surface` schema had those fields from the start.

What stays out is unchanged and is the actual line: **an entry whose only
content is a fitted model parameter with no measurement behind it.** `polished`
with a `sigma_alpha` tuned until the simulation matched is a knob, not a fact,
and it belongs in the consuming engine's config.

The practical consequence for a consumer: a `lut` entry hands you an angular
reflectance distribution and you use it directly; a `diffuse`/`specular` entry
hands you `R(λ)` and the *consumer* composes it with the crystal's `n(λ)` to
get the Fresnel step. That composition depends on both materials, so it belongs
on the side that knows which two are being joined — which is also why these
entries are named for the reflector and coupling, never for the crystal.

### 4. `WavelengthCurve` — the λ twin of `TempCurve`

New primitive in `curves.py`, sharing TempCurve's validation and interpolation
helpers (one implementation, two field-name façades):

- Knots `(wavelengths_nm, values)`, strictly ascending, validated **at
  construction and therefore at TOML load**.
- **Clamps** outside the measured range. Same reasoning as ADR-0003 §2, and
  stronger here: a Sellmeier fit evaluated outside its stated validity range does
  not just lose accuracy, it returns a confident number from a divergent pole.

**Storage is unchanged.** The structured slots stay plain dicts on the
dataclasses — `refractive_index_dispersion = {wavelengths_nm, n}` and
`emission_spectrum = {wavelengths_nm, intensities}` shipped in #153/#164, are
already on disk, and round-trip through JSON in the MCP client. The curve is
built on demand by the accessors. The loader builds a throwaway curve at parse
time purely to *validate*, so a mismatched-length spectrum raises at load, not at
first query.

**Accessors are new names, not overloads:**

```python
opt.n_at(420)                        # or 420 * ureg.nm
opt.absorption_length_at(420)        # Quantity, mm
opt.emission_at(430)                 # relative intensity
opt.absorption_length_matrix_at(420)
opt.absorption_length_reabs_at(420)
```

`refractive_index_at(T)` has meant *temperature* since #148. Dispatching on
argument type would silently change behaviour for every existing caller. `n_at`
is unambiguous and is what the brief asked for.

`emission_at()` has **no scalar fallback**. `emission_peak` is one point on a
band, not a stand-in for its shape; a caller with only a peak should sample
monochromatically and know that it is doing so.

### 5. The self-absorption split is accepted as schema

A photon absorbed in a doped scintillator has two physically distinct fates, and
one lumped `absorption_length` cannot express the difference:

```toml
absorption_length_matrix = 1200.0   # mm — true loss to the host lattice
absorption_length_reabs  = 340.0    # mm — activator self-absorption
reemit_qe = 0.75                    # P(re-emitted | reabsorbed)
```

Each scalar has a `_spectrum` sibling. **Populate both channels, or declare the
missing one absent** — never leave one silently unset. A lone `_reabs` with a
bare `None` next to it implies "the rest is matrix loss", which is a claim the
data usually cannot make; a lone `_reabs` next to an explicit
`_matrix = {reason = "not-measured"}` makes exactly the right claim.

LYSO turns out to be precisely this case: its self-absorption coefficient is
measured and CC-BY-licensed, while the matrix-loss channel with cerium
subtracted has no clean measurement anywhere we could reach. Without `_absent`
(§6) that asymmetry would be inexpressible.

This is a schema decision, not a data decision. Whether any given material's
split is *measurable* is answered per material — see §6, and see
`docs/briefs/strata-optical-response.md` for LYSO specifically.

### 6. `_absent` — declared absences

The brief asks for "an explicit absent-declaration rather than folding it into
one number". Accepted, and generalised beyond optics.

`None` on a property cannot distinguish *nobody looked* from *we looked and the
number does not exist in the literature*. Those two facts should make a
downstream engine behave differently, and today they are indistinguishable.

```toml
[lyso.Ce._absent]
"optical.absorption_length_reabs" = { reason = "not-separable", note = "..." }
```

- Sidecar `Material._absent: dict[str, Absent]`, keyed by dotted property path.
- Parent-overlay inheritance, exactly like `_sources`. A child that *does* have
  the measurement simply sets the value.
- `reason` is a **closed set** — `not-measured`, `not-applicable`,
  `not-separable`, `proprietary`, `pending` — validated at load. The point of a
  declared absence is that it can be counted; free text cannot be counted.
- Accessors `mat.absent(path)` / `mat.is_absent(path)`. No `_default` fallback:
  an absence is always specific to one property.

### 7. `rs-materials` grows to **physics** parity, not full parity (answers Q4)

The brief asks for full parity with the Python schema plus a narrower view on
top. **Rejected, and replaced with something stronger.**

Full parity is parity with *what*, exactly? The Python dataclasses carry
`printable_fdm`, `machinability`, `rohs_compliant`, `lead_time_weeks`, and the
whole `vis` texture-identity layer. Mirroring those into a Monte Carlo transport
crate is a permanent maintenance and semver obligation with no consumer. Parity
as a goal also fails the moment the two sides are edited a week apart — which is
precisely how the drift the brief complains about happened in the first place.

Instead:

- **Typed, in full fidelity, for the physics domains** — optical (including
  every structured λ slot, decay components, the self-absorption split),
  nuclear, mechanical, thermal — plus curves, uncertainty (`nominal`/`stddev`),
  and `_sources`/`_absent` provenance. This is everything a transport kernel can
  use, at full resolution, with no lossy flattening.
- **`Material::raw()`** — the unparsed TOML table for the material, with parent
  overlay applied. This is the guarantee the brief actually wants: *the Rust side
  can never be the reason a field is unusable*, because every field is always
  reachable, typed or not. A promise to maintain parity would decay; an escape
  hatch does not.
- **Not mirrored:** manufacturing, compliance, sourcing, vis. Reachable via
  `raw()` if anyone ever needs them.

### 8. Where the brief's factual claims about py-mat are wrong

Recorded here because the brief will be read again later:

1. **"rs-materials 0.1.0 … still carries `radiation_length`/`interaction_length`
   under `OpticalProperties` — a live schema drift."** Not true on `main`. The
   crate is at **0.2.0**, and `NuclearProperties` has existed there, with the
   #157 migration comment, since before this brief was written. strata is pinned
   to a stale crates.io release; the fix is a version bump on strata's side.
2. **"exactly six `Option<f64>` optical scalars."** Four
   (`refractive_index`, `light_yield`, `decay_time`, `emission_peak`), plus three
   nuclear. The *shape* of the complaint — that everything structured is dropped
   — is correct and is fixed by §7.
3. **The real drift was on the Python side, and the brief missed it.**
   `sources.py:SHORT_ALIASES` still mapped `"radiation_length"` →
   `"optical.radiation_length"` after #157 moved the property to `nuclear`, so
   `mat.cite("radiation_length")` silently resolved to a path no TOML writes and
   fell through to `_default`. Fixed in this PR.

Separately, and found while implementing: `[esr.optical] reflectivity = 98.5`
has been on disk since #147, but `OpticalProperties` had no `reflectivity`
field, so the loader's `hasattr` guard **silently dropped it on every load**.
The field now exists. This is the strongest available argument for the brief's
§P2 point about provenance, from the opposite direction: a value can be cited,
committed, reviewed — and still not be there.

### 9. `default_surface` on a material is rejected — a narrowing (re: brief §P1)

The brief proposes:

```toml
[lyso.Ce.polished]
treatment = "polished"
[lyso.Ce.polished.optical]
default_surface = "surface.lyso_polished_esr_grease"   # ← rejected
```

The **variant itself is accepted and tested** — `treatment = "polished"` is a
substance-with-treatment fact, the inheritance shape works end to end, and there
is now a test pinning it (`tests/test_surfaces.py::TestInheritedVariant`).

`default_surface` is rejected by the brief's own contract. That a crystal is
*polished* is a fact about the crystal. That a polished crystal is *then wrapped
in ESR with grease, rather than in Teflon with an air gap* is a fact about the
detector somebody built — the brief's own words: "Which face is the readout is a
property of the built detector, not of LYSO. Two scanners using identical LYSO
differ here." A default wrapping is the same category of claim, only weaker,
because it is silently applied.

Nor would it work mechanically: `optical.default_surface` inherits, so every
vendor and every child variant under `lyso.Ce.polished` would silently acquire a
wrapping choice that no one made for them.

strata gets the same ergonomics by pairing a material key with a surface key in
its `.strata` file, or by putting a default in its config TOML — where run-time
policy already lives.

If a *product* is genuinely shipped pre-wrapped (a vendor part number for an
ESR-wrapped array, not a treatment), that is a real substance-side fact and we
will revisit it on the vendor node where it belongs.

### 10. The `#201` dispersion gate is an ownership rule, not a blocker (answers Q3)

`ceramics.toml:480` says *"DO NOT populate `refractive_index_dispersion` here —
the #201 refractiveindex.info enricher owns bulk dispersion; sapphire is not yet
in its scope."*

There is no blocker. `scripts/enrich_from_refractiveindex.py` (#164, tests in
#201) is an **add-only** automated enricher that pulls CC0 dispersion from the
Polyanskiy database and writes it together with a `_sources` row. It skips any
material that already has dispersion, so hand-authored data in its scope would
permanently mask the automated pull and the two would diverge invisibly.

**Does it apply to scintillators? Partly, and this matters:**

- **In scope, hand-authoring forbidden:** `nai`, `nai.Tl`, `csi`, `csi.Tl`,
  `csi.Na`, `bgo`. All six currently have *no* dispersion on disk — the enricher
  has not been run to `--write`. That is the action, not hand-authoring.
- **Out of scope, hand-authoring allowed:** `lyso`, `lso`, `gagg`, `labr3`,
  `pwo`, plastics. refractiveindex.info has no LYSO entry. These are hand-authored
  with citations, exactly as the sapphire comment intends.

The rule generalises: **automated enrichers own the property paths they write.**
Where an enricher covers a path, hand-authoring is forbidden; where it does not,
hand-authoring with a citation is the expectation. The sapphire comment was
right and should be read as scoped to the enricher's material list, not as a
freeze on dispersion data.

### 11. A photodetector is not a material — PDE does not belong here

Asked directly by strata, and decided here rather than by default.

**A SiPM does not go in py-mat.** Three reasons, in order of weight:

1. **PDE is not a property of a substance.** It is a manufactured device's
   response at an operating point — PDE(λ, V_over, T). Change the overvoltage,
   which is a run-time choice in a config file, and PDE moves by tens of
   percent; Hamamatsu's own "40% at 450 nm" is quoted *at V_over = 3 V* and is
   roughly 50% at 5–6 V. Against the §1 test — did someone measure it, and does
   the number survive moving the part? — PDE survives being moved and does not
   survive being re-biased. Bias is policy.
2. **DCR, crosstalk and afterpulse are worse on the same axis.** All are
   strongly temperature- and voltage-dependent, and dark count rate varies
   2–3× unit to unit *within one part number*. Those are facts about a specific
   die at a specific temperature, not facts about matter.
3. **A `Material` has density, formula, composition.** What is the chemical
   formula of an S13360-3050CS? The question does not type-check. The device is
   an assembly: silicon epi, quench resistors, a window, a package.

**But the parts of it that are substances do belong here, and are now present:**

- `sipm_window_silicone` (n = 1.41) and `sipm_window_epoxy` (n = 1.55). The
  window is what an optical photon actually crosses — the boundary is
  grease→window, not grease→"SiPM" — so the Fresnel step at the readout face is
  computed from cited indices on both sides.
- The crystal↔photodetector interface already exists as `davis.detector`.

**Where PDE(λ) goes:** the consuming engine's config, for now. Not a separate
devices repo — one datasheet curve does not justify a repo's overhead (CI,
releases, versioning, a second citation policy). The revisit trigger is real
and stated: ~5 devices, or a second consumer needing the same curve.

`pymat.curves.WavelengthCurve` is public and importable precisely so a consumer
can hold that curve with the same clamp-never-extrapolate contract and the same
load-time validation used here, without the device itself crossing the line.

There is a supporting fact worth recording: **no redistributable tabulated
PDE(λ) exists for the S13360-3050CS at all.** The datasheet gives a figure, not
a table, and no CC-BY paper we could find measures that exact part. So even a
consumer who wanted this in py-mat would be putting a digitised proprietary
figure here — which §P2's own standard forbids.

## Non-goals (unchanged from the brief, and honoured)

No geometry. No per-volume or per-face assignment. No SiPM or electronics
configuration. No sampling tables or inverse-CDFs. Nothing keyed by a strata
volume id. No GPU-shaped flattening — py-mat stays human-authored, cited,
unit-carrying and uncertainty-aware; strata does the resampling.

## Consequences

- `curves.py` grows a second curve type; TempCurve's public API is byte-identical
  (validation and interpolation moved to shared helpers).
- `OpticalProperties` grows `reflectivity`, six `_spectrum`/split fields,
  `reemit_qe`, and eight accessors. All additive; no existing field changes type.
- A new data file, `surfaces.toml`, is picked up automatically by the
  `check_licenses.py` gate (it globs `data/*.toml`), so the 30 catalogue entries
  are license-checked from day one.
- `rs-materials` takes a minor version bump. strata must unpin from 0.1.0.
- Materials may now assert that a value does not exist, and that assertion is
  itself checkable.

## Alternatives considered

- **`Surface` as a `Material` in `surfaces.toml`.** Cheapest to build — the
  loader, inheritance, `_sources` and registry all come free. Rejected because it
  makes `Material` mean two things and puts massless, formula-less objects into
  `pymat.materials`, `search()` and `mass_from_volume_mm3()`.
- **Finishes nested under the material they are measured against.** Rejected:
  an interface is a relation, so nesting picks an arbitrary owner and duplicates
  every entry across every crystal it could touch.
- **Overloading `refractive_index_at()` on argument type** (Quantity-in-Kelvin
  vs Quantity-in-nm). Rejected as a silent behaviour change for every caller
  since #148.
- **Promoting the structured λ slots from `dict` to `WavelengthCurve` on the
  dataclass.** Rejected: breaks the JSON round-trip in the MCP client and the
  on-disk shape written by the #164 enricher, for no gain the accessors do not
  already provide.
- **Full Python-schema parity in `rs-materials`.** Rejected in favour of typed
  physics plus `raw()` — see §7.
- **Free-text `_absent` reasons.** Rejected: the point of a declared absence is
  that it can be counted.

## Upgrade trigger

Revisit when any of these becomes true:

- A vendor ships a genuinely pre-wrapped assembly as a catalogue part, making
  "as-shipped finish" a substance-side product fact (§9).
- Someone publishes a redistributable tabulated LYSO:Ce emission spectrum, or
  paid access to Chen 2011 makes the Sellmeier coefficients available — both are
  currently `_absent` and both would flip to real data.
- A measured interface appears that is not in `G4RealSurface`, forcing the
  catalogue's `lut_*` identity fields to become optional in practice rather than
  just in the type.
- Non-physics fields acquire a Rust consumer, at which point `raw()` stops being
  sufficient and §7's line moves.
