//! Provenance and declared absences — the Rust mirror of `pymat.sources`.
//!
//! Both are sidecars keyed by dotted property path (`"optical.light_yield"`),
//! carried on [`crate::Material`] and [`crate::Surface`] rather than wrapped
//! around each value. A value stays an `f64`; where it came from is metadata
//! *about* the value (ADR-0003 §1).

use std::collections::HashMap;

/// Where a value came from.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Source {
    /// Short BibTeX-style key, e.g. `"bosca_lopez_2023"`.
    pub citation: String,
    /// One of `doi`, `qid`, `handbook`, `vendor`, `measured`.
    pub kind: String,
    /// The reference itself — a DOI, a Wikidata QID, a URL, a handbook page.
    pub reference: String,
    /// `CC0`, `PD-USGov`, `CC-BY-3.0`, `CC-BY-4.0`, `CC-BY-SA-4.0`,
    /// `Geant4-SL`, or `proprietary-reference-only`.
    pub license: String,
    /// Free-text detail — measurement conditions, caveats, corroboration.
    pub note: Option<String>,
}

impl Source {
    pub(crate) fn from_toml(table: &toml::Table) -> Option<Self> {
        let get = |k: &str| table.get(k).and_then(|v| v.as_str()).map(str::to_string);
        Some(Self {
            citation: get("citation")?,
            kind: get("kind")?,
            reference: get("ref")?,
            license: get("license")?,
            note: get("note"),
        })
    }
}

/// Why a value is missing.
///
/// The negative twin of [`Source`]. A `None` property with no `Absent` entry
/// means "we have not said anything about this"; a `None` with an entry means
/// "we looked, and here is why there is no number". A transport engine should
/// treat those differently — the first is a gap in the database, the second is
/// a fact about the literature (ADR-0004 §6).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Absent {
    /// One of `not-measured`, `not-applicable`, `not-separable`,
    /// `proprietary`, `pending`. Validated on the Python side at load.
    pub reason: String,
    /// What was searched for, what was found instead, what would fill the gap.
    pub note: Option<String>,
}

impl Absent {
    pub(crate) fn from_toml(table: &toml::Table) -> Option<Self> {
        Some(Self {
            reason: table.get("reason")?.as_str()?.to_string(),
            note: table
                .get("note")
                .and_then(|v| v.as_str())
                .map(str::to_string),
        })
    }
}

/// Parse a `_sources` table into `{path: Source}`.
pub(crate) fn parse_sources(table: &toml::Table) -> HashMap<String, Source> {
    table
        .iter()
        .filter_map(|(k, v)| Some((k.clone(), Source::from_toml(v.as_table()?)?)))
        .collect()
}

/// Parse an `_absent` table into `{path: Absent}`.
pub(crate) fn parse_absent(table: &toml::Table) -> HashMap<String, Absent> {
    table
        .iter()
        .filter_map(|(k, v)| Some((k.clone(), Absent::from_toml(v.as_table()?)?)))
        .collect()
}

/// Overlay `child` onto `parent`; child wins on collision.
pub(crate) fn overlay<T: Clone>(
    parent: &HashMap<String, T>,
    child: HashMap<String, T>,
) -> HashMap<String, T> {
    let mut out = parent.clone();
    out.extend(child);
    out
}
