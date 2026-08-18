//! Material types and property structs.
//!
//! # What is typed here, and what is not
//!
//! This crate types the **physics** domains in full fidelity — optical,
//! nuclear, mechanical, thermal — including structured spectra, temperature
//! curves, uncertainty and provenance. It deliberately does **not** mirror
//! `manufacturing`, `compliance`, `sourcing` or `vis`: machinability and RoHS
//! status are real facts, but they are not transport-kernel inputs, and every
//! mirrored field is a permanent maintenance and semver obligation.
//!
//! Nothing is unreachable as a result. [`Material::raw`] hands back the merged
//! TOML table for any material, so a consumer that needs an untyped field can
//! always get it. That is a guarantee; a promise to maintain full parity would
//! decay the first time the two sides were edited a week apart. See ADR-0004 §7.

use std::collections::HashMap;

use crate::curves::Curve;
use crate::provenance::{Absent, Source};

/// Path-length multiplier `1/cos(theta)` for a slab at incidence `theta`.
///
/// Capped at 40 (~88.6 degrees): beyond that a plane-parallel slab model has
/// stopped describing anything real, and a finite large number is less
/// misleading than an infinity.
pub fn obliquity_factor(incidence_deg: f64) -> f64 {
    let theta = incidence_deg.abs().to_radians();
    if theta >= std::f64::consts::FRAC_PI_2 {
        return 40.0;
    }
    (1.0 / theta.cos()).min(40.0)
}

/// One exponential component of a multi-exponential scintillation decay.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct DecayComponent {
    /// Time constant, ns.
    pub tau_ns: f64,
    /// Fractional amplitude. Fractions across all components sum to ~1.
    pub fraction: f64,
}

/// Optical / scintillator properties relevant for photon transport.
///
/// Scalars are the nominal value; per-field standard deviations live in
/// [`OpticalProperties::stddev`] rather than wrapping every field in a
/// `Value` struct, which would make the common path (`opt.light_yield`) worse
/// for the sake of the rare one.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct OpticalProperties {
    /// Index of refraction (scalar; see `refractive_index_dispersion` for n(lambda)).
    pub refractive_index: Option<f64>,
    /// Scintillation light yield (photons/MeV).
    pub light_yield: Option<f64>,
    /// Primary decay time (ns).
    pub decay_time: Option<f64>,
    /// Rise time (ns).
    pub rise_time: Option<f64>,
    /// Peak emission wavelength (nm).
    pub emission_peak: Option<f64>,
    /// `(min, max)` emission wavelengths (nm).
    pub emission_range: Option<(f64, f64)>,
    /// Transmission, % (0-100).
    pub transparency: Option<f64>,
    /// Bulk reflectivity, % (0-100).
    pub reflectivity: Option<f64>,
    /// Reflectivity vs lambda, % — diffuse reflectors are strongly
    /// wavelength-dependent at the blue end, where scintillators emit.
    pub reflectivity_spectrum: Option<Curve>,
    /// Transmission vs lambda, % at the path length named in `_sources`.
    pub transparency_spectrum: Option<Curve>,
    /// Lumped bulk attenuation length (mm).
    pub absorption_length: Option<f64>,
    /// Absorption coefficient (1/cm).
    pub absorption_coefficient: Option<f64>,
    /// Scattering length (cm).
    pub scattering_length: Option<f64>,
    /// Rayleigh scattering length (cm).
    pub rayleigh_length: Option<f64>,

    // --- the self-absorption split (ADR-0004 §5) -------------------------
    /// Host-matrix attenuation length (mm) — true loss. Photon is gone.
    pub absorption_length_matrix: Option<f64>,
    /// Activator self-absorption length (mm). The photon may be re-emitted
    /// after a fresh decay draw, with probability `reemit_qe`.
    pub absorption_length_reabs: Option<f64>,
    /// Probability in `[0, 1]` that a reabsorbed photon is re-emitted.
    pub reemit_qe: Option<f64>,

    // --- activator ---------------------------------------------------------
    /// Activator element, e.g. `"Ce"`, `"Tl"`.
    pub dopant: Option<String>,
    /// Activator concentration, mol %.
    pub dopant_pct: Option<f64>,

    // --- detector-physics scalars -----------------------------------------
    pub non_proportionality: Option<f64>,
    pub intrinsic_resolution_pct_at_662kev: Option<f64>,
    pub temperature_coefficient_light_yield: Option<f64>,
    pub hygroscopic: Option<bool>,

    // --- wavelength-resolved (nm abscissa) --------------------------------
    /// n(lambda).
    pub refractive_index_dispersion: Option<Curve>,
    /// k(lambda) — the extinction column of the same dispersion table.
    pub extinction: Option<Curve>,
    /// Kubelka-Munk absorption coefficient k(lambda), 1/cm.
    pub km_k: Option<Curve>,
    /// Kubelka-Munk scattering coefficient s(lambda), 1/cm.
    pub km_s: Option<Curve>,
    /// Relative emission intensity vs lambda.
    pub emission_spectrum: Option<Curve>,
    /// Lumped attenuation length vs lambda (mm).
    pub absorption_length_spectrum: Option<Curve>,
    /// Matrix-loss length vs lambda (mm).
    pub absorption_length_matrix_spectrum: Option<Curve>,
    /// Self-absorption length vs lambda (mm).
    pub absorption_length_reabs_spectrum: Option<Curve>,

    // --- temperature-resolved (K abscissa) --------------------------------
    pub refractive_index_curve: Option<Curve>,
    pub light_yield_curve: Option<Curve>,
    pub decay_time_curve: Option<Curve>,

    /// Multi-exponential decay, when published.
    pub decay_components: Vec<DecayComponent>,

    /// Per-field standard deviations, keyed by field name.
    pub stddev: HashMap<String, f64>,
}

impl OpticalProperties {
    /// Standard deviation for a field name, if the data carries one.
    pub fn stddev_of(&self, field: &str) -> Option<f64> {
        self.stddev.get(field).copied()
    }

    /// Refractive index at a wavelength (nm). Dispersion beats the scalar;
    /// outside the measured range the dispersion curve clamps.
    pub fn n_at(&self, wavelength_nm: f64) -> Option<f64> {
        match &self.refractive_index_dispersion {
            Some(c) => Some(c.interpolate(wavelength_nm)),
            None => self.refractive_index,
        }
    }

    /// Lumped attenuation length (mm) at a wavelength (nm).
    pub fn absorption_length_at(&self, wavelength_nm: f64) -> Option<f64> {
        match &self.absorption_length_spectrum {
            Some(c) => Some(c.interpolate(wavelength_nm)),
            None => self.absorption_length,
        }
    }

    /// Matrix-loss length (mm) at a wavelength (nm).
    pub fn absorption_length_matrix_at(&self, wavelength_nm: f64) -> Option<f64> {
        match &self.absorption_length_matrix_spectrum {
            Some(c) => Some(c.interpolate(wavelength_nm)),
            None => self.absorption_length_matrix,
        }
    }

    /// Self-absorption length (mm) at a wavelength (nm).
    pub fn absorption_length_reabs_at(&self, wavelength_nm: f64) -> Option<f64> {
        match &self.absorption_length_reabs_spectrum {
            Some(c) => Some(c.interpolate(wavelength_nm)),
            None => self.absorption_length_reabs,
        }
    }

    /// Reflectivity (%) at a wavelength (nm). Spectrum beats the scalar.
    pub fn reflectivity_at(&self, wavelength_nm: f64) -> Option<f64> {
        match &self.reflectivity_spectrum {
            Some(c) => Some(c.interpolate(wavelength_nm)),
            None => self.reflectivity,
        }
    }

    /// Transmission (%) at a wavelength (nm). Spectrum beats the scalar.
    pub fn transparency_at(&self, wavelength_nm: f64) -> Option<f64> {
        match &self.transparency_spectrum {
            Some(c) => Some(c.interpolate(wavelength_nm)),
            None => self.transparency,
        }
    }

    /// Extinction coefficient at a wavelength (nm), or None if transparent.
    pub fn k_at(&self, wavelength_nm: f64) -> Option<f64> {
        Some(self.extinction.as_ref()?.interpolate(wavelength_nm))
    }

    /// Normal-incidence reflectance from vacuum, PERCENT.
    ///
    /// `R = ((n-1)^2 + k^2) / ((n+1)^2 + k^2)`. Derived rather than stored, so
    /// it cannot drift from the n,k it comes from. This is the smooth,
    /// optically-thick, normal-incidence ceiling — a real wrap measures lower.
    pub fn normal_reflectance_at(&self, wavelength_nm: f64) -> Option<f64> {
        let n = self.n_at(wavelength_nm)?;
        let k = self.k_at(wavelength_nm).unwrap_or(0.0);
        Some(100.0 * ((n - 1.0).powi(2) + k * k) / ((n + 1.0).powi(2) + k * k))
    }

    /// Kubelka-Munk thick-layer reflectance, PERCENT.
    ///
    /// `R_inf = 1 + k/s - sqrt((k/s)^2 + 2k/s)`.
    pub fn km_reflectance_infinite_at(&self, wavelength_nm: f64) -> Option<f64> {
        let k = self.km_k.as_ref()?.interpolate(wavelength_nm);
        let s = self.km_s.as_ref()?.interpolate(wavelength_nm);
        if s <= 0.0 {
            return None;
        }
        let x = k / s;
        Some(100.0 * (1.0 + x - (x * x + 2.0 * x).sqrt()))
    }

    /// `(R, T, A)` in PERCENT for a finite layer — every photon's fate.
    ///
    /// Sums to 100 by construction. `T` is the inter-crystal crosstalk channel
    /// in a segmented detector, `A` is the only true loss, and `R` is the
    /// reflectance the layer actually delivers — which is NOT
    /// [`km_reflectance_infinite_at`] unless the layer is optically thick.
    ///
    /// **The layer is against a non-reflecting (black) backing** — a
    /// transmitted photon is gone from this interface's point of view, which
    /// is the correct model for an inter-crystal septum.
    ///
    /// There is deliberately no `backing` parameter. With a reflective
    /// backing, K-M's `R` is the reflectance of the COMPOSITE (layer plus
    /// backing), while `T` is the layer's own transmittance; they are not two
    /// parts of one photon budget, so `A := 100 - R - T` stops meaning
    /// "absorbed" and can go negative. An earlier revision exposed such a
    /// parameter and documented a conservation property it did not have.
    ///
    /// **`incidence_deg` is for COLLIMATED light at a known angle.** For
    /// diffuse illumination pass 0.
    ///
    /// Two traps, both of which have caught real consumers:
    ///
    /// 1. A diffuse reflector ERASES the incident angular distribution. After
    ///    one contact with a Lambertian surface, direction is cosine-distributed
    ///    about that normal with mean `|cos theta| = 2/3` (48.2 degrees),
    ///    regardless of how the light arrived. "High-aspect crystal, therefore
    ///    grazing incidence" is wrong as soon as the wall is diffuse.
    /// 2. Kubelka-Munk `k` and `s` are already defined for DIFFUSE flux — the
    ///    obliquity is baked in (hence the factor 2 in the usual `K = 2k`).
    ///    Multiplying by `1/cos` on top of that double-counts.
    ///
    /// Note the limit: with `k = 0` the thick-layer reflectance is exactly 1,
    /// not 0.999. Absorption is the only thing that puts R_inf below unity.
    pub fn km_split_at(
        &self,
        wavelength_nm: f64,
        thickness_cm: f64,
        incidence_deg: f64,
    ) -> Option<(f64, f64, f64)> {
        let k = self.km_k.as_ref()?.interpolate(wavelength_nm);
        let s = self.km_s.as_ref()?.interpolate(wavelength_nm);
        if s <= 0.0 || thickness_cm <= 0.0 {
            return None;
        }
        let thickness_cm = thickness_cm * obliquity_factor(incidence_deg);
        if k == 0.0 {
            let sd = s * thickness_cm;
            return Some((100.0 * sd / (1.0 + sd), 100.0 / (1.0 + sd), 0.0));
        }
        let a = 1.0 + k / s;
        let b = (a * a - 1.0).sqrt();
        let bsd = b * s * thickness_cm;
        // Optically thick limit. `cosh` overflows an f64 above ~710 and `coth`
        // is 1.0 to machine precision by ~20, so branch before the arithmetic
        // can blow up. EXACT, not an approximation: coth -> 1 gives
        // R = 1/(a+b), which is identically R_inf.
        if bsd > 20.0 {
            let r = 1.0 / (a + b);
            return Some((100.0 * r, 0.0, 100.0 * (1.0 - r)));
        }
        let coth = bsd.cosh() / bsd.sinh();
        let r = 1.0 / (a + b * coth);
        let t = b / (a * bsd.sinh() + b * bsd.cosh());
        Some((100.0 * r, 100.0 * t, 100.0 * (1.0 - r - t)))
    }

    /// Reflectance (%) of a FINITE layer — the number a real reflector gives.
    ///
    /// Prefer this over [`km_reflectance_infinite_at`] for any physical layer.
    pub fn km_reflectance_at(
        &self,
        wavelength_nm: f64,
        thickness_cm: f64,
        incidence_deg: f64,
    ) -> Option<f64> {
        Some(
            self.km_split_at(wavelength_nm, thickness_cm, incidence_deg)?
                .0,
        )
    }

    /// Kubelka-Munk diffuse transmittance through a FINITE layer, PERCENT.
    ///
    /// Answers a different question from [`km_reflectance_infinite_at`]:
    /// reflectance converges to its thick-layer limit quickly, transmittance
    /// does not. A layer can be "optically thick" for reflectance and still
    /// transmit several percent — in a segmented detector that is the
    /// inter-crystal crosstalk channel.
    pub fn km_transmittance_at(
        &self,
        wavelength_nm: f64,
        thickness_cm: f64,
        incidence_deg: f64,
    ) -> Option<f64> {
        Some(
            self.km_split_at(wavelength_nm, thickness_cm, incidence_deg)?
                .1,
        )
    }

    /// Relative emission intensity at a wavelength (nm).
    ///
    /// There is deliberately no scalar fallback: `emission_peak` is one point
    /// on a band, not a stand-in for its shape. A caller with only a peak
    /// should sample monochromatically and know that it is doing so.
    pub fn emission_at(&self, wavelength_nm: f64) -> Option<f64> {
        Some(self.emission_spectrum.as_ref()?.interpolate(wavelength_nm))
    }

    /// Refractive index at a temperature (K). Curve beats the scalar.
    pub fn refractive_index_at_temp(&self, temp_k: f64) -> Option<f64> {
        match &self.refractive_index_curve {
            Some(c) => Some(c.interpolate(temp_k)),
            None => self.refractive_index,
        }
    }

    /// Light yield at a temperature (K). Curve beats the scalar.
    pub fn light_yield_at_temp(&self, temp_k: f64) -> Option<f64> {
        match &self.light_yield_curve {
            Some(c) => Some(c.interpolate(temp_k)),
            None => self.light_yield,
        }
    }

    /// Decay time at a temperature (K). Curve beats the scalar.
    pub fn decay_time_at_temp(&self, temp_k: f64) -> Option<f64> {
        match &self.decay_time_curve {
            Some(c) => Some(c.interpolate(temp_k)),
            None => self.decay_time,
        }
    }
}

/// Nuclear / radiation-physics scalars (#157).
///
/// Moved here from `OpticalProperties` to mirror the Python schema —
/// `radiation_length` and friends are nuclear physics, not optics.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct NuclearProperties {
    /// Radiation length X0 (cm).
    pub radiation_length: Option<f64>,
    /// Nuclear interaction length lambda (cm).
    pub interaction_length: Option<f64>,
    /// Moliere radius (cm).
    pub moliere_radius: Option<f64>,
    /// Effective atomic number.
    pub z_eff: Option<f64>,
    /// Geant4 mean excitation energy (eV).
    pub mean_excitation_energy_ev: Option<f64>,
    /// Intrinsic activity (Bq/g) — LYSO's 176-Lu content, for instance.
    pub intrinsic_activity_bq_per_g: Option<f64>,
    /// Per-field standard deviations.
    pub stddev: HashMap<String, f64>,
}

impl NuclearProperties {
    pub fn stddev_of(&self, field: &str) -> Option<f64> {
        self.stddev.get(field).copied()
    }
}

/// Mechanical properties a transport or geometry stage may need.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct MechanicalProperties {
    /// Density (g/cm^3).
    pub density: Option<f64>,
    /// Young's modulus (GPa).
    pub youngs_modulus: Option<f64>,
    /// Poisson's ratio.
    pub poissons_ratio: Option<f64>,
    /// Per-field standard deviations.
    pub stddev: HashMap<String, f64>,
}

impl MechanicalProperties {
    pub fn stddev_of(&self, field: &str) -> Option<f64> {
        self.stddev.get(field).copied()
    }
}

/// Thermal properties, including temperature-dependent curves.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct ThermalProperties {
    /// Thermal conductivity (W/(m*K)).
    pub thermal_conductivity: Option<f64>,
    /// Specific heat (J/(kg*K)).
    pub specific_heat: Option<f64>,
    /// Linear thermal expansion (1/K).
    pub thermal_expansion: Option<f64>,
    /// Melting point (degC).
    pub melting_point: Option<f64>,
    pub thermal_conductivity_curve: Option<Curve>,
    pub specific_heat_curve: Option<Curve>,
    pub thermal_expansion_curve: Option<Curve>,
    /// Per-field standard deviations.
    pub stddev: HashMap<String, f64>,
}

impl ThermalProperties {
    pub fn stddev_of(&self, field: &str) -> Option<f64> {
        self.stddev.get(field).copied()
    }

    /// Thermal conductivity at a temperature (K). Curve beats the scalar.
    pub fn thermal_conductivity_at(&self, temp_k: f64) -> Option<f64> {
        match &self.thermal_conductivity_curve {
            Some(c) => Some(c.interpolate(temp_k)),
            None => self.thermal_conductivity,
        }
    }
}

/// A material with its physical properties.
///
/// `Send + Sync` — load once, share via `Arc`.
#[derive(Debug, Clone)]
pub struct Material {
    /// Lookup key (e.g. `"lyso"`, `"stainless.s316L"`).
    pub key: String,
    /// Human-readable name.
    pub name: String,
    /// Chemical formula, if known.
    pub formula: Option<String>,
    /// Elemental composition as `{symbol: fraction}`.
    /// Interpretation (mass vs atom) depends on the source data.
    pub composition: Option<HashMap<String, f64>>,
    /// Density in g/cm^3. Kept at the top level for backward compatibility;
    /// also present on `mechanical`.
    pub density: Option<f64>,
    /// Surface treatment, e.g. `"polished"`, `"electropolished"`.
    pub treatment: Option<String>,
    /// Grade designation.
    pub grade: Option<String>,
    /// Temper designation (e.g. `"T6"`).
    pub temper: Option<String>,
    /// Vendor key.
    pub vendor: Option<String>,
    /// Multi-axial filterable labels (#132), orthogonal to the TOML hierarchy.
    /// Children inherit their ancestors' tags and extend — parent context
    /// first, then the child's own, duplicates dropped.
    pub tags: Vec<String>,
    /// Optical / scintillator properties.
    pub optical: Option<OpticalProperties>,
    /// Nuclear / radiation-physics scalars.
    pub nuclear: Option<NuclearProperties>,
    /// Mechanical properties.
    pub mechanical: Option<MechanicalProperties>,
    /// Thermal properties.
    pub thermal: Option<ThermalProperties>,
    /// Provenance, keyed by dotted property path (`"optical.light_yield"`).
    pub sources: HashMap<String, Source>,
    /// Declared absences, keyed by dotted property path.
    pub absent: HashMap<String, Absent>,
    /// The merged TOML table this material was built from, parent fields
    /// included. The escape hatch for anything this crate does not type.
    pub(crate) raw: toml::Table,
}

impl Material {
    /// Density in g/cm^3 (convenience accessor).
    pub fn density(&self) -> Option<f64> {
        self.density
    }

    /// Chemical formula string.
    pub fn formula(&self) -> Option<&str> {
        self.formula.as_deref()
    }

    /// Compute mass fractions from the formula (if present).
    ///
    /// Returns `None` if no formula is set or parsing fails.
    pub fn mass_fractions(&self) -> Option<Vec<(String, f64)>> {
        let f = self.formula.as_ref()?;
        crate::formula::formula_to_mass_fractions(f).ok()
    }

    /// Return the optical properties, if any.
    pub fn optical(&self) -> Option<&OpticalProperties> {
        self.optical.as_ref()
    }

    /// Return the nuclear / radiation-physics scalars, if any.
    pub fn nuclear(&self) -> Option<&NuclearProperties> {
        self.nuclear.as_ref()
    }

    /// Return the mechanical properties, if any.
    pub fn mechanical(&self) -> Option<&MechanicalProperties> {
        self.mechanical.as_ref()
    }

    /// Return the thermal properties, if any.
    pub fn thermal(&self) -> Option<&ThermalProperties> {
        self.thermal.as_ref()
    }

    /// Provenance for a dotted property path, falling back to `_default`.
    pub fn source_of(&self, path: &str) -> Option<&Source> {
        self.sources
            .get(path)
            .or_else(|| self.sources.get("_default"))
    }

    /// Declared absence for a dotted property path.
    ///
    /// Unlike [`Material::source_of`] there is no `_default` fallback — an
    /// absence is always specific to one property.
    pub fn absent_reason(&self, path: &str) -> Option<&Absent> {
        self.absent.get(path)
    }

    /// True when `path` carries an explicit absence declaration.
    ///
    /// Distinguishes "nobody looked" (`false`, value is simply `None`) from
    /// "we looked and the number does not exist" (`true`).
    pub fn is_absent(&self, path: &str) -> bool {
        self.absent.contains_key(path)
    }

    /// The merged TOML table backing this material, with parent fields applied.
    ///
    /// The escape hatch of ADR-0004 §7: every field in the database is
    /// reachable from Rust even when this crate does not type it.
    ///
    /// ```
    /// # use rs_materials::MaterialDb;
    /// let db = MaterialDb::builtin();
    /// let peek = db.get("peek").unwrap();
    /// // `manufacturing` is not typed by this crate — but it is not lost.
    /// let printable = peek
    ///     .raw()
    ///     .get("manufacturing")
    ///     .and_then(|m| m.as_table())
    ///     .and_then(|m| m.get("printable_fdm"))
    ///     .and_then(|v| v.as_bool());
    /// assert_eq!(printable, Some(true));
    /// ```
    pub fn raw(&self) -> &toml::Table {
        &self.raw
    }
}
