//! Chemical formula parsing with support for fractional stoichiometry.
//!
//! Parses formulas like `"Lu1.8Y0.2SiO5"` into `[(Lu, 1.8), (Y, 0.2), (Si, 1.0), (O, 5.0)]`.

use std::collections::HashMap;

use regex::Regex;

use crate::elements::ATOMIC_WEIGHT;
use crate::error::MatError;

/// Parse a chemical formula into element → count pairs.
///
/// Supports integer and fractional stoichiometry:
/// - `"H2O"` → `{H: 2.0, O: 1.0}`
/// - `"Lu1.8Y0.2SiO5"` → `{Lu: 1.8, Y: 0.2, Si: 1.0, O: 5.0}`
/// - `"Al2O3"` → `{Al: 2.0, O: 3.0}`
///
/// Dopant notation (`:Ce`) is stripped before parsing.
pub fn parse_formula(formula: &str) -> Result<Vec<(String, f64)>, MatError> {
    // Strip dopant notation (e.g., "Lu1.8Y0.2SiO5:Ce" → "Lu1.8Y0.2SiO5")
    let clean = formula.split(':').next().unwrap_or(formula);

    let re = Regex::new(r"([A-Z][a-z]?)(\d+\.?\d*)?").unwrap();
    let mut elements: Vec<(String, f64)> = Vec::new();
    let mut seen: HashMap<String, usize> = HashMap::new();

    for cap in re.captures_iter(clean) {
        let symbol = cap.get(1).map_or("", |m| m.as_str());
        if symbol.is_empty() {
            continue;
        }
        // Validate element symbol
        if !ATOMIC_WEIGHT.contains_key(symbol) {
            return Err(MatError::UnknownElement(symbol.to_string()));
        }
        let count: f64 = cap
            .get(2)
            .map_or(1.0, |m| m.as_str().parse().unwrap_or(1.0));

        if let Some(&idx) = seen.get(symbol) {
            elements[idx].1 += count;
        } else {
            seen.insert(symbol.to_string(), elements.len());
            elements.push((symbol.to_string(), count));
        }
    }

    if elements.is_empty() {
        return Err(MatError::InvalidFormula(formula.to_string()));
    }

    Ok(elements)
}

/// Convert a chemical formula to elemental mass fractions (summing to 1.0).
pub fn formula_to_mass_fractions(formula: &str) -> Result<Vec<(String, f64)>, MatError> {
    let counts = parse_formula(formula)?;
    let mut total_mass = 0.0;
    let mut masses: Vec<(String, f64)> = Vec::new();

    for (sym, count) in &counts {
        let w = ATOMIC_WEIGHT
            .get(sym.as_str())
            .ok_or_else(|| MatError::UnknownElement(sym.clone()))?;
        let mass = count * w;
        masses.push((sym.clone(), mass));
        total_mass += mass;
    }

    if total_mass == 0.0 {
        return Err(MatError::InvalidFormula(formula.to_string()));
    }

    Ok(masses
        .into_iter()
        .map(|(sym, m)| (sym, m / total_mass))
        .collect())
}

/// Convert mass fractions → atom fractions.
///
/// Input: `[(symbol, mass_fraction)]` where fractions sum to ~1.0.
/// Output: `[(symbol, atom_fraction)]` normalized to sum to 1.0.
pub fn mass_to_atom_fractions(
    mass_fractions: &[(String, f64)],
) -> Result<Vec<(String, f64)>, MatError> {
    let mut moles: Vec<(String, f64)> = Vec::new();
    let mut total = 0.0;

    for (sym, w) in mass_fractions {
        let aw = ATOMIC_WEIGHT
            .get(sym.as_str())
            .ok_or_else(|| MatError::UnknownElement(sym.clone()))?;
        let m = w / aw;
        moles.push((sym.clone(), m));
        total += m;
    }

    if total == 0.0 {
        return Ok(Vec::new());
    }

    Ok(moles.into_iter().map(|(sym, m)| (sym, m / total)).collect())
}

/// Convert atom fractions → mass fractions.
///
/// Input: `[(symbol, atom_fraction)]` where fractions sum to ~1.0.
/// Output: `[(symbol, mass_fraction)]` normalized to sum to 1.0.
pub fn atom_to_mass_fractions(
    atom_fractions: &[(String, f64)],
) -> Result<Vec<(String, f64)>, MatError> {
    let mut masses: Vec<(String, f64)> = Vec::new();
    let mut total = 0.0;

    for (sym, x) in atom_fractions {
        let aw = ATOMIC_WEIGHT
            .get(sym.as_str())
            .ok_or_else(|| MatError::UnknownElement(sym.clone()))?;
        let m = x * aw;
        masses.push((sym.clone(), m));
        total += m;
    }

    if total == 0.0 {
        return Ok(Vec::new());
    }

    Ok(masses
        .into_iter()
        .map(|(sym, m)| (sym, m / total))
        .collect())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_h2o() {
        let result = parse_formula("H2O").unwrap();
        assert_eq!(result.len(), 2);
        assert_eq!(result[0], ("H".into(), 2.0));
        assert_eq!(result[1], ("O".into(), 1.0));
    }

    #[test]
    fn test_parse_al2o3() {
        let result = parse_formula("Al2O3").unwrap();
        assert_eq!(result[0], ("Al".into(), 2.0));
        assert_eq!(result[1], ("O".into(), 3.0));
    }

    #[test]
    fn test_parse_lyso() {
        let result = parse_formula("Lu1.8Y0.2SiO5").unwrap();
        assert_eq!(result.len(), 4);
        assert_eq!(result[0].0, "Lu");
        assert!((result[0].1 - 1.8).abs() < 1e-9);
        assert_eq!(result[1].0, "Y");
        assert!((result[1].1 - 0.2).abs() < 1e-9);
        assert_eq!(result[2].0, "Si");
        assert!((result[2].1 - 1.0).abs() < 1e-9);
        assert_eq!(result[3].0, "O");
        assert!((result[3].1 - 5.0).abs() < 1e-9);
    }

    #[test]
    fn test_parse_single_element() {
        let result = parse_formula("Cu").unwrap();
        assert_eq!(result.len(), 1);
        assert_eq!(result[0], ("Cu".into(), 1.0));
    }

    #[test]
    fn test_parse_with_dopant() {
        let result = parse_formula("Lu1.8Y0.2SiO5:Ce").unwrap();
        assert_eq!(result.len(), 4);
        assert_eq!(result[0].0, "Lu");
    }

    #[test]
    fn test_parse_bgo() {
        let result = parse_formula("Bi4Ge3O12").unwrap();
        assert_eq!(result.len(), 3);
        assert_eq!(result[0], ("Bi".into(), 4.0));
        assert_eq!(result[1], ("Ge".into(), 3.0));
        assert_eq!(result[2], ("O".into(), 12.0));
    }

    #[test]
    fn test_invalid_formula() {
        assert!(parse_formula("").is_err());
        assert!(parse_formula("123").is_err());
    }

    #[test]
    fn test_unknown_element() {
        assert!(parse_formula("Xx2O3").is_err());
    }

    #[test]
    fn test_mass_fractions_h2o() {
        let fracs = formula_to_mass_fractions("H2O").unwrap();
        let h_frac = fracs.iter().find(|(s, _)| s == "H").unwrap().1;
        let o_frac = fracs.iter().find(|(s, _)| s == "O").unwrap().1;
        // H: 2*1.008 = 2.016, O: 16.00, total: 18.016
        assert!((h_frac - 2.016 / 18.016).abs() < 1e-3);
        assert!((o_frac - 16.00 / 18.016).abs() < 1e-3);
        // Sum to 1.0
        let sum: f64 = fracs.iter().map(|(_, f)| f).sum();
        assert!((sum - 1.0).abs() < 1e-9);
    }

    #[test]
    fn test_mass_fractions_lyso() {
        let fracs = formula_to_mass_fractions("Lu1.8Y0.2SiO5").unwrap();
        let sum: f64 = fracs.iter().map(|(_, f)| f).sum();
        assert!((sum - 1.0).abs() < 1e-9);
        // Lu should dominate by mass
        let lu = fracs.iter().find(|(s, _)| s == "Lu").unwrap().1;
        assert!(lu > 0.5);
    }

    #[test]
    fn test_mass_atom_roundtrip() {
        let formula_counts = parse_formula("Al2O3").unwrap();
        // Normalize to atom fractions
        let total: f64 = formula_counts.iter().map(|(_, c)| c).sum();
        let atom_fracs: Vec<(String, f64)> = formula_counts
            .iter()
            .map(|(s, c)| (s.clone(), c / total))
            .collect();

        let mass_fracs = atom_to_mass_fractions(&atom_fracs).unwrap();
        let back = mass_to_atom_fractions(&mass_fracs).unwrap();

        for (orig, recovered) in atom_fracs.iter().zip(back.iter()) {
            assert_eq!(orig.0, recovered.0);
            assert!(
                (orig.1 - recovered.1).abs() < 1e-9,
                "Mismatch for {}: {} vs {}",
                orig.0,
                orig.1,
                recovered.1
            );
        }
    }

    #[test]
    fn test_mass_to_atom_fractions_steel() {
        // Simplified stainless: Fe=0.70, Cr=0.18, Ni=0.12
        let mass_fracs = vec![
            ("Fe".into(), 0.70),
            ("Cr".into(), 0.18),
            ("Ni".into(), 0.12),
        ];
        let atom_fracs = mass_to_atom_fractions(&mass_fracs).unwrap();
        let sum: f64 = atom_fracs.iter().map(|(_, f)| f).sum();
        assert!((sum - 1.0).abs() < 1e-9);
        // Fe should still dominate
        let fe = atom_fracs.iter().find(|(s, _)| s == "Fe").unwrap().1;
        assert!(fe > 0.5);
    }
}
