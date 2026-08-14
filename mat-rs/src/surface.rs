//! Measured optical surface finishes — the Rust mirror of `pymat.surfaces`.
//!
//! A [`Surface`] is an *interface*, not a bulk: a crystal face with a given
//! treatment, a reflector, and whatever fills the gap between them. It has no
//! density and no formula, so it is a separate type with a separate database
//! rather than a [`crate::Material`] (ADR-0004 §2).
//!
//! The catalogue holds **measured** interfaces only — the 21 LBNL and 9 DAVIS
//! look-up tables shipped in the Geant4 `G4RealSurface` 2.2 data set. Geant4's
//! six analytic UNIFIED finishes (`polished`, `ground`, …) carry no measured
//! data and are model selections, so they belong to the consuming engine's
//! configuration, not here (ADR-0004 §3).
//!
//! Assignments — which face of which crystal carries which finish — are not
//! here either. That is a fact about a built detector.

use std::collections::HashMap;

use crate::curves::Curve;
use crate::error::MatError;
use crate::provenance::{Absent, Source, overlay, parse_absent, parse_sources};

/// What fills the gap between a crystal face and its reflector.
///
/// The distinction is physically load-bearing: an air gap means the photon
/// meets a crystal→air Fresnel step first (large index contrast, small
/// critical angle, strong total-internal-reflection light-piping — the
/// mechanism depth-of-interaction designs exploit), while optical contact
/// means it meets the coupling polymer directly.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Coupling {
    /// A reflector is present, with air between it and the face.
    AirGap,
    /// The gap is index-filled (grease, glue, meltmount).
    OpticalContact,
    /// No reflector at all — a bare face against the ambient.
    None,
}

impl Coupling {
    fn parse(s: &str) -> Option<Self> {
        match s {
            "air_gap" => Some(Self::AirGap),
            "optical_contact" => Some(Self::OpticalContact),
            "none" => Some(Self::None),
            _ => None,
        }
    }
}

/// Which measured look-up-table family an entry belongs to.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LutFamily {
    /// Janecek & Moses 2010, goniometer measurements. `dielectric_LUT`.
    Lbnl,
    /// Roncali & Cherry 2013, AFM topography. `dielectric_LUTDAVIS`.
    Davis,
}

impl LutFamily {
    fn parse(s: &str) -> Option<Self> {
        match s {
            "lbnl" => Some(Self::Lbnl),
            "davis" => Some(Self::Davis),
            _ => None,
        }
    }
}

/// One measured optical interface.
#[derive(Debug, Clone)]
pub struct Surface {
    /// Catalogue key, e.g. `"davis.polished_esr_grease"`.
    pub key: String,
    /// Human-readable name.
    pub name: String,
    /// Measured LUT family.
    pub lut_family: Option<LutFamily>,
    /// The exact `G4OpticalSurfaceFinish` enum spelling, verbatim.
    ///
    /// Casing is inconsistent across families (`polishedvm2000glue` for LBNL,
    /// `PolishedESRGrease_LUT` for DAVIS) because Geant4's is. Match on it
    /// as-is; do not normalise.
    pub lut_surface: Option<String>,
    /// The exact `G4SurfaceType` the finish is valid with.
    pub g4_surface_type: Option<String>,
    /// Data-set release, e.g. `"G4RealSurface-2.2"`.
    pub lut_dataset: Option<String>,
    /// Crystal-face preparation: `polished`, `etched`, `ground`, `rough`.
    pub treatment: Option<String>,
    /// Human label for the reflector.
    pub reflector: Option<String>,
    /// Material key for the reflector, when this database has one.
    pub reflector_material: Option<String>,
    /// What fills the gap.
    pub coupling: Option<Coupling>,
    /// Material key for the coupling medium, when this database has one.
    pub coupling_material: Option<String>,
    /// Refractive index of the coupling medium.
    pub coupling_index: Option<f64>,
    /// Reflectivity, % (0-100).
    pub reflectivity: Option<f64>,
    /// Reflectivity vs wavelength (nm abscissa, % ordinate).
    pub reflectivity_spectrum: Option<Curve>,
    /// Reflector film thickness (um).
    pub thickness_um: Option<f64>,
    /// Free-text note.
    pub note: Option<String>,
    /// Provenance keyed by field name.
    pub sources: HashMap<String, Source>,
    /// Declared absences keyed by field name.
    pub absent: HashMap<String, Absent>,
}

impl Surface {
    /// True when the gap is index-filled rather than air.
    pub fn is_optical_contact(&self) -> bool {
        self.coupling == Some(Coupling::OpticalContact)
    }

    /// True when a reflector sits behind an air gap — the configuration that
    /// produces total-internal-reflection light-piping.
    pub fn is_air_gap(&self) -> bool {
        self.coupling == Some(Coupling::AirGap)
    }

    /// Reflectivity (%) at a wavelength (nm). Spectrum beats scalar, clamped.
    pub fn reflectivity_at(&self, wavelength_nm: f64) -> Option<f64> {
        match &self.reflectivity_spectrum {
            Some(c) => Some(c.interpolate(wavelength_nm)),
            None => self.reflectivity,
        }
    }

    /// Provenance for a field name, falling back to `_default`.
    pub fn source_of(&self, field: &str) -> Option<&Source> {
        self.sources
            .get(field)
            .or_else(|| self.sources.get("_default"))
    }

    /// Declared absence for a field name.
    pub fn absent_reason(&self, field: &str) -> Option<&Absent> {
        self.absent.get(field)
    }
}

/// The surface-finish catalogue. `Send + Sync` for `Arc` sharing.
#[derive(Debug, Clone)]
pub struct SurfaceDb {
    surfaces: HashMap<String, Surface>,
}

const BUILTIN_SURFACES: &str = include_str!("../data/surfaces.toml");

impl SurfaceDb {
    /// Load the built-in catalogue (embedded at compile time).
    pub fn builtin() -> Self {
        let table: toml::Table =
            toml::from_str(BUILTIN_SURFACES).expect("embedded surfaces.toml should always parse");
        Self {
            surfaces: parse_catalogue(&table),
        }
    }

    /// Load a catalogue from a `surfaces.toml` on disk.
    pub fn open(path: impl AsRef<std::path::Path>) -> Result<Self, MatError> {
        let path = path.as_ref();
        let raw = std::fs::read_to_string(path).map_err(|e| MatError::TomlRead {
            path: path.to_path_buf(),
            source: e,
        })?;
        let table: toml::Table = toml::from_str(&raw).map_err(|e| MatError::TomlParse {
            path: path.to_path_buf(),
            source: e,
        })?;
        Ok(Self {
            surfaces: parse_catalogue(&table),
        })
    }

    /// Get a surface by key. Accepts `davis.rough` or `surface.davis.rough`.
    pub fn get(&self, key: &str) -> Result<&Surface, MatError> {
        let norm = key.strip_prefix("surface.").unwrap_or(key);
        self.surfaces
            .get(norm)
            .ok_or_else(|| MatError::NotFound(key.to_string()))
    }

    /// Look up by the exact `G4OpticalSurfaceFinish` enum spelling.
    ///
    /// This is the reverse index a consumer holding a Geant4 finish name needs.
    pub fn by_lut_surface(&self, lut_surface: &str) -> Option<&Surface> {
        self.surfaces
            .values()
            .find(|s| s.lut_surface.as_deref() == Some(lut_surface))
    }

    /// All entries in a family.
    pub fn family(&self, family: LutFamily) -> Vec<&Surface> {
        self.surfaces
            .values()
            .filter(|s| s.lut_family == Some(family))
            .collect()
    }

    /// All entries with a given coupling.
    pub fn with_coupling(&self, coupling: Coupling) -> Vec<&Surface> {
        self.surfaces
            .values()
            .filter(|s| s.coupling == Some(coupling))
            .collect()
    }

    /// All catalogue keys.
    pub fn keys(&self) -> impl Iterator<Item = &str> {
        self.surfaces.keys().map(|s| s.as_str())
    }

    /// All entries.
    pub fn values(&self) -> impl Iterator<Item = &Surface> {
        self.surfaces.values()
    }

    /// Number of entries.
    pub fn len(&self) -> usize {
        self.surfaces.len()
    }

    /// Whether the catalogue is empty.
    pub fn is_empty(&self) -> bool {
        self.surfaces.is_empty()
    }
}

impl Default for SurfaceDb {
    fn default() -> Self {
        Self::builtin()
    }
}

/// Fields that configure a node rather than naming a child surface.
const SURFACE_FIELDS: &[&str] = &[
    "name",
    "model",
    "treatment",
    "lut_family",
    "lut_surface",
    "g4_surface_type",
    "lut_dataset",
    "reflector",
    "reflector_material",
    "coupling",
    "coupling_material",
    "coupling_index",
    "reflectivity",
    "reflectivity_spectrum",
    "thickness_um",
    "note",
    "abstract",
];

fn parse_catalogue(root: &toml::Table) -> HashMap<String, Surface> {
    let mut out = HashMap::new();
    if let Some(surface_root) = root.get("surface").and_then(|v| v.as_table()) {
        for (key, node) in surface_root {
            if let Some(table) = node.as_table() {
                resolve(
                    key,
                    table,
                    &toml::Table::new(),
                    &HashMap::new(),
                    &HashMap::new(),
                    &mut out,
                );
            }
        }
    }
    out
}

fn resolve(
    key: &str,
    node: &toml::Table,
    inherited: &toml::Table,
    parent_sources: &HashMap<String, Source>,
    parent_absent: &HashMap<String, Absent>,
    out: &mut HashMap<String, Surface>,
) {
    // Overlay this node's own fields onto whatever flowed down from the family.
    let mut merged = inherited.clone();
    for field in SURFACE_FIELDS {
        if let Some(v) = node.get(*field) {
            merged.insert((*field).to_string(), v.clone());
        }
    }

    let sources = match node.get("_sources").and_then(|v| v.as_table()) {
        Some(t) => overlay(parent_sources, parse_sources(t)),
        None => parent_sources.clone(),
    };
    let absent = match node.get("_absent").and_then(|v| v.as_table()) {
        Some(t) => overlay(parent_absent, parse_absent(t)),
        None => parent_absent.clone(),
    };

    let is_abstract = merged
        .get("abstract")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);
    if !is_abstract {
        out.insert(
            key.to_string(),
            build_surface(key, &merged, &sources, &absent),
        );
    }

    // Identity fields must not flow to children — they are what makes each
    // entry a distinct measurement.
    let mut child_inherited = merged;
    for identity in ["name", "lut_surface", "note", "abstract"] {
        child_inherited.remove(identity);
    }

    for (child_key, child_value) in node {
        if SURFACE_FIELDS.contains(&child_key.as_str()) || child_key.starts_with('_') {
            continue;
        }
        if let Some(child_table) = child_value.as_table() {
            resolve(
                &format!("{key}.{child_key}"),
                child_table,
                &child_inherited,
                &sources,
                &absent,
                out,
            );
        }
    }
}

fn build_surface(
    key: &str,
    t: &toml::Table,
    sources: &HashMap<String, Source>,
    absent: &HashMap<String, Absent>,
) -> Surface {
    let s = |k: &str| t.get(k).and_then(|v| v.as_str()).map(str::to_string);
    let f = |k: &str| {
        t.get(k)
            .and_then(|v| v.as_float().or_else(|| v.as_integer().map(|i| i as f64)))
    };
    Surface {
        key: key.to_string(),
        name: s("name").unwrap_or_else(|| key.to_string()),
        lut_family: s("lut_family").as_deref().and_then(LutFamily::parse),
        lut_surface: s("lut_surface"),
        g4_surface_type: s("g4_surface_type"),
        lut_dataset: s("lut_dataset"),
        treatment: s("treatment"),
        reflector: s("reflector"),
        reflector_material: s("reflector_material"),
        coupling: s("coupling").as_deref().and_then(Coupling::parse),
        coupling_material: s("coupling_material"),
        coupling_index: f("coupling_index"),
        reflectivity: f("reflectivity"),
        reflectivity_spectrum: t
            .get("reflectivity_spectrum")
            .and_then(|v| v.as_table())
            .and_then(Curve::from_wavelength_toml),
        thickness_um: f("thickness_um"),
        note: s("note"),
        sources: sources.clone(),
        absent: absent.clone(),
    }
}
