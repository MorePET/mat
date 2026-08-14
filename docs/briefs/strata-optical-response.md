# Response: optical properties for downstream MC transport

**From:** py-mat, 2026-08-14
**Re:** `docs/briefs/strata-optical-requirements.md` (strata light-module), strata ADR-089, gerchowl/strata#1050
**Decision record:** `docs/decisions/0004-optical-transport-and-surface-finishes.md`
**Branch:** `feat/optical-transport-schema`

The contract is accepted with two narrowings and three factual corrections. The
P0 work is built and tested. The P1 data work ran into a wall that is itself the
most important thing in this document — read §4 before you plan the sampling
code.

---

## 1. Answers to your four open questions

### Q1 — Does the surface-finish catalogue belong in py-mat?

**Yes.** A measured interface is citable, reusable, and meaningless without the
substances it joins; it has exactly the lifecycle of a material property.
Splitting it into a third repo would put a citation boundary in the middle of
one physical story and create a repo whose only job is to depend on this one.

**But a `Surface` is not a `Material`,** and it is not modelled as one. It has
no density, no formula, no mass. Making it a `Material` would put objects into
`pymat.materials`, `search()` and `mass_from_volume_mm3()` for which those
operations are nonsense. It is a separate frozen dataclass with a separate
registry, sharing the `Source` / `Absent` / `WavelengthCurve` primitives.

```python
from pymat import surfaces
s = surfaces["davis.polished_esr_grease"]
s.lut_surface        # 'PolishedESRGrease_LUT' — exact G4 enum spelling
s.coupling           # 'optical_contact'
s.coupling_index     # 1.465
surfaces(coupling="air_gap")   # -> 19 entries
```

### Q2 — `surfaces.toml`, or nested under the material?

**Top-level `surfaces.toml`, not nested.** An interface is a relation between
two substances; nesting it under one of them forces an arbitrary choice of owner
and duplicates every entry across every crystal it could touch. ESR-with-grease
would appear under `lyso`, `bgo`, `gagg`, … as copies that drift.

Your draft schema had `pair = ["lyso", "surface.esr.grease"]`. **Dropped** — it
mixes a material reference with a surface reference in one list, and more
importantly it asserts that the LUT is LYSO-specific. It is not: Geant4 applies
these tables at any dielectric boundary. What the catalogue carries instead is
`reflector_material` and `coupling_material` (real material keys that resolve,
and there is a test that they do), plus the citation to the paper where the
measurement substrate is described.

### Q3 — What blocks dispersion data at `ceramics.toml:480`?

**Nothing. It is an ownership rule, not a blocker,** and you should read it as
scoped to one tool's material list rather than as a freeze.

`scripts/enrich_from_refractiveindex.py` (#164, tests in #201) is an **add-only**
enricher that pulls CC0 dispersion from the Polyanskiy database and writes it
with a `_sources` row. It skips any material that already has dispersion, so
hand-authored data inside its scope would permanently mask the automated pull and
the two would diverge invisibly. Hence "do not hand-author here".

It applies to scintillators, and this matters to you:

| Material | Status | What to do |
|---|---|---|
| `nai`, `nai.Tl`, `csi`, `csi.Tl`, `csi.Na`, `bgo` | In scope, **currently empty on disk** | Run the enricher with `--write`. Do not hand-author. |
| `lyso`, `lso`, `gagg`, `labr3`, `pwo`, plastics | Out of scope | Hand-author with citations — but see §4 for LYSO. |

For BGO specifically the data exists and is clean: Williams et al., *Appl. Opt.*
**35**, 3562 (1996), doi:10.1364/AO.35.003562, republished CC0 by
refractiveindex.info. It gives n = 2.177 at 420 nm and 2.080 at the 480 nm
emission peak — **note that the scalar 2.15 currently in the database sits
between them, so your monochromatic-at-peak sampling is off by ~3% in n at the
peak, in the direction that makes the critical angle wrong.** The action is to
run the enricher, and that is recorded in a comment on `[bgo.optical]`.

### Q4 — Full parity for `rs-materials`, or a narrower transport view?

**Neither. Full fidelity for the physics, plus a guarantee instead of a promise.**

Full parity is parity with *what*? The Python dataclasses carry `printable_fdm`,
`machinability`, `rohs_compliant`, `lead_time_weeks` and a texture-identity
layer. Mirroring those into a Monte Carlo crate is a permanent maintenance and
semver obligation with no consumer. Parity as a goal also fails the moment the
two sides are edited a week apart — which is exactly how the drift you complained
about arises.

So `rs-materials 0.3.0`:

- **Typed in full fidelity** for optical, nuclear, mechanical, thermal —
  including every structured λ slot, temperature curves, decay components, the
  self-absorption split, uncertainty, `_sources` and `_absent`.
- **`Material::raw()`** returns the merged TOML table with parent overlay
  applied. This is the guarantee you actually asked for: *the Rust side can
  never be the reason a field is unusable*, because every field is always
  reachable, typed or not.
- Not mirrored: manufacturing, compliance, sourcing, vis. Reachable via `raw()`.

---

## 2. Where the brief was wrong about py-mat

Recorded because the brief will be read again later, and because one of these
means you have a bug to fix on your side.

1. **"rs-materials 0.1.0 … still carries `radiation_length`/`interaction_length`
   under `OpticalProperties` — a live schema drift."**
   Not true on `main`. The crate was at **0.2.0** and `NuclearProperties` has
   existed there, with the #157 migration comment, since before the brief was
   written. **You are pinned to a stale crates.io release.** Bump to 0.3.0.

2. **"exactly six `Option<f64>` optical scalars."** Four (`refractive_index`,
   `light_yield`, `decay_time`, `emission_peak`), plus three nuclear. The shape
   of the complaint — everything structured is dropped — was correct and is fixed.

3. **The real drift was on the Python side and the brief missed it.**
   `sources.py:SHORT_ALIASES` still mapped `"radiation_length"` →
   `"optical.radiation_length"` after #157 moved the property to `nuclear`, so
   `mat.cite("radiation_length")` silently resolved to a path no TOML writes.
   Fixed here.

And three found while implementing, the first of which is the strongest possible
argument for your own §P2 point, from the opposite direction:

4. **`[esr.optical] reflectivity = 98.5` had been on disk since #147 and was
   silently dropped on every single load** — `OpticalProperties` had no
   `reflectivity` field, so the loader's `hasattr` guard swallowed it. A value
   can be cited, committed, reviewed, and still not be there. A corpus-wide audit
   found four more (`optical.dopant`, `optical.dopant_pct`,
   `compliance.flammable`, `compliance.toxic`, plus `electrical.permeability`
   filed under the wrong group). All fixed, and there is now a test that fails if
   any TOML key anywhere lacks a field to land in.

5. **Every *root* material silently lost its `grade`, `temper`, `treatment` and
   `vendor`.** `loader.py` wrote `grade or parent.grade if parent else None`,
   which Python parses as `(grade or parent.grade) if parent else None` — so
   with no parent the whole expression collapsed to `None` and the node's own
   value was thrown away. `pymat.beryllium.grade` was `None` despite the TOML
   saying `"S-200F"`. Eleven grades and six vendors across the corpus. Child
   materials were unaffected, which is why it survived this long.

6. **The Rust side merged child `tags` over the parent's instead of unioning
   them**, so `stainless.s316L` reported 4 tags where py-mat reports 7 —
   a divergence from the #132 inherit-and-extend rule.

**Neither of those last two was found by reading code.** They fell out of a
mechanical cross-check, which is now a permanent gate:
`tests/test_rs_python_parity.py` drives the Rust loader and diffs 28 fields
across every material against the Python loader — 144 materials, ~4000 value
pairs including the `_sources` and `_absent` key sets, zero tolerance. It runs in the `rust` CI job, the only one with both
toolchains, and it was mutation-tested by reintroducing bug 5 and confirming it
fails with a readable diff.

That gate is the real answer to the drift complaint behind your brief. The
schema already had provenance, uncertainty and curves; what it did not have was
anything checking that the two readers of the same file agreed about what it
said. Now it does, and the next time the Rust side lags you will find out from
CI rather than from a downstream simulation being quietly wrong.

---

## 3. Where we narrowed the contract — two disagreements

### 3a. The catalogue holds *measured* interfaces only

Geant4's `G4OpticalSurfaceFinish` has 39 values and they are not the same kind
of thing. The catalogue ships **30**: the 21 LBNL LUTs that have `.dat` files
and the 9 DAVIS LUTs. Excluded on purpose:

- **The 6 analytic UNIFIED/GLISUR finishes** (`polished`, `ground`,
  `polishedfrontpainted`, …). No data file. They are model selections
  parameterised by a fitted `sigma_alpha`. Not measured, not citable — **these
  are yours**, in the config TOML where run-time policy already lives.
- **`polishedair`, `etchedair`, `groundair`.** These *are* `dielectric_LUT` enum
  members, but `ReadLUTFile()` finds no `.dat` for them. They are named in a
  comment in `surfaces.toml` so the omission is greppable rather than silent.

If you look up `surfaces["polished"]` you get a `KeyError` that explains this
rather than a miss.

### 3b. `default_surface` on a material is rejected

Your P1 proposal:

```toml
[lyso.Ce.polished]
treatment = "polished"
[lyso.Ce.polished.optical]
default_surface = "surface.lyso_polished_esr_grease"   # <- rejected
```

**The variant is accepted, built and tested** (`pymat.lyso.Ce.polished`,
`tests/test_surfaces.py::TestInheritedVariant`, 8 assertions, plus a Rust test).
Inheritance works end to end: it picks up light yield and dopant from `lyso.Ce`,
refractive index and emission peak from `lyso`, the self-absorption channel,
the `_sources` rows, and the `_absent` declarations.

`default_surface` is rejected **by your own contract**. You wrote: *"Which face
is the readout is a property of the built detector, not of LYSO. Two scanners
using identical LYSO differ here."* A default wrapping is the same category of
claim, only weaker, because it is applied silently. That a crystal is *polished*
is a fact about the crystal; that a polished crystal is then wrapped in ESR with
grease *rather than Teflon in an air gap* is a fact about a detector somebody
built.

It also would not work mechanically: `optical.default_surface` inherits, so every
vendor node under `lyso.Ce.polished` would acquire a wrapping choice nobody made
for them.

What you do instead is a two-key lookup — a material key and a surface key,
paired in `.strata` or defaulted in your config. There is a test showing both
halves resolving. If a vendor genuinely ships a pre-wrapped assembly, that is a
real product fact and we will revisit it on the vendor node, where it belongs.

---

## 4. The LYSO data — read this before writing the sampler

You called `emission_spectrum` "the single highest-value field in this brief".
We could not populate it, and the reason is not laziness.

**There is no tabulated (wavelength, intensity) LYSO:Ce emission spectrum in a
redistributable source.** The two papers that plot one — Mao/Zhang/Zhu 2008
(doi:10.1109/TNS.2008.922804) and Melcher & Schweitzer's original LSO
characterisation — are paywalled figures. Digitising them produces a derivative
of a proprietary figure, which this repo's licence policy does not permit and
which would in any case be an uncited number wearing a citation.

So the field is **declared absent**, with the reason, the search, and what would
close it:

```python
pymat.lyso.absent("optical.emission_spectrum").reason   # 'proprietary'
pymat.lyso.absent("optical.emission_spectrum").note     # the full story
```

This is the mechanism your brief asked for ("an explicit absent-declaration
rather than folding it into one number"), generalised: `Material._absent`, a
sidecar keyed by dotted property path with a **closed** reason vocabulary
(`not-measured`, `not-applicable`, `not-separable`, `proprietary`, `pending`),
inheriting exactly like `_sources`. `None` with no declaration means "nobody
looked"; `None` with a declaration means "we looked and the number does not
exist". Those should make your engine behave differently.

**What you should do with the emission band.** These parameters ARE cited and
CC-BY (Bosca & Lopez, *Sci. Rep.* **13**, 7199 (2023),
doi:10.1038/s41598-023-32689-z): band centre 430 nm, FWHM 60 nm, two
inequivalent Ce sites (Ce1 at 393 and 427 nm, Ce2 near 460 nm), peak 420 nm from
the vendor datasheets. **Synthesise the curve on your side and label it
synthesised** — in the parquet manifest, not in a comment. A sampled band built
from cited parameters and marked as constructed is honest; the same curve shipped
from here as if it were measured is not.

### What LYSO now carries, all cited

| Field | Value | Source | Licence |
|---|---|---|---|
| `refractive_index` | 1.82 | Chen/Mao/Zhu 2011, doi:10.1016/j.optmat.2011.10.006 | proprietary-ref |
| `emission_range` | [380, 600] nm | Bosca & Lopez 2023 | CC-BY-4.0 |
| `absorption_length` | 200 mm | Usubov 2013, arXiv:1305.3010 | proprietary-ref |
| `absorption_length_reabs` | **588 mm** | Bosca & Lopez 2023 | **CC-BY-4.0** |
| `rise_time` (on `lyso.Ce`) | 0.072 ns | Seifert et al. 2012, JINST 7 P09004 | CC-BY-3.0 |
| `temperature_coefficient_light_yield` | −0.15 %/°C | Tully 2022, arXiv:2205.14890 | proprietary-ref |
| `intrinsic_activity_Bq_per_g` | 40 | Enríquez-Mier-y-Terán 2020, doi:10.1186/s40658-020-00291-1 | CC-BY-4.0 |
| `hygroscopic` | false | Luxium PreLude 420 | proprietary-ref |

**Three things in that table need your attention:**

1. **Your 200 mm literal is a Monte-Carlo convention, not a measurement.** It is
   in the database now, but the source note says so in capital letters. The chain:
   Usubov 2013 adopts 20 cm flat across the band, inferred from Vilardi et al.
   2006 (doi:10.1016/j.nima.2006.04.079), who measured ~10 cm **effective**
   attenuation in 3.2×3.2×100 mm bars — a figure that includes surface and
   wrapping losses and is therefore a lower bound on the bulk value. Other
   simulation papers use 15 cm and 40 cm. Treat it as a tunable, not a constant.

2. **The self-absorption split is real and half-measured.** Bosca & Lopez measure
   α_L = 1.7×10⁻² cm⁻¹ in the emission band over 105 mm of propagation →
   `absorption_length_reabs = 588 mm`, CC-BY, directly usable. The **matrix**
   channel with cerium subtracted has no clean measurement anywhere we could
   reach, and is declared absent rather than back-computed from
   `absorption_length − absorption_length_reabs`, which would silently promote
   the Monte-Carlo convention above into a measurement.

   Note what this does to your 10–30% estimate: 588 mm over a 20 mm crystal is
   ~3.4% single-pass reabsorption, not 10–30%. Over 5–20 bounces the path length
   is longer, so your figure may still be right, but the single-pass number is an
   order of magnitude below the brief's estimate and the discrepancy is worth
   resolving before you tune anything against it.

3. **`reemit_qe` does not exist as a measured quantity.** Declared absent. The
   number usually pressed into this role is Bosca & Lopez's absolute
   photoluminescence quantum yield, **PLQY = 0.51** at 365 nm excitation — but
   PLQY under external UV pumping is not re-emission efficiency following
   self-absorption *within* the emission band. If you need a value, adopt 0.51
   explicitly as an assumption anchored to that paper, **in your run config where
   the assumption is visible**, not as a database constant.

Also declared absent for LYSO: `refractive_index_dispersion` (Sellmeier
coefficients exist in Chen 2011 and Petrosyan 2015 but both are paywalled;
refractiveindex.info carries neither LSO nor LYSO — verified twice, so this is a
real absence, not a tooling artifact) and `decay_components` (the review
literature repeats "fast 20–30 ns at 10–40%, slow ~43 ns at 60–90%" but it could
not be tied to a single measurement paper for standard uncodoped LYSO:Ce at room
temperature).

One data correction: `lyso.Ce.saint_gobain.prelude420.light_yield` was **34000**,
an uncited round-up. The Luxium PreLude 420 data sheet says **33200**. Fixed.

### What is deliberately *not* done yet

`gagg`, `nai_tl`, `csi_tl` and the plastics were on the P1 list and are
**untouched**. This is a refusal, not an omission: the literature sweep behind
this PR covered LYSO and BGO only, and adding values to the others would mean
either copying them from the existing uncited numbers or asserting
`_absent` reasons for searches nobody ran. Both are worse than leaving them
alone, by the standard your own §P2 sets. They need the same treatment LYSO
got — a real source sweep — and that is a follow-up, not a five-minute edit.

What *is* free for four of them: `nai`, `nai.Tl`, `csi`, `csi.Tl`, `csi.Na` are
inside the enricher's scope, so their dispersion is one command away. The rule
is now stated once at the top of `scintillators.toml` rather than per-material.

---

## 5. What shipped

**Python**

- `pymat.curves.WavelengthCurve` — the λ twin of `TempCurve`, sharing its
  validation and interpolation helpers. Clamps, never extrapolates; validated at
  construction and therefore at load. `range_nm` tells you where the data stops,
  which is what your resampler needs so it does not fabricate the tails.
- Accessors on `OpticalProperties`: `n_at(λ)`, `absorption_length_at(λ)`,
  `absorption_length_matrix_at(λ)`, `absorption_length_reabs_at(λ)`,
  `emission_at(λ)`, plus `*_curve` properties. All take a Pint Quantity or bare
  nm. `emission_at` has **no** scalar fallback by design.
  `refractive_index_at(T)` still means temperature — that is why the new ones are
  named differently.
- New optical fields: `reflectivity`, `absorption_length_spectrum`, the
  `_matrix`/`_reabs` split with `_spectrum` siblings, `reemit_qe`, `dopant`,
  `dopant_pct`.
- `Material._absent` + `mat.absent(path)` / `mat.is_absent(path)`.
- `pymat.surfaces` — 30 measured interfaces, Mapping + callable + filterable,
  mirroring the `pymat.materials` contract from #228.
- Structured spectra are validated at load, so a mismatched-length table raises
  in the loader rather than at first query.

**Data**

- `src/pymat/data/surfaces.toml` — 21 LBNL + 9 DAVIS, every entry carrying its
  exact `G4OpticalSurfaceFinish` spelling, its `G4SurfaceType`, the
  `G4RealSurface-2.2` data set, and DOIs (Janecek & Moses 2010
  10.1109/TNS.2010.2042731; Roncali & Cherry 2013 10.1088/0031-9155/58/7/2185;
  Roncali/Stockhoff 2017 10.1088/1361-6560/aa6ca5; Stockhoff 2017
  10.1088/1361-6560/aa7007).
- Air gap vs optical contact is a validated closed vocabulary. An entry declaring
  `optical_contact` **must** carry `coupling_index` — the index of the filler is
  the whole physical difference — and an entry declaring `air_gap` must not.
  LBNL glue is Cargille Meltmount n = 1.582; DAVIS grease is BC-630 n = 1.465,
  which is already a material (`bc630`) in this database.
- Worth knowing for your model: 3M ESR is a multilayer interference stack
  designed for an air interface, so wet-coupling measurably *lowers* its
  effective reflectivity (Kang et al., NIM A 2017,
  doi:10.1016/j.nima.2017.02.032). The `*_air` and `*Grease` LUTs are separate
  measurements for two independent physical reasons, not one surface with a
  different gap material.
- Also: Lumirror is Toray voided PET and reflects **diffusely**. It is not ESR.
  The LBNL family contains both and they behave qualitatively differently.

**Rust — `rs-materials 0.3.0`**

- `Curve` with `interpolate` / `range` / `covers` / `resample(lo, hi, n)` — the
  last one is there so your 128-node λ grid is one call.
- `OpticalProperties` grew from 4 scalars to the full set including every
  spectrum, both temperature and wavelength curves, decay components, and the
  self-absorption split. `NuclearProperties`, `MechanicalProperties`,
  `ThermalProperties` too.
- `Source` / `Absent` sidecars with `source_of()` / `is_absent()` /
  `absent_reason()`.
- Per-field uncertainty via `stddev_of("light_yield")`. No material in the corpus
  uses it yet — the schema landed in #149 but the data sweep has not happened.
- `SurfaceDb` with `by_lut_surface("PolishedESRGrease_LUT")` — the reverse index
  you need when holding a Geant4 finish name — plus `family()` and
  `with_coupling()`.
- `Material::raw()`, the escape hatch.
- **Two parser bugs fixed while in there.** Inheritance only ever consulted *one*
  level of parent, so `lyso.Ce.saint_gobain.prelude420` silently lost everything
  its grandparent declared; and property groups were replaced wholesale rather
  than merged key-by-key, so a child that overrode `light_yield` dropped its
  parent's `refractive_index`. Both are now tested.
- `PROPERTY_GROUPS` was missing `magnetic`, `vacuum`, `nuclear`, `vis`, `custom`.
  They avoided being mis-parsed as child materials only by accident.
- **Behaviour change to know about:** `formula` no longer inherits from the
  parent node. py-mat's loader does not inherit it either
  (`pymat.lyso.Ce.saint_gobain.prelude420.formula` is `None`), so the old
  one-level lookup was itself a silent divergence from the source of truth. If
  you were relying on it, you were relying on a bug. Whether Python *should*
  inherit formula is a separate question worth raising as an issue.

**Tests:** 1069 Python (144 new, incl. the loader-parity gate), 104 Rust (67 new). License gate passes on all
8 TOMLs — `surfaces.toml` is covered automatically because the gate globs
`data/*.toml`. `CC-BY-3.0` was added to the allow-list for JINST.

---

## 6. What is on your side now

1. **Unpin `rs-materials` from 0.1.0.** Go to 0.3.0. Several of your complaints
   were already fixed in 0.2.0.
2. **Synthesise the LYSO emission band from the cited Bosca & Lopez parameters,
   and label it synthesised in the manifest.** Do not wait for a curve from here;
   it is not coming without paid journal access.
3. **Run the refractiveindex.info enricher for `bgo`, `nai`, `nai.Tl`, `csi`,
   `csi.Tl`, `csi.Na`** — or ask us to. It is one command and it will fix the ~3%
   n error at BGO's emission peak.
4. **Reconcile the 10–30% reabsorption estimate** against the measured
   588 mm / 3.4%-per-pass figure before tuning against either.
5. **Decide `reemit_qe` in your config**, anchored to PLQY = 0.51, with the
   assumption visible.
6. **Take the analytic UNIFIED finishes and `sigma_alpha` into your config.**
   They are not coming from here.
7. **Check `Curve::covers()` before resampling.** Every curve clamps silently
   outside its measured range — that is deliberate, and it means a 300–800 nm
   grid laid over a 400–700 nm measurement will hand you 100 nm of fabricated
   flat line unless you look.

Open the PR discussion on ADR-0004 if you want to contest either narrowing. §3b
in particular is a judgement call, and it is your brief's own reasoning that
decided it.

---

# Round 2 — the concrete detector

strata came back with a specific module to support (8×8 LYSO 3×3×25 mm, 0.2 mm
BaSO4 septa, aluminium outer wrap, grease-coupled SiPM on the −z end) and,
more usefully, with a **sensitivity result that re-ordered the work**.

## What changed the priorities

Their measurement, 20k photons, identical seeds, absorption length swept:

| absorption length | mean CE | readout end | far end | DOI ratio |
|---|---|---|---|---|
| 200 mm (MC convention) | 0.2206 | 0.6139 | 0.0730 | 8.4 : 1 |
| 588 mm (measured Ce channel) | 0.2590 | 0.6470 | 0.1039 | 6.2 : 1 |

A 2.9× change in absorption length moves mean collection efficiency by only
+17% relative, and reflector loss ran 25% at the readout end to 63% at the far
end against 13→29% for bulk. The conclusion drawn at the time — *the reflector
dominates, so reflectance provenance outranks scintillator bulk data* — is what
re-ordered the work.

> ⚠️ **RETRACTED in round 3, and the retraction is the more useful result.**
> That sweep was computed at an assumed reflectance of 0.97. At the cited value
> the model inverts: far-end wrap loss goes from 64% to **5%**, and bulk loss
> from 29% to **69%**. The reflector does not dominate; at a realistic
> reflectance the *crystal* does.
>
> The re-prioritisation was still correct, but **for the opposite reason to the
> one given**: reflectance provenance mattered enormously because the assumed
> value was wrong, not because reflector loss is the dominant channel.
>
> Kept visible rather than edited away, because a sensitivity analysis computed
> at an unmeasured parameter is exactly the failure mode this document is about
> — and it is one that produced a *right answer from wrong reasoning*, which is
> the hardest kind to catch.

**The deeper finding: the two parameters interact, so no standalone sensitivity
is meaningful.** Absorption length moves collection efficiency by +17% at
R = 0.97 and by **+53%** at R = 0.999. At low reflectivity photons die at the
wrap before path length can matter; at high reflectivity they survive long
enough to accumulate path, and absorption takes over. Any statement of the form
"parameter X is second-order" is only true at whatever value of Y it was
computed at.

The practical consequence for this repository: **the measured 588 mm
self-absorption channel is worth substantially more than the round-2 analysis
credited**, and the 200 mm lumped convention is correspondingly more dangerous
— see the strengthened source note on `[lyso.optical] absorption_length`.

### A design tension the data now prices

Falling out of the same 2D sweep, and worth recording because it is not
obvious: **a better reflector destroys depth-of-interaction resolution.** Across
R = 0.97 → 0.999 the depth gradient collapses from 8.4:1 to 1.6:1. Uniform light
collection is what you want for energy resolution and precisely what you must
not have for depth encoding.

That makes the *uncertainty* on the BaSO4 number load-bearing in both
directions, not just the value — which is a good argument for shipping the
0.98–0.999 bracket rather than a point estimate.

## BaSO4 — the number that mattered

Grum & Luckey 1968 (doi:10.1364/AO.7.002289), the primary reference for pressed
BaSO4 as a reflectance standard: **0.999 at 420–470 nm**, 0.985 at 350 nm.
strata's working estimate was **0.97**.

    0.970 ^ 40 = 0.296
    0.999 ^ 40 = 0.961

That is not a refinement, it is a different model. Three caveats travel with it
in the TOML header, and they matter more than the headline: the cited values are
pressed powder at high packing density measured in an integrating sphere; the
paper's own BaSO4/PVA *paint* measures 0.992; and a septum is bounded by crystal
faces rather than open to a sphere. The honest bracket is ~0.98–0.999. Every
point of it is above 0.97, so the *direction* is certain even where the value is
not — which is the right way to hand over a number like this.

## A question that decided model structure, not just a value

Patterson 1977 (doi:10.1364/AO.16.000729) gives Kubelka-Munk coefficients:
`s = 572 cm⁻¹` at 500 nm → a ~17 µm scattering mean free path → **0.2 mm is
~12 scattering lengths, so the septum is effectively optically thick.** No need
to transport into it; a surface entry suffices.

But only just. Coating vendors specify 0.5–0.6 mm because real coatings pack
looser than a pressed pellet. If the septum is paint or a loaded binder, light
leaks through into the neighbouring crystal — **an inter-crystal crosstalk
channel the model does not currently have**. That is a gap in the physics, not
in the data, and it would surface as crosstalk that cannot be reproduced.

> **This claim went through three states. All three are kept, because the
> sequence is more instructive than any one of them.**
>
> 1. **Asserted** (above), unqualified: 0.2 mm is optically thick.
> 2. **Retracted** in round 3, when a measured 15% inter-crystal light share
>    arrived and the K-M finite-layer solution gave T = 7.6% at 0.2 mm. I
>    concluded the claim was simply wrong and said so.
> 3. **Attempted un-retraction, itself wrong.** The consumer proposed that the
>    retraction was computed at an unstated condition: T = 7.6% is the
>    *normal-incidence* figure, and TIR-trapped light in a 3×3×25 mm crystal
>    was said to meet the side walls at ~76.7°, giving `d/cos θ ≈ 4.34 d` and
>    **R = 96.9%, T = 1.35%** — the semi-infinite limit. On that basis they
>    recommended un-striking the original claim. **This repository declined to
>    un-strike it, on principle, before the evidence arrived.**
> 4. **Falsified.** They instrumented the mechanism's own prediction rather
>    than the number it was fitted to, and measured the mean side-wall
>    incidence at **47.8°, not 76.7°** — a factor 2.9 in path length. The
>    reason is clean and had been in front of both of us: **the septum is
>    Lambertian, and a diffuse reflector randomises direction on first
>    contact.** Mean `|cos θ| = 2/3` exactly → 48.2°, *independent of aspect
>    ratio*. The grazing-incidence story reasoned about the angular
>    distribution of trapped light and forgot that the wall being reasoned
>    about destroys that distribution.
>
> **So the retraction at state 2 stands as originally written.** At 48° the
> path multiplier is 1.49, nowhere near optically thick: a 0.2 mm septum
> transmits ~5%. The original unqualified claim was simply wrong, and the
> attempt to rescue it with a condition was wrong too.
>
> Recorded at four states rather than edited to the final one. A two-state
> record cannot represent "struck → argued back → struck again", and the
> sequence is the instructive part: **two plausible mechanisms, both
> constructed after the fit to explain a value already chosen, both surviving
> review by two parties, both killed by measurement rather than by scrutiny.**

### What this cost, and the failure mode it belongs to

Working from the normal-incidence number, the consumer initially identified
per-encounter transmittance with the observed light share — different
quantities, since a photon meets a septum ~40 times in this geometry — and on
that arithmetic fitted the scattering coefficient down to 47% of pellet
density. That fit was offered to this repository as a property of BaSO4. It was
declined, for the reason given in round 3: *a fit against one module is a
measurement of that module, not of the material.* Had it been accepted, an
arithmetic error would now be recorded here as a material constant, cited.

Note what caught it, though — not the headline number, which could have been
tuned to agree, but the **shape**: at T = 0.076 per encounter the simulated
crosstalk had *further* crystals exceeding *direct* neighbours, where the
measurement falls off. A second constraint on the same data is what made the
first one falsifiable.

And note the failure mode on this side, because it is the one named in round 3
arriving from the other direction. `km_transmittance_at` was correct, cited,
tested, and complete for the question it answers — normal incidence. **Not a
wrong value, and not a missing one: a right one answering an adjacent
question.** The accessors now take an incidence angle for that reason.

But the fix carried its own trap, and it is worth stating because this
repository built it: **an `incidence_deg` parameter invites exactly the error
that followed.** Kubelka-Munk `k` and `s` are *already* defined for diffuse
flux — the obliquity is averaged into them, which is the origin of the factor 2
in the usual `K = 2k` convention — so for diffusely-illuminated layers plain
`d` is correct and multiplying by `1/cos θ` double-counts. Offering a knob
without saying loudly when *not* to turn it is another way of answering an
adjacent question. The docstrings now lead with when to leave it at zero.

### The sharpened lesson

Round 3 recorded: *a fit with one constraint is a reparameterisation, a fit
with two is a test.* This round sharpens it, and the consumer's phrasing is
better than mine:

> **The second constraint has to be a prediction of the *mechanism*, not
> another property of the outcome.**

Their further-vs-direct crosstalk shape was a genuine second constraint and did
real work — it killed the packing-density fit. But it could not distinguish
grazing incidence from anything else producing the same transmittance, because
it says nothing about *angle*. Only instrumenting the angle could, and when
they did, the mechanism died in an hour.

For any fitted parameter: ask what **else** the proposed mechanism asserts, and
go measure *that*.

## Aluminium — derived, not stored

The `--write` enricher run put Rakić CC0 n,k on disk, so reflectance became
derivable rather than typed:

    OpticalProperties.normal_reflectance_at(420)  ->  92.46 %

92.29% mean over 400–500 nm, with the interband dip at 800 nm (now a test —
if either the CC0 pull or the Fresnel derivation breaks, that shape is what
stops looking right). strata replaced its own 0.88 estimate with it.

Derived beats stored here: a hand-entered scalar can drift from the n,k it is
supposed to be consistent with, and nothing would notice. The surface entry
carries an explicit `_absent` on `reflectivity` saying exactly that.

## Where the line got drawn again

**A photodetector is not a material** (ADR-0004 §11). PDE is a device response
at an operating point — it survives moving the part and does not survive
re-biasing it. The window *is* a substance and is now present in both variants,
which caught a real error: the S13360 **CS** package window is silicone at
**n = 1.41**, not the 1.55 both sides were carrying (that is the **PE** epoxy
variant). From BC-630 grease at 1.465 those are qualitatively different — CS
steps the index down and puts a TIR cone at the readout face, PE does not.

An independent fact settles the same question without appeal to principle:
**no redistributable tabulated PDE(λ) exists for the S13360-3050CS at all.**
Datasheet figure, no table, no CC-BY paper on that exact part. Putting it here
would mean shipping a digitised proprietary figure — the thing we refused to do
for LYSO's emission spectrum.

**`contact.grease_sipm` was requested and refused.** It would carry no measured
number of its own — the grease index is on `bc630`, the window index is on
`sipm_window_silicone` — only the pairing, and pairing is assembly. A test pins
its absence so the reasoning cannot be quietly reversed.

## Self-inflicted bug, worth recording

`reflectivity_spectrum` was registered in the loader's validation table with no
dataclass field behind it: validated, then silently dropped. **That is the exact
bug class this branch audited the corpus for, reintroduced by me**, in the one
direction the corpus scan cannot see — no shipped file used the slot yet, so
nothing failed. There is now a structural test that every validated slot has a
field to land in.

The lesson generalises past this repo: a scan over *existing data* cannot find a
gap that only opens when new data arrives. The invariant has to be checked
against the schema, not against the corpus.
