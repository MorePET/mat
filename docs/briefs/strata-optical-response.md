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
`tests/test_rs_python_parity.py` drives the Rust loader and diffs 26 fields
across every material against the Python loader — 144 materials, ~3700 value
pairs, zero tolerance. It runs in the `rust` CI job, the only one with both
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

**Tests:** 1064 Python (139 new, incl. the loader-parity gate), 101 Rust (64 new). License gate passes on all
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
