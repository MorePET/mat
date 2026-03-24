//! Error types for mat-rs.

use std::path::PathBuf;

#[derive(Debug, thiserror::Error)]
pub enum MatError {
    #[error("unknown element symbol: {0}")]
    UnknownElement(String),

    #[error("invalid chemical formula: {0}")]
    InvalidFormula(String),

    #[error("material not found: {0}")]
    NotFound(String),

    #[error("failed to read TOML file {path}: {source}")]
    TomlRead {
        path: PathBuf,
        source: std::io::Error,
    },

    #[error("failed to parse TOML file {path}: {source}")]
    TomlParse {
        path: PathBuf,
        source: toml::de::Error,
    },

    #[error("missing data directory: {0}")]
    MissingDataDir(PathBuf),
}
