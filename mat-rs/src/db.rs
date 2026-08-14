//! Material database: loads TOML files, provides lookup by key.

use std::collections::HashMap;
use std::path::{Path, PathBuf};

use crate::curves::{Curve, float_array};
use crate::error::MatError;
use crate::material::{
    DecayComponent, Material, MechanicalProperties, NuclearProperties, OpticalProperties,
    ThermalProperties,
};
use crate::provenance::{Absent, Source, overlay, parse_absent, parse_sources};

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

/// Property-group keys that are NOT child materials.
///
/// Must stay in sync with the Python loader's list. `magnetic`, `vacuum`,
/// `nuclear`, `vis` and `custom` were missing here and only avoided being
/// mis-parsed as child materials because `is_leaf_property` happened to reject
/// them — an accident that would break the moment any of them gained a
/// sub-table. Fixed in #243.
const PROPERTY_GROUPS: &[&str] = &[
    "mechanical",
    "thermal",
    "electrical",
    "optical",
    "magnetic",
    "vacuum",
    "nuclear",
    "manufacturing",
    "compliance",
    "sourcing",
    "vis",
    "custom",
    "pbr",
];

/// Material-node scalar keys that are not child materials either.
const LEAF_KEYS: &[&str] = &[
    "name",
    "formula",
    "composition",
    "grade",
    "temper",
    "treatment",
    "vendor",
    "tags",
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

    /// All materials.
    pub fn values(&self) -> impl Iterator<Item = &Material> {
        self.materials.values()
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
        if key.starts_with('_') {
            continue;
        }
        if let Some(mat_table) = value.as_table() {
            resolve_node(
                key,
                key,
                mat_table,
                &toml::Table::new(),
                &HashMap::new(),
                &HashMap::new(),
                out,
            );
        }
    }
}

/// Recursively resolve a material node, applying parent inheritance.
///
/// `inherited` is the merged property state flowing down from ancestors — the
/// Rust equivalent of the Python loader's `deepcopy(parent_props)` overlay.
/// Previously this crate only ever consulted ONE level of parent, so a
/// grandchild (`lyso.Ce.saint_gobain.prelude420`) silently lost anything its
/// grandparent declared. Fixed in #243.
fn resolve_node(
    full_key: &str,
    local_key: &str,
    node: &toml::Table,
    inherited: &toml::Table,
    parent_sources: &HashMap<String, Source>,
    parent_absent: &HashMap<String, Absent>,
    out: &mut HashMap<String, Material>,
) {
    let merged = merge_node(inherited, node);

    let sources = match node.get("_sources").and_then(|v| v.as_table()) {
        Some(t) => overlay(parent_sources, parse_sources(t)),
        None => parent_sources.clone(),
    };
    let absent = match node.get("_absent").and_then(|v| v.as_table()) {
        Some(t) => overlay(parent_absent, parse_absent(t)),
        None => parent_absent.clone(),
    };

    let name = merged
        .get("name")
        .and_then(|v| v.as_str())
        .unwrap_or(local_key)
        .to_string();
    let str_field = |k: &str| merged.get(k).and_then(|v| v.as_str()).map(str::to_string);

    let mechanical = group(&merged, "mechanical").map(parse_mechanical);
    let density = mechanical.as_ref().and_then(|m| m.density);

    let material = Material {
        key: full_key.to_string(),
        name,
        formula: str_field("formula"),
        composition: extract_composition(&merged),
        density,
        treatment: str_field("treatment"),
        grade: str_field("grade"),
        vendor: str_field("vendor"),
        optical: group(&merged, "optical").map(parse_optical),
        nuclear: group(&merged, "nuclear").map(parse_nuclear),
        mechanical,
        thermal: group(&merged, "thermal").map(parse_thermal),
        sources: sources.clone(),
        absent: absent.clone(),
        raw: merged.clone(),
    };
    out.insert(full_key.to_string(), material);

    // A child must not inherit its parent's identity.
    let mut child_inherited = merged;
    for identity in ["name", "formula", "composition"] {
        child_inherited.remove(identity);
    }

    for (child_key, child_value) in node {
        if child_key.starts_with('_')
            || PROPERTY_GROUPS.contains(&child_key.as_str())
            || LEAF_KEYS.contains(&child_key.as_str())
        {
            continue;
        }
        if let Some(child_table) = child_value.as_table() {
            resolve_node(
                &format!("{full_key}.{child_key}"),
                child_key,
                child_table,
                &child_inherited,
                &sources,
                &absent,
                out,
            );
        }
    }
}

/// Overlay a node's own fields and property groups onto the inherited state.
///
/// Property groups merge key-by-key rather than wholesale: a child that sets
/// `[lyso.Ce.optical] light_yield` must keep its parent's `refractive_index`,
/// which a whole-table replacement would drop.
fn merge_node(inherited: &toml::Table, node: &toml::Table) -> toml::Table {
    let mut merged = inherited.clone();
    for (key, value) in node {
        if key.starts_with('_') {
            continue;
        }
        if PROPERTY_GROUPS.contains(&key.as_str())
            && let Some(own_group) = value.as_table()
        {
            let base = merged.get(key).and_then(|v| v.as_table()).cloned();
            let mut group = base.unwrap_or_default();
            for (gk, gv) in own_group {
                group.insert(gk.clone(), gv.clone());
            }
            merged.insert(key.clone(), toml::Value::Table(group));
            continue;
        }
        if LEAF_KEYS.contains(&key.as_str()) {
            merged.insert(key.clone(), value.clone());
        }
    }
    merged
}

fn group<'a>(table: &'a toml::Table, name: &str) -> Option<&'a toml::Table> {
    table.get(name).and_then(|v| v.as_table())
}

// ---------------------------------------------------------------------------
// Scalar / structured extraction
// ---------------------------------------------------------------------------

/// Read a scalar, accepting the plain form, the `<key>_value` form, and the
/// `{ nominal, stddev }` / `{ min, max }` uncertainty tables.
///
/// Returns `(nominal, stddev)`.
fn number(table: &toml::Table, key: &str) -> Option<(f64, Option<f64>)> {
    let raw = table
        .get(key)
        .or_else(|| table.get(&format!("{key}_value")))?;

    let as_f64 = |v: &toml::Value| v.as_float().or_else(|| v.as_integer().map(|i| i as f64));

    let (nominal, mut stddev) = if let Some(t) = raw.as_table() {
        let nominal = t.get("nominal").and_then(as_f64).or_else(|| {
            // {min, max} with no nominal -> midpoint, half-range as stddev.
            let lo = t.get("min").and_then(as_f64)?;
            let hi = t.get("max").and_then(as_f64)?;
            Some((lo + hi) / 2.0)
        })?;
        let sd = t.get("stddev").and_then(as_f64).or_else(|| {
            let lo = t.get("min").and_then(as_f64)?;
            let hi = t.get("max").and_then(as_f64)?;
            Some((hi - lo) / 2.0)
        });
        (nominal, sd)
    } else {
        (as_f64(raw)?, None)
    };

    // Sibling `<key>_stddev` sugar.
    if stddev.is_none() {
        stddev = table.get(&format!("{key}_stddev")).and_then(as_f64);
    }
    Some((nominal, stddev))
}

/// Read a scalar into `out`, recording any stddev in `sd`.
fn scalar(table: &toml::Table, key: &str, sd: &mut HashMap<String, f64>) -> Option<f64> {
    let (nominal, stddev) = number(table, key)?;
    if let Some(s) = stddev {
        sd.insert(key.to_string(), s);
    }
    Some(nominal)
}

fn wl_curve(table: &toml::Table, key: &str) -> Option<Curve> {
    Curve::from_wavelength_toml(table.get(key)?.as_table()?)
}

fn temp_curve(table: &toml::Table, key: &str) -> Option<Curve> {
    Curve::from_temp_toml(table.get(key)?.as_table()?)
}

fn parse_optical(t: &toml::Table) -> OpticalProperties {
    let mut sd = HashMap::new();
    OpticalProperties {
        refractive_index: scalar(t, "refractive_index", &mut sd),
        light_yield: scalar(t, "light_yield", &mut sd),
        decay_time: scalar(t, "decay_time", &mut sd),
        rise_time: scalar(t, "rise_time", &mut sd),
        emission_peak: scalar(t, "emission_peak", &mut sd),
        emission_range: t.get("emission_range").and_then(|v| {
            let a = float_array(v)?;
            (a.len() == 2).then(|| (a[0], a[1]))
        }),
        transparency: scalar(t, "transparency", &mut sd),
        reflectivity: scalar(t, "reflectivity", &mut sd),
        absorption_length: scalar(t, "absorption_length", &mut sd),
        absorption_coefficient: scalar(t, "absorption_coefficient", &mut sd),
        scattering_length: scalar(t, "scattering_length", &mut sd),
        rayleigh_length: scalar(t, "rayleigh_length", &mut sd),
        absorption_length_matrix: scalar(t, "absorption_length_matrix", &mut sd),
        absorption_length_reabs: scalar(t, "absorption_length_reabs", &mut sd),
        reemit_qe: scalar(t, "reemit_qe", &mut sd),
        dopant: t.get("dopant").and_then(|v| v.as_str()).map(str::to_string),
        dopant_pct: scalar(t, "dopant_pct", &mut sd),
        non_proportionality: scalar(t, "non_proportionality", &mut sd),
        intrinsic_resolution_pct_at_662kev: scalar(
            t,
            "intrinsic_resolution_pct_at_662keV",
            &mut sd,
        ),
        temperature_coefficient_light_yield: scalar(
            t,
            "temperature_coefficient_light_yield",
            &mut sd,
        ),
        hygroscopic: t.get("hygroscopic").and_then(|v| v.as_bool()),
        refractive_index_dispersion: wl_curve(t, "refractive_index_dispersion"),
        emission_spectrum: wl_curve(t, "emission_spectrum"),
        absorption_length_spectrum: wl_curve(t, "absorption_length_spectrum"),
        absorption_length_matrix_spectrum: wl_curve(t, "absorption_length_matrix_spectrum"),
        absorption_length_reabs_spectrum: wl_curve(t, "absorption_length_reabs_spectrum"),
        refractive_index_curve: temp_curve(t, "refractive_index_curve"),
        light_yield_curve: temp_curve(t, "light_yield_curve"),
        decay_time_curve: temp_curve(t, "decay_time_curve"),
        decay_components: parse_decay_components(t),
        stddev: sd,
    }
}

fn parse_decay_components(t: &toml::Table) -> Vec<DecayComponent> {
    let Some(array) = t.get("decay_components").and_then(|v| v.as_array()) else {
        return Vec::new();
    };
    array
        .iter()
        .filter_map(|entry| {
            let e = entry.as_table()?;
            let g = |k: &str| {
                e.get(k)
                    .and_then(|v| v.as_float().or_else(|| v.as_integer().map(|i| i as f64)))
            };
            Some(DecayComponent {
                tau_ns: g("tau_ns")?,
                fraction: g("fraction")?,
            })
        })
        .collect()
}

fn parse_nuclear(t: &toml::Table) -> NuclearProperties {
    let mut sd = HashMap::new();
    NuclearProperties {
        radiation_length: scalar(t, "radiation_length", &mut sd),
        interaction_length: scalar(t, "interaction_length", &mut sd),
        moliere_radius: scalar(t, "moliere_radius", &mut sd),
        z_eff: scalar(t, "Z_eff", &mut sd),
        mean_excitation_energy_ev: scalar(t, "mean_excitation_energy_eV", &mut sd),
        intrinsic_activity_bq_per_g: scalar(t, "intrinsic_activity_Bq_per_g", &mut sd),
        stddev: sd,
    }
}

fn parse_mechanical(t: &toml::Table) -> MechanicalProperties {
    let mut sd = HashMap::new();
    MechanicalProperties {
        density: scalar(t, "density", &mut sd),
        youngs_modulus: scalar(t, "youngs_modulus", &mut sd),
        poissons_ratio: scalar(t, "poissons_ratio", &mut sd),
        stddev: sd,
    }
}

fn parse_thermal(t: &toml::Table) -> ThermalProperties {
    let mut sd = HashMap::new();
    ThermalProperties {
        thermal_conductivity: scalar(t, "thermal_conductivity", &mut sd),
        specific_heat: scalar(t, "specific_heat", &mut sd),
        thermal_expansion: scalar(t, "thermal_expansion", &mut sd),
        melting_point: scalar(t, "melting_point", &mut sd),
        thermal_conductivity_curve: temp_curve(t, "thermal_conductivity_curve"),
        specific_heat_curve: temp_curve(t, "specific_heat_curve"),
        thermal_expansion_curve: temp_curve(t, "thermal_expansion_curve"),
        stddev: sd,
    }
}

/// One composition entry's fraction.
///
/// Entries are usually plain numbers but may be `{nominal, stddev}` or
/// `{min, max}` tables — the alloy TOMLs use ranges for trace elements. The
/// old parser only handled the plain form and dropped the rest, so an alloy
/// specified with ranges came through with holes in its composition.
fn composition_fraction(value: &toml::Value) -> Option<f64> {
    if let Some(f) = value
        .as_float()
        .or_else(|| value.as_integer().map(|i| i as f64))
    {
        return Some(f);
    }
    let inner = value.as_table()?;
    let as_f64 = |k: &str| {
        inner
            .get(k)
            .and_then(|x| x.as_float().or_else(|| x.as_integer().map(|i| i as f64)))
    };
    as_f64("nominal").or_else(|| Some((as_f64("min")? + as_f64("max")?) / 2.0))
}

fn extract_composition(table: &toml::Table) -> Option<HashMap<String, f64>> {
    let comp_table = table.get("composition")?.as_table()?;
    let mut map = HashMap::new();
    for (k, v) in comp_table {
        if let Some(fraction) = composition_fraction(v) {
            map.insert(k.clone(), fraction);
        }
    }
    if map.is_empty() { None } else { Some(map) }
}
