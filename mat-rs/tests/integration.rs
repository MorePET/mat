//! Integration tests: load actual py-mat TOML data and verify material properties.

use rs_materials::{
    MaterialDb, atom_to_mass_fractions, formula_to_mass_fractions, mass_to_atom_fractions,
    parse_formula,
};

fn db() -> MaterialDb {
    MaterialDb::from_pymat_data().expect("failed to load py-mat data")
}

// ---------------------------------------------------------------------------
// Database loading
// ---------------------------------------------------------------------------

#[test]
fn loads_all_categories() {
    let db = db();
    assert!(db.len() > 50, "expected >50 materials, got {}", db.len());
}

#[test]
fn builtin_matches_file_loaded() {
    let from_files = db();
    let builtin = MaterialDb::builtin();
    assert_eq!(
        builtin.len(),
        from_files.len(),
        "builtin and file-loaded should have same number of materials"
    );

    // Spot-check a few materials
    for key in &[
        "lyso",
        "stainless.s316L",
        "water",
        "air",
        "alumina",
        "fr4",
        "peek",
    ] {
        let b = builtin.get(key).unwrap();
        let f = from_files.get(key).unwrap();
        assert_eq!(b.density(), f.density(), "density mismatch for {key}");
        assert_eq!(b.formula(), f.formula(), "formula mismatch for {key}");
    }
}

#[test]
fn builtin_lyso_properties() {
    let db = MaterialDb::builtin();
    let lyso = db.get("lyso").unwrap();
    assert_eq!(lyso.density(), Some(7.1));
    assert_eq!(lyso.formula(), Some("Lu1.8Y0.2SiO5"));
    let opt = lyso.optical().unwrap();
    assert_eq!(opt.light_yield, Some(32000.0));
}

#[test]
fn all_materials_have_names() {
    let db = db();
    for key in db.keys() {
        let mat = db.get(key).unwrap();
        assert!(!mat.name.is_empty(), "material {key} has empty name");
    }
}

// ---------------------------------------------------------------------------
// Scintillators
// ---------------------------------------------------------------------------

#[test]
fn lyso_properties() {
    let db = db();
    let lyso = db.get("lyso").unwrap();
    assert_eq!(lyso.name, "LYSO");
    assert_eq!(lyso.formula(), Some("Lu1.8Y0.2SiO5"));
    assert_eq!(lyso.density(), Some(7.1));

    let opt = lyso.optical().expect("LYSO should have optical properties");
    assert_eq!(opt.refractive_index, Some(1.82));
    assert_eq!(opt.light_yield, Some(32000.0));
    assert_eq!(opt.decay_time, Some(41.0));
    assert_eq!(opt.emission_peak, Some(420.0));
    assert_eq!(opt.radiation_length, Some(1.14));
}

#[test]
fn lyso_mass_fractions() {
    let db = db();
    let lyso = db.get("lyso").unwrap();
    let fracs = lyso.mass_fractions().expect("LYSO formula should parse");
    let sum: f64 = fracs.iter().map(|(_, f)| f).sum();
    assert!((sum - 1.0).abs() < 1e-9, "mass fractions must sum to 1.0");

    // Lu should dominate by mass (>50%)
    let lu = fracs.iter().find(|(s, _)| s == "Lu").unwrap().1;
    assert!(lu > 0.5, "Lu mass fraction should be >50%, got {lu}");
}

#[test]
fn lyso_ce_inherits_from_lyso() {
    let db = db();
    let ce = db.get("lyso.Ce").unwrap();
    assert_eq!(ce.name, "LYSO:Ce");
    // Should inherit density from parent
    assert_eq!(ce.density(), Some(7.1));
    // Should have its own optical with overridden light_yield
    let opt = ce.optical().unwrap();
    assert_eq!(opt.light_yield, Some(33000.0));
}

#[test]
fn bgo_properties() {
    let db = db();
    let bgo = db.get("bgo").unwrap();
    assert_eq!(bgo.formula(), Some("Bi4Ge3O12"));
    assert_eq!(bgo.density(), Some(7.13));

    let opt = bgo.optical().unwrap();
    assert_eq!(opt.refractive_index, Some(2.15));
    assert_eq!(opt.light_yield, Some(8500.0));
    assert_eq!(opt.decay_time, Some(300.0));
}

#[test]
fn nai_tl_inherits() {
    let db = db();
    let nai_tl = db.get("nai.Tl").unwrap();
    assert_eq!(nai_tl.name, "NaI(Tl)");
    // Inherits density from parent nai
    assert_eq!(nai_tl.density(), Some(3.67));
}

#[test]
fn pwo_properties() {
    let db = db();
    let pwo = db.get("pwo").unwrap();
    assert_eq!(pwo.formula(), Some("PbWO4"));
    assert_eq!(pwo.density(), Some(8.28));
    let opt = pwo.optical().unwrap();
    assert_eq!(opt.decay_time, Some(6.0));
}

// ---------------------------------------------------------------------------
// Metals
// ---------------------------------------------------------------------------

#[test]
fn stainless_steel() {
    let db = db();
    let ss = db.get("stainless").unwrap();
    assert_eq!(ss.density(), Some(8.0));
    assert!(ss.composition.is_some());
    let comp = ss.composition.as_ref().unwrap();
    assert!(comp.contains_key("Fe"));
    assert!(comp.contains_key("Cr"));
}

#[test]
fn stainless_316l() {
    let db = db();
    let ss316 = db.get("stainless.s316L").unwrap();
    assert_eq!(ss316.name, "Stainless Steel 316L");
    assert_eq!(ss316.density(), Some(8.0));
    // Has its own composition
    let comp = ss316.composition.as_ref().unwrap();
    assert!(comp.contains_key("Mo"), "316L should contain Mo");
}

#[test]
fn stainless_316l_electropolished() {
    let db = db();
    let ep = db.get("stainless.s316L.electropolished").unwrap();
    assert_eq!(ep.name, "Stainless Steel 316L - Electropolished");
}

#[test]
fn aluminum() {
    let db = db();
    let al = db.get("aluminum").unwrap();
    assert_eq!(al.formula(), Some("Al"));
    assert_eq!(al.density(), Some(2.7));
}

#[test]
fn tungsten() {
    let db = db();
    let w = db.get("tungsten").unwrap();
    assert_eq!(w.density(), Some(19.3));
}

#[test]
fn havar_composition() {
    let db = db();
    let havar = db.get("havar").unwrap();
    assert_eq!(havar.density(), Some(8.3));
    let comp = havar.composition.as_ref().unwrap();
    assert!(comp.contains_key("Co"));
    let co = comp["Co"];
    assert!((co - 0.425).abs() < 1e-3);
}

#[test]
fn copper() {
    let db = db();
    let cu = db.get("copper").unwrap();
    assert_eq!(cu.formula(), Some("Cu"));
    assert_eq!(cu.density(), Some(8.96));
}

#[test]
fn lead() {
    let db = db();
    let pb = db.get("lead").unwrap();
    assert_eq!(pb.formula(), Some("Pb"));
    assert_eq!(pb.density(), Some(11.34));
}

// ---------------------------------------------------------------------------
// Gases
// ---------------------------------------------------------------------------

#[test]
fn air() {
    let db = db();
    let air = db.get("air").unwrap();
    assert_eq!(air.density(), Some(0.001204));
    let opt = air.optical().unwrap();
    assert_eq!(opt.refractive_index, Some(1.000293));
}

#[test]
fn vacuum() {
    let db = db();
    let vac = db.get("vacuum").unwrap();
    assert_eq!(vac.density(), Some(0.0));
}

#[test]
fn water() {
    let db = db();
    let h2o = db.get("water").unwrap();
    assert_eq!(h2o.formula(), Some("H2O"));
    assert_eq!(h2o.density(), Some(0.998));
}

#[test]
fn helium() {
    let db = db();
    let he = db.get("helium").unwrap();
    assert_eq!(he.formula(), Some("He"));
    assert_eq!(he.density(), Some(0.000166));
}

// ---------------------------------------------------------------------------
// Liquids
// ---------------------------------------------------------------------------

#[test]
fn heavy_water() {
    let db = db();
    let d2o = db.get("heavy_water").unwrap();
    assert_eq!(d2o.density(), Some(1.107));
}

#[test]
fn glycerol() {
    let db = db();
    let gly = db.get("glycerol").unwrap();
    assert_eq!(gly.formula(), Some("C3H8O3"));
    assert_eq!(gly.density(), Some(1.261));
}

// ---------------------------------------------------------------------------
// Ceramics
// ---------------------------------------------------------------------------

#[test]
fn alumina() {
    let db = db();
    let al2o3 = db.get("alumina").unwrap();
    assert_eq!(al2o3.formula(), Some("Al2O3"));
    assert_eq!(al2o3.density(), Some(3.95));
}

#[test]
fn fused_silica() {
    let db = db();
    let sio2 = db.get("glass.fused_silica").unwrap();
    assert_eq!(sio2.formula(), Some("SiO2"));
    assert_eq!(sio2.density(), Some(2.2));
    let opt = sio2.optical().unwrap();
    assert_eq!(opt.refractive_index, Some(1.46));
}

// ---------------------------------------------------------------------------
// Plastics
// ---------------------------------------------------------------------------

#[test]
fn peek() {
    let db = db();
    let peek = db.get("peek").unwrap();
    assert_eq!(peek.formula(), Some("C19H12O3"));
    assert_eq!(peek.density(), Some(1.32));
}

#[test]
fn pmma_optical() {
    let db = db();
    let pmma = db.get("pmma").unwrap();
    assert_eq!(pmma.density(), Some(1.18));
    let opt = pmma.optical().unwrap();
    assert_eq!(opt.refractive_index, Some(1.49));
}

// ---------------------------------------------------------------------------
// Electronics
// ---------------------------------------------------------------------------

#[test]
fn fr4() {
    let db = db();
    let fr4 = db.get("fr4").unwrap();
    assert_eq!(fr4.density(), Some(1.86));
}

// ---------------------------------------------------------------------------
// Formula parsing (standalone, no DB)
// ---------------------------------------------------------------------------

#[test]
fn parse_complex_formula() {
    let elems = parse_formula("Bi4Ge3O12").unwrap();
    assert_eq!(elems.len(), 3);
    assert_eq!(elems[0], ("Bi".into(), 4.0));
    assert_eq!(elems[1], ("Ge".into(), 3.0));
    assert_eq!(elems[2], ("O".into(), 12.0));
}

#[test]
fn parse_fractional_formula() {
    let elems = parse_formula("Lu1.8Y0.2SiO5").unwrap();
    assert_eq!(elems.len(), 4);
    assert!((elems[0].1 - 1.8).abs() < 1e-9);
    assert!((elems[1].1 - 0.2).abs() < 1e-9);
}

#[test]
fn formula_mass_fractions_sum_to_one() {
    for formula in &[
        "H2O",
        "Al2O3",
        "Lu1.8Y0.2SiO5",
        "Bi4Ge3O12",
        "SiO2",
        "PbWO4",
        "NaI",
    ] {
        let fracs = formula_to_mass_fractions(formula).unwrap();
        let sum: f64 = fracs.iter().map(|(_, f)| f).sum();
        assert!(
            (sum - 1.0).abs() < 1e-9,
            "mass fractions for {formula} sum to {sum}, not 1.0"
        );
    }
}

#[test]
fn mass_atom_roundtrip_all() {
    for formula in &["H2O", "Al2O3", "SiO2", "NaI", "Bi4Ge3O12"] {
        let counts = parse_formula(formula).unwrap();
        let total: f64 = counts.iter().map(|(_, c)| c).sum();
        let atom_fracs: Vec<(String, f64)> =
            counts.iter().map(|(s, c)| (s.clone(), c / total)).collect();

        let mass_fracs = atom_to_mass_fractions(&atom_fracs).unwrap();
        let back = mass_to_atom_fractions(&mass_fracs).unwrap();

        for (orig, recovered) in atom_fracs.iter().zip(back.iter()) {
            assert_eq!(orig.0, recovered.0);
            assert!(
                (orig.1 - recovered.1).abs() < 1e-9,
                "roundtrip failed for {formula}/{}: {} vs {}",
                orig.0,
                orig.1,
                recovered.1
            );
        }
    }
}

// ---------------------------------------------------------------------------
// Edge cases
// ---------------------------------------------------------------------------

#[test]
fn material_not_found() {
    let db = db();
    assert!(db.get("nonexistent_material").is_err());
}

#[test]
fn material_without_formula_returns_none() {
    let db = db();
    // stainless has composition but no formula
    let ss = db.get("stainless").unwrap();
    assert!(ss.formula().is_none());
    assert!(ss.mass_fractions().is_none());
}

#[test]
fn material_without_optical_returns_none() {
    let db = db();
    let pb = db.get("lead").unwrap();
    assert!(pb.optical().is_none());
}

#[test]
fn thread_safety() {
    // MaterialDb should be Send + Sync for Arc sharing
    fn assert_send_sync<T: Send + Sync>() {}
    assert_send_sync::<MaterialDb>();
    assert_send_sync::<rs_materials::Material>();
}
