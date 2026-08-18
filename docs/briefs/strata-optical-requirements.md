# Brief: optical properties for downstream MC transport (strata)

**Author:** strata light-module work, 2026-08-14
**Consumer:** [strata](https://github.com/gerchowl/strata) — Rust Monte Carlo PET engine
**Strata-side ADR:** ADR-089 (optical/light-tracking module)
**Strata-side issue:** gerchowl/strata#1050

This brief states what strata needs from py-mat, and — equally important — what
strata must NOT ask py-mat to hold. Treat the separation of concerns section as
the contract; the work-list is the consequence.

---

## 1. Separation of concerns (the contract)

The question this brief answers: *when a PET crystal is wrapped in ESR film and
read out by a SiPM, which of those facts is a **material** fact and which is an
**assembly** fact?*

| Layer | Owns | Rationale |
|---|---|---|
| **py-mat** | *Substance* physics: what LYSO **is**. n(λ), bulk attenuation, self-absorption, emission spectrum, decay components, light yield, re-emission QE — with provenance and uncertainty. Plus the **named surface-finish catalogue** (what "PolishedESRGrease" *is* as a measured interface). | These are citable, measured, reusable properties of a substance or a substance pair. They do not change when you move a crystal. |
| **strata-data/optical/\*.parquet** | Flat, resampled, sha-pinned tables derived from py-mat + G4 RealSurface. | Build artifact, regenerable. Strata's established "physics-as-data" chain. Not authored by hand. |
| **`.strata` geometry (from build123d)** | *Assembly* facts: this volume is LYSO; **this face** carries `sipm_grease`; the other five carry `esr_wrap`. | Which face is the readout is a property of the built detector, not of LYSO. Two scanners using identical LYSO differ here. |
| **strata config TOML** | Policy: which model, which toggles, SiPM PDE/SPTR, max bounces. | Run-time choices, not facts about matter. |
| **strata kernel crates** | Algorithms. Own no data. | |

**The load-bearing line:** py-mat owns *what a material and an interface are*;
strata owns *what was built and how it is simulated*. A surface finish is a
material-pair fact (LYSO↔ESR↔air) and belongs here. The *assignment* of that
finish to a particular face of a particular crystal belongs in strata.

**Non-goals for py-mat** — do not add any of these, strata will reject them:
per-volume or per-face assignments; geometry; SiPM electronics config; sampling
tables (ICDFs); anything keyed by a strata volume id.

---

## 2. Current state (verified 2026-08-14)

Good news first — more of this exists than strata was using:

- `OpticalProperties` (`src/pymat/properties.py`) already defines
  `refractive_index`, `light_yield`, `decay_time`, `rise_time`, `emission_peak`,
  `emission_range`, `absorption_length`, `absorption_coefficient`,
  `scattering_length`, `rayleigh_length`, `non_proportionality`,
  `intrinsic_resolution_pct_at_662keV`, and more.
- Structured slots already exist and round-trip through the loader:
  `emission_spectrum {wavelengths_nm, intensities}`,
  `refractive_index_dispersion {wavelengths_nm, n}`,
  `decay_components [{tau_ns, fraction}]`.
- T-dependence is a solved problem: `<prop>_curve = {temps_K, values}` with
  `_at(T)` accessors, clamping (never extrapolating). Registered for
  `refractive_index`, `light_yield`, `decay_time`.
- Inheritance works and is the right answer for finishes-as-variants:
  `[stainless.s316L.electropolished]` is the working template.
- Provenance (`_sources` per property path) and uncertainty (`_stddev`,
  `{nominal, stddev}`, `{min, max}`) are wired.

The gaps:

1. **Data is sparse.** `[lyso.optical]` carries four numbers
   (`refractive_index=1.82`, `light_yield=32000`, `decay_time=41`,
   `emission_peak=420`). No absorption length, no spectrum, no dispersion, no
   decay components — despite the slots existing.
2. **No wavelength accessor.** `_at(T)` exists for temperature; there is no
   `n_at(λ)` / `absorption_length_at(λ)`. The structured λ slots are inert data.
3. **`rs-materials 0.1.0` is far behind the Python side.** It exposes exactly six
   `Option<f64>` optical scalars and silently drops every structured field, every
   `_curve`, all uncertainty and all provenance. It also still carries
   `radiation_length`/`interaction_length` under `OpticalProperties`, which the
   Python side moved to `nuclear` in #157 — a live schema drift.
4. **No surface-finish concept at all.** Nowhere to say what `PolishedESR` is.

---

## 3. What strata needs (in priority order)

### P0 — the wavelength accessor + the Rust surface

Without these, everything else is unreachable from strata.

- **`WavelengthCurve`**, mirroring `TempCurve` in `curves.py` — piecewise-linear,
  clamp-outside-range, validated at load. Accessors `refractive_index_at(λ)`,
  `absorption_length_at(λ)`, and spectrum sampling support.
- **Grow `rs-materials`** to expose the structured fields, curves, uncertainty and
  `_sources`. Cut a new version. Strata pins it.
  - Fix the `radiation_length`/`interaction_length` drift while you are there.

### P0 — the surface-finish catalogue

A new top-level category (proposal: `surfaces.toml`, group `[surface.*]`). Each
entry describes an **interface**, not a bulk:

```toml
[surface.esr]
name = "3M ESR / Vikuiti specular reflector"
kind = "specular"                  # specular | diffuse | lut
thickness_um = 65
[surface.esr.optical]
reflectivity = 0.985               # scalar fallback
reflectivity_spectrum = { wavelengths_nm = [...], values = [...] }

[surface.esr.grease]               # inherits: ESR, index-matched
name = "ESR with silicone-grease coupling"
coupling = "optical_contact"
[surface.esr.grease.optical]
coupling_index = 1.465

[surface.lyso_polished_esr_grease]
name = "Polished LYSO / ESR / grease"
kind = "lut"
lut_family = "davis"               # G4 RealSurface 2.2
lut_surface = "PolishedESRGrease"
pair = ["lyso", "surface.esr.grease"]
```

Two things must be expressible, because they are physically different and strata
currently cannot tell them apart:

- **air gap** (dry-pressed wrap): photon sees crystal→air Fresnel first, then the
  reflector. Produces TIR light-piping — the mechanism DOI designs exploit.
- **optical contact** (grease/glue): photon sees crystal→polymer directly.

Also: G4 RealSurface 2.2 ships 21 LBNL and 9 DAVIS measured surfaces. Strata has
those parquets already but no vocabulary to name them. The catalogue is that
vocabulary, and it should carry the citations.

### P1 — populate the scintillators

For `lyso` first, then `bgo`, `gagg`, `gso`, `nai_tl`, `csi_tl`, plastics:

| Field | Why strata needs it |
|---|---|
| `emission_spectrum` | Strata samples emission **monochromatically at the peak** today, which makes every λ-dependent term silently constant. This is the single highest-value field in this brief. |
| `refractive_index_dispersion` | Fresnel and TIR angles are n(λ); with one scalar the critical angle is wrong off-peak. |
| `absorption_length` + spectrum | Currently a hardcoded `200 mm` literal in strata's Rust. |
| `decay_components` | LYSO is not single-exponential; the slow component drives the CTR tail. |
| **self-absorption** — see below | Not currently expressible. |
| `reemit_qe` | Probability a reabsorbed photon is re-emitted. |

**New field needed: self-absorption.** LYSO:Ce has real overlap between the Ce
absorption tail and its own emission tail. On a 20 mm crystal over 5–20 bounces
this reabsorbs an estimated 10–30% of the light, and re-emission (delayed by a
fresh decay draw) puts a slow tail on the timing distribution. Strata must sample
"lost to matrix" and "reabsorbed, may re-emit" as **distinct fates**, so one
lumped `absorption_length` cannot express it. Proposal:

```toml
[lyso.Ce.optical]
absorption_length_matrix = { wavelengths_nm = [...], values = [...] }   # true loss
absorption_length_reabs  = { wavelengths_nm = [...], values = [...] }   # Ce self-abs
reemit_qe = 0.75
```

If the split is not measurable for a given material, say so with an explicit
absent-declaration rather than folding it into one number.

### P1 — `polished_lyso` as an inherited variant

The idiomatic form, needing no new machinery:

```toml
[lyso.Ce.polished]
name = "LYSO:Ce, polished"
treatment = "polished"
[lyso.Ce.polished.optical]
default_surface = "surface.lyso_polished_esr_grease"
```

Everything else inherits. Please confirm this shape works end-to-end and add a
test, since strata intends to rely on it.

### P2 — provenance is not optional

Every number strata consumes must carry `_sources`. Strata's own contract
(`docs/foundations.md`) is that a claim without a gate is a claim that will
silently stop being true; the same standard applies to values crossing the
repo boundary. A value with no citation is worse than an absent one, because
absence is visible.

---

## 4. What strata will do on its side (so you can ignore it)

- Resample py-mat's spectra onto a shared 128-node λ grid (300–800 nm) and emit
  flat `#[repr(C)]` `f32` rows into `strata-data/optical/*.parquet`, sha-pinned in
  `strata-tables.manifest.toml`, generated by a deterministic script. That layout
  is chosen to be device-representable for the GPU kernel; it is strata's problem,
  not py-mat's.
- Precompute an emission inverse-CDF for sampling. Also strata's problem.
- Carry per-face finish **assignments** in `.strata`, referencing catalogue names
  from here by string key.

py-mat should stay human-authored, cited, unit-carrying and uncertainty-aware.
Do not optimise it for the GPU; strata will do the flattening.

---

## 5. Open questions for the py-mat maintainer

1. Does the surface-finish catalogue belong in py-mat at all, or is an interface a
   fundamentally different kind of object deserving its own repo? Strata's view:
   it belongs here — it is measured, citable, reusable, and meaningless without
   the two materials it joins. But this is your call and it should be an ADR.
2. Is `surfaces.toml` the right home, or should finishes nest under the material
   they are measured against?
3. `ceramics.toml:480` gates dispersion data on issue #201 — what is the blocker,
   and does it apply to scintillators?
4. Should `rs-materials` grow to full parity with the Python schema, or expose a
   deliberately narrower "transport-relevant" subset? Strata prefers full parity
   with an explicit subset view on top, so the Rust side never becomes the reason
   a field is unusable.
