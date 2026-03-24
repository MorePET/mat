//! Material types and property structs.

use std::collections::HashMap;

/// Optical / scintillator properties relevant for radiation physics.
#[derive(Debug, Clone, Default)]
pub struct OpticalProperties {
    /// Index of refraction.
    pub refractive_index: Option<f64>,
    /// Scintillation light yield (photons/MeV).
    pub light_yield: Option<f64>,
    /// Primary decay time (ns).
    pub decay_time: Option<f64>,
    /// Peak emission wavelength (nm).
    pub emission_peak: Option<f64>,
    /// Radiation length X₀ (cm).
    pub radiation_length: Option<f64>,
    /// Nuclear interaction length λ (cm).
    pub interaction_length: Option<f64>,
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
    /// Density in g/cm³.
    pub density: Option<f64>,
    /// Optical / scintillator properties.
    pub optical: Option<OpticalProperties>,
}

impl Material {
    /// Density in g/cm³ (convenience accessor).
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
}
