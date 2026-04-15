//! Material database: loads TOML files, provides lookup by key.

use std::collections::HashMap;
use std::path::{Path, PathBuf};

use crate::error::MatError;
use crate::material::{Material, OpticalProperties};

/// Embedded TOML data files (compiled into the binary).
const BUILTIN_TOML: &[(&str, &str)] = &[
    ("metals", include_str!("../data/metals.toml")),
    ("scintillators", include_str!("../data/scintillators.toml")),
    ("plastics", include_str!("../data/plastics.toml")),
    ("ceramics", include_str!("../data/ceramics.toml")),
    ("electronics", include_str!("../data/electronics.toml")),
    ("liquids", include_str!("../data/liquids.toml")),
    ("gases", include_str!("../data/gases.toml")),
];

/// Categories of TOML data files.
const CATEGORIES: &[&str] = &[
    "metals",
    "scintillators",
    "plastics",
    "ceramics",
    "electronics",
    "liquids",
    "gases",
];

/// Property-group keys that should NOT be treated as child materials.
const PROPERTY_GROUPS: &[&str] = &[
    "mechanical",
    "thermal",
    "electrical",
    "optical",
    "pbr",
    "manufacturing",
    "compliance",
    "sourcing",
];

/// The material database. `Send + Sync` for `Arc` sharing.
#[derive(Debug, Clone)]
pub struct MaterialDb {
    materials: HashMap<String, Material>,
}

impl MaterialDb {
    /// Load the built-in material database (no external files needed).
    ///
    /// All 7 TOML category files are embedded in the binary at compile time.
    /// This is the recommended way to use the database as a crates.io dependency.
    pub fn builtin() -> Self {
        let mut materials = HashMap::new();
        for &(_category, raw) in BUILTIN_TOML {
            let table: toml::Table =
                toml::from_str(raw).expect("embedded TOML should always parse");
            parse_top_level(&table, &mut materials);
        }
        Self { materials }
    }

    /// Load all TOML category files from a data directory.
    ///
    /// The directory should contain `metals.toml`, `scintillators.toml`, etc.
    /// Use this for custom or extended material databases.
    pub fn open(data_dir: impl AsRef<Path>) -> Result<Self, MatError> {
        let dir = data_dir.as_ref();
        if !dir.is_dir() {
            return Err(MatError::MissingDataDir(dir.to_path_buf()));
        }

        let mut materials = HashMap::new();

        for category in CATEGORIES {
            let path = dir.join(format!("{category}.toml"));
            if !path.exists() {
                continue;
            }
            let raw = std::fs::read_to_string(&path).map_err(|e| MatError::TomlRead {
                path: path.clone(),
                source: e,
            })?;
            let table: toml::Table = toml::from_str(&raw).map_err(|e| MatError::TomlParse {
                path: path.clone(),
                source: e,
            })?;
            parse_top_level(&table, &mut materials);
        }

        Ok(Self { materials })
    }

    /// Load from the default py-mat data directory (auto-detected relative to the crate).
    ///
    /// This looks for `../src/pymat/data/` relative to the mat-rs crate root,
    /// which works for development within the mat monorepo.
    pub fn from_pymat_data() -> Result<Self, MatError> {
        let manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        let data_dir = manifest.join("../src/pymat/data");
        Self::open(data_dir)
    }

    /// Get a material by key. Keys are dot-separated paths like `"lyso"` or `"stainless.s316L"`.
    pub fn get(&self, key: &str) -> Result<&Material, MatError> {
        self.materials
            .get(key)
            .ok_or_else(|| MatError::NotFound(key.to_string()))
    }

    /// List all material keys.
    pub fn keys(&self) -> impl Iterator<Item = &str> {
        self.materials.keys().map(|s| s.as_str())
    }

    /// Total number of materials loaded.
    pub fn len(&self) -> usize {
        self.materials.len()
    }

    /// Whether the database is empty.
    pub fn is_empty(&self) -> bool {
        self.materials.is_empty()
    }
}

/// Parse top-level TOML keys as root materials and recurse into children.
fn parse_top_level(table: &toml::Table, out: &mut HashMap<String, Material>) {
    for (key, value) in table {
        if let Some(mat_table) = value.as_table() {
            let mat = build_material(key, key, mat_table, None);
            out.insert(key.clone(), mat);
            parse_children(key, mat_table, out, mat_table);
        }
    }
}

/// Recursively parse child materials from nested TOML tables.
fn parse_children(
    parent_key: &str,
    table: &toml::Table,
    out: &mut HashMap<String, Material>,
    parent_table: &toml::Table,
) {
    for (child_key, child_value) in table {
        if PROPERTY_GROUPS.contains(&child_key.as_str()) {
            continue;
        }
        if let Some(child_table) = child_value.as_table() {
            // Skip if this looks like a property (has no sub-tables that aren't property groups)
            if is_leaf_property(child_table) {
                continue;
            }
            let full_key = format!("{parent_key}.{child_key}");
            let mat = build_material(&full_key, child_key, child_table, Some(parent_table));
            out.insert(full_key.clone(), mat);
            parse_children(&full_key, child_table, out, child_table);
        }
    }
}

/// Check if a table is a leaf property value (not a child material).
/// A child material typically has property group sub-tables or a `name` key.
fn is_leaf_property(table: &toml::Table) -> bool {
    // If it has a `name` key, it's definitely a material
    if table.contains_key("name") {
        return false;
    }
    // If it has any property group sub-tables, it's a material
    for key in PROPERTY_GROUPS {
        if table.contains_key(*key) {
            return false;
        }
    }
    // If it has any sub-table children that aren't property groups, it's a material
    for (key, val) in table {
        if val.is_table() && !PROPERTY_GROUPS.contains(&key.as_str()) {
            return false;
        }
    }
    true
}

/// Build a Material from a TOML table, optionally inheriting from a parent.
fn build_material(
    full_key: &str,
    local_key: &str,
    table: &toml::Table,
    parent_table: Option<&toml::Table>,
) -> Material {
    let name = table
        .get("name")
        .and_then(|v| v.as_str())
        .unwrap_or(local_key)
        .to_string();

    let formula = table
        .get("formula")
        .and_then(|v| v.as_str())
        .or_else(|| {
            parent_table
                .and_then(|p| p.get("formula"))
                .and_then(|v| v.as_str())
        })
        .map(|s| s.to_string());

    let composition =
        extract_composition(table).or_else(|| parent_table.and_then(extract_composition));

    let density = extract_density(table).or_else(|| parent_table.and_then(extract_density));

    let optical = extract_optical(table, parent_table);

    Material {
        key: full_key.to_string(),
        name,
        formula,
        composition,
        density,
        optical,
    }
}

fn extract_composition(table: &toml::Table) -> Option<HashMap<String, f64>> {
    let comp = table.get("composition")?;
    let comp_table = comp.as_table()?;
    let mut map = HashMap::new();
    for (k, v) in comp_table {
        if let Some(f) = v.as_float().or_else(|| v.as_integer().map(|i| i as f64)) {
            map.insert(k.clone(), f);
        }
    }
    if map.is_empty() { None } else { Some(map) }
}

fn extract_density(table: &toml::Table) -> Option<f64> {
    let mech = table.get("mechanical")?.as_table()?;
    // Try *_value format first, then plain
    mech.get("density_value")
        .or_else(|| mech.get("density"))
        .and_then(|v| v.as_float().or_else(|| v.as_integer().map(|i| i as f64)))
}

fn extract_optical(
    table: &toml::Table,
    parent_table: Option<&toml::Table>,
) -> Option<OpticalProperties> {
    let opt_table = table.get("optical").and_then(|v| v.as_table());
    let parent_opt = parent_table
        .and_then(|p| p.get("optical"))
        .and_then(|v| v.as_table());

    if opt_table.is_none() && parent_opt.is_none() {
        return None;
    }

    let get = |key: &str| -> Option<f64> {
        opt_table
            .and_then(|t| t.get(key))
            .or_else(|| parent_opt.and_then(|t| t.get(key)))
            .and_then(|v| v.as_float().or_else(|| v.as_integer().map(|i| i as f64)))
    };

    Some(OpticalProperties {
        refractive_index: get("refractive_index"),
        light_yield: get("light_yield"),
        decay_time: get("decay_time"),
        emission_peak: get("emission_peak"),
        radiation_length: get("radiation_length"),
        interaction_length: get("interaction_length"),
    })
}
