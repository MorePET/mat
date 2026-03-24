//! # rs-materials
//!
//! Material database and formula parsing for Monte Carlo particle transport.
//!
//! Reads py-mat's TOML material files and exposes material properties
//! (density, formula, composition, optical/scintillator data) for use in
//! Rust-based physics engines like strata.
//!
//! ## Quick start
//!
//! ```no_run
//! use rs_materials::MaterialDb;
//!
//! let db = MaterialDb::open("path/to/mat/data").unwrap();
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

pub mod db;
pub mod elements;
pub mod error;
pub mod formula;
pub mod material;

// Re-exports for convenience.
pub use db::MaterialDb;
pub use error::MatError;
pub use formula::{
    atom_to_mass_fractions, formula_to_mass_fractions, mass_to_atom_fractions, parse_formula,
};
pub use material::{Material, OpticalProperties};
