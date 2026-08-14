//! # rs-materials
//!
//! Material database and formula parsing for Monte Carlo particle transport.
//!
//! Reads py-mat's TOML material files and exposes material properties
//! (density, formula, composition, optical/scintillator data) for use in
//! Rust-based physics engines like strata.
//!
//! ## Scope
//!
//! The **physics** domains are typed in full fidelity — optical, nuclear,
//! mechanical, thermal — including wavelength-resolved spectra, temperature
//! curves, uncertainty, `_sources` provenance and `_absent` declarations.
//! `manufacturing`, `compliance`, `sourcing` and `vis` are deliberately not
//! typed; they remain reachable through [`Material::raw`], so no field in the
//! database is ever unusable from Rust. See ADR-0004 §7.
//!
//! ## Optical transport
//!
//! ```
//! use rs_materials::MaterialDb;
//!
//! let db = MaterialDb::builtin();
//! let lyso = db.get("lyso").unwrap();
//! let opt = lyso.optical().unwrap();
//!
//! // Wavelength accessors fall back to the scalar and clamp outside the
//! // measured range — they never extrapolate.
//! assert_eq!(opt.n_at(420.0), Some(1.82));
//!
//! // Self-absorption is a distinct fate from matrix loss.
//! assert_eq!(opt.absorption_length_reabs, Some(588.0));
//!
//! // A value can be absent *and say why*.
//! assert!(lyso.is_absent("optical.emission_spectrum"));
//! ```
//!
//! ## Surface finishes
//!
//! ```
//! use rs_materials::{Coupling, SurfaceDb};
//!
//! let surfaces = SurfaceDb::builtin();
//! let s = surfaces.by_lut_surface("PolishedESRGrease_LUT").unwrap();
//! assert!(s.is_optical_contact());
//! assert_eq!(s.coupling_index, Some(1.465));
//!
//! // Air-gap and index-filled coupling are physically different and are
//! // distinguishable here.
//! assert_eq!(surfaces.with_coupling(Coupling::AirGap).len(), 19);
//! ```
//!
//! ## Quick start
//!
//! ```
//! use rs_materials::MaterialDb;
//!
//! let db = MaterialDb::builtin();
//! let lyso = db.get("lyso").unwrap();
//! assert_eq!(lyso.density(), Some(7.1));
//! ```
//!
//! ## Formula parsing (standalone)
//!
//! ```
//! let elems = rs_materials::parse_formula("Lu1.8Y0.2SiO5").unwrap();
//! assert_eq!(elems[0], ("Lu".into(), 1.8));
//! ```

pub mod curves;
pub mod db;
pub mod elements;
pub mod error;
pub mod formula;
pub mod material;
pub mod provenance;
pub mod surface;

// Re-exports for convenience.
pub use curves::Curve;
pub use db::MaterialDb;
pub use error::MatError;
pub use formula::{
    atom_to_mass_fractions, formula_to_mass_fractions, mass_to_atom_fractions, parse_formula,
};
pub use material::{
    DecayComponent, Material, MechanicalProperties, NuclearProperties, OpticalProperties,
    ThermalProperties,
};
pub use provenance::{Absent, Source};
pub use surface::{Coupling, LutFamily, Surface, SurfaceDb};
