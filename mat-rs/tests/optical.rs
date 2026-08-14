//! Integration tests for the #243 schema growth: structured fields, curves,
//! uncertainty, provenance, declared absences, and the `raw()` escape hatch.
//!
//! Before #243 this crate exposed four `Option<f64>` optical scalars and
//! silently dropped everything else. These tests pin what it now carries.

use rs_materials::{MaterialDb, SurfaceDb};

fn db() -> MaterialDb {
    MaterialDb::builtin()
}

// ---------------------------------------------------------------------------
// The nuclear/optical split (#157) — verify no drift in either direction
// ---------------------------------------------------------------------------

#[test]
fn radiation_length_is_nuclear_not_optical() {
    let db = db();
    let lyso = db.get("lyso").unwrap();
    let nuc = lyso.nuclear().unwrap();
    assert_eq!(nuc.radiation_length, Some(1.14));
    assert_eq!(nuc.interaction_length, Some(25.0));

    // Nothing named radiation_length survives under optical.
    assert!(
        lyso.raw()
            .get("optical")
            .and_then(|o| o.as_table())
            .is_some()
    );
    assert!(
        lyso.raw()["optical"]
            .as_table()
            .unwrap()
            .get("radiation_length")
            .is_none(),
        "radiation_length must not reappear under [optical]"
    );
}

#[test]
fn intrinsic_activity_is_carried() {
    let db = db();
    let nuc = db.get("lyso").unwrap().nuclear().unwrap();
    assert_eq!(nuc.intrinsic_activity_bq_per_g, Some(40.0));
}

// ---------------------------------------------------------------------------
// Structured optical fields
// ---------------------------------------------------------------------------

#[test]
fn self_absorption_channel_is_exposed() {
    let db = db();
    let opt = db.get("lyso").unwrap().optical().unwrap();
    assert_eq!(opt.absorption_length_reabs, Some(588.0));
    assert_eq!(opt.absorption_length_reabs_at(420.0), Some(588.0));
    // The matrix channel is not measured for LYSO and must NOT be invented.
    assert_eq!(opt.absorption_length_matrix, None);
}

#[test]
fn lumped_absorption_length_is_exposed() {
    let db = db();
    let opt = db.get("lyso").unwrap().optical().unwrap();
    assert_eq!(opt.absorption_length, Some(200.0));
    assert_eq!(opt.absorption_length_at(500.0), Some(200.0));
}

#[test]
fn rise_time_and_dopant_are_exposed() {
    let db = db();
    let opt = db.get("lyso.Ce").unwrap().optical().unwrap();
    assert_eq!(opt.rise_time, Some(0.072));
    assert_eq!(opt.dopant.as_deref(), Some("Ce"));
    assert_eq!(opt.dopant_pct, Some(0.1));
}

#[test]
fn reflectivity_is_exposed() {
    // `[esr.optical] reflectivity = 98.5` was on disk since #147 and dropped
    // by BOTH loaders until #243.
    let db = db();
    let opt = db.get("esr").unwrap().optical().unwrap();
    assert_eq!(opt.reflectivity, Some(98.5));
}

#[test]
fn emission_range_is_exposed() {
    let db = db();
    let opt = db.get("lyso").unwrap().optical().unwrap();
    assert_eq!(opt.emission_range, Some((380.0, 600.0)));
}

#[test]
fn hygroscopic_flag_is_exposed() {
    let db = db();
    assert_eq!(
        db.get("lyso").unwrap().optical().unwrap().hygroscopic,
        Some(false)
    );
}

#[test]
fn emission_at_has_no_scalar_fallback() {
    // LYSO has an emission_peak but no spectrum — `emission_at` must return
    // None rather than pretending the peak is the band.
    let db = db();
    let opt = db.get("lyso").unwrap().optical().unwrap();
    assert_eq!(opt.emission_peak, Some(420.0));
    assert_eq!(opt.emission_at(420.0), None);
}

#[test]
fn n_at_falls_back_to_the_scalar_when_no_dispersion() {
    let db = db();
    let opt = db.get("lyso").unwrap().optical().unwrap();
    assert_eq!(opt.n_at(420.0), Some(1.82));
}

// ---------------------------------------------------------------------------
// Inheritance — including the grandchild case the old parser lost
// ---------------------------------------------------------------------------

#[test]
fn grandchild_inherits_from_grandparent() {
    let db = db();
    // prelude420 is lyso -> Ce -> saint_gobain -> prelude420. Its own table
    // sets only light_yield/decay_time/refractive_index; everything else must
    // come down the chain.
    let p = db.get("lyso.Ce.saint_gobain.prelude420").unwrap();
    assert_eq!(p.density(), Some(7.1)); // from lyso.mechanical
    let opt = p.optical().unwrap();
    assert_eq!(opt.light_yield, Some(33200.0)); // own
    assert_eq!(opt.refractive_index, Some(1.81)); // own, overriding lyso's 1.82
    assert_eq!(opt.emission_peak, Some(420.0)); // from lyso
    assert_eq!(opt.absorption_length_reabs, Some(588.0)); // from lyso
    assert_eq!(opt.dopant.as_deref(), Some("Ce")); // from lyso.Ce
}

#[test]
fn property_groups_merge_key_by_key() {
    // lyso.Ce sets light_yield but not refractive_index; a whole-table
    // replacement would drop the parent's value.
    let db = db();
    let opt = db.get("lyso.Ce").unwrap().optical().unwrap();
    assert_eq!(opt.light_yield, Some(33000.0)); // own
    assert_eq!(opt.refractive_index, Some(1.82)); // inherited
}

#[test]
fn inherited_variant_carries_its_treatment() {
    let db = db();
    let p = db.get("lyso.Ce.polished").unwrap();
    assert_eq!(p.treatment.as_deref(), Some("polished"));
    assert_eq!(p.name, "LYSO:Ce, polished");
    assert_eq!(p.optical().unwrap().light_yield, Some(33000.0));
}

#[test]
fn a_child_does_not_inherit_its_parents_name() {
    let db = db();
    assert_eq!(db.get("lyso").unwrap().name, "LYSO");
    assert_eq!(db.get("lyso.Ce").unwrap().name, "LYSO:Ce");
}

// ---------------------------------------------------------------------------
// Provenance and declared absences
// ---------------------------------------------------------------------------

#[test]
fn sources_are_exposed() {
    let db = db();
    let lyso = db.get("lyso").unwrap();
    let src = lyso.source_of("optical.absorption_length_reabs").unwrap();
    assert_eq!(src.citation, "bosca_lopez_2023");
    assert_eq!(src.kind, "doi");
    assert_eq!(src.reference, "10.1038/s41598-023-32689-z");
    assert_eq!(src.license, "CC-BY-4.0");
    assert!(src.note.is_some());
}

#[test]
fn sources_inherit_to_children() {
    let db = db();
    let polished = db.get("lyso.Ce.polished").unwrap();
    assert_eq!(
        polished
            .source_of("optical.absorption_length_reabs")
            .unwrap()
            .citation,
        "bosca_lopez_2023"
    );
}

#[test]
fn declared_absences_are_exposed() {
    let db = db();
    let lyso = db.get("lyso").unwrap();
    assert!(lyso.is_absent("optical.emission_spectrum"));
    assert!(lyso.is_absent("optical.reemit_qe"));
    let a = lyso.absent_reason("optical.reemit_qe").unwrap();
    assert_eq!(a.reason, "not-measured");
    assert!(a.note.as_ref().unwrap().contains("PLQY"));
}

#[test]
fn absence_is_distinguishable_from_silence() {
    let db = db();
    let lyso = db.get("lyso").unwrap();
    // Both are None on the value...
    assert_eq!(lyso.optical().unwrap().reemit_qe, None);
    assert_eq!(lyso.optical().unwrap().scattering_length, None);
    // ...but only one was searched for.
    assert!(lyso.is_absent("optical.reemit_qe"));
    assert!(!lyso.is_absent("optical.scattering_length"));
}

#[test]
fn absences_inherit_to_children() {
    let db = db();
    assert!(
        db.get("lyso.Ce.polished")
            .unwrap()
            .is_absent("optical.emission_spectrum")
    );
}

// ---------------------------------------------------------------------------
// Uncertainty
// ---------------------------------------------------------------------------

#[test]
fn nominal_stddev_tables_are_parsed() {
    // The canonical uncertainty form from ADR-0003 §3. No material in the
    // shipped corpus uses it yet — the schema landed in #149 but the data
    // sweep has not happened — so this exercises the parser directly rather
    // than asserting corpus presence, which would pass vacuously today and
    // fail confusingly the day someone adds the first stddev.
    let dir = std::env::temp_dir().join("rs_materials_stddev_test");
    std::fs::create_dir_all(&dir).unwrap();
    std::fs::write(
        dir.join("metals.toml"),
        r#"
        [x]
        name = "X"
        [x.optical]
        light_yield = { nominal = 33000.0, stddev = 1500.0 }
        decay_time = 41.0
        "#,
    )
    .unwrap();
    let db = MaterialDb::open(&dir).unwrap();
    let opt = db.get("x").unwrap().optical().unwrap();
    assert_eq!(opt.light_yield, Some(33000.0));
    assert_eq!(opt.stddev_of("light_yield"), Some(1500.0));
    // A plain scalar carries no uncertainty, and must not invent one.
    assert_eq!(opt.decay_time, Some(41.0));
    assert_eq!(opt.stddev_of("decay_time"), None);
    std::fs::remove_dir_all(&dir).ok();
}

#[test]
fn formula_does_not_inherit_matching_python() {
    // py-mat's loader reads `formula` from the node only, with no parent
    // fallback — `pymat.lyso.Ce.saint_gobain.prelude420.formula` is None.
    // This crate previously did a one-level parent lookup, which was a
    // silent divergence from the source of truth. Now aligned (#243).
    let db = db();
    assert_eq!(
        db.get("lyso.Ce").unwrap().formula(),
        Some("Lu1.8Y0.2SiO5:Ce")
    );
    assert_eq!(
        db.get("lyso.Ce.saint_gobain.prelude420").unwrap().formula(),
        None
    );
}

#[test]
fn min_max_becomes_nominal_and_half_range() {
    let table: toml::Table = toml::from_str(
        r#"
        [x]
        name = "X"
        [x.mechanical]
        density = { min = 2.0, max = 4.0 }
        "#,
    )
    .unwrap();
    let dir = std::env::temp_dir().join("rs_materials_minmax_test");
    std::fs::create_dir_all(&dir).unwrap();
    std::fs::write(dir.join("metals.toml"), toml::to_string(&table).unwrap()).unwrap();
    let db = MaterialDb::open(&dir).unwrap();
    let m = db.get("x").unwrap();
    assert_eq!(m.density(), Some(3.0));
    assert_eq!(m.mechanical().unwrap().stddev_of("density"), Some(1.0));
    std::fs::remove_dir_all(&dir).ok();
}

// ---------------------------------------------------------------------------
// Curves
// ---------------------------------------------------------------------------

#[test]
fn temperature_curves_are_parsed_and_clamp() {
    let table: toml::Table = toml::from_str(
        r#"
        [x]
        name = "X"
        [x.thermal]
        thermal_conductivity = 167.0
        thermal_conductivity_curve = { temps_K = [77, 293, 500], values = [105, 167, 192] }
        "#,
    )
    .unwrap();
    let dir = std::env::temp_dir().join("rs_materials_curve_test");
    std::fs::create_dir_all(&dir).unwrap();
    std::fs::write(dir.join("metals.toml"), toml::to_string(&table).unwrap()).unwrap();
    let db = MaterialDb::open(&dir).unwrap();
    let th = db.get("x").unwrap().thermal().unwrap();
    assert_eq!(th.thermal_conductivity_at(293.0), Some(167.0));
    assert_eq!(th.thermal_conductivity_at(10.0), Some(105.0)); // clamped
    assert_eq!(th.thermal_conductivity_at(9000.0), Some(192.0)); // clamped
    std::fs::remove_dir_all(&dir).ok();
}

#[test]
fn wavelength_curves_parse_every_on_disk_spelling() {
    let table: toml::Table = toml::from_str(
        r#"
        [x]
        name = "X"
        [x.optical]
        refractive_index_dispersion = { wavelengths_nm = [400, 500], n = [1.9, 1.8] }
        emission_spectrum = { wavelengths_nm = [400, 500], intensities = [0.5, 1.0] }
        absorption_length_spectrum = { wavelengths_nm = [400, 500], values = [10.0, 20.0] }
        "#,
    )
    .unwrap();
    let dir = std::env::temp_dir().join("rs_materials_wl_test");
    std::fs::create_dir_all(&dir).unwrap();
    std::fs::write(dir.join("metals.toml"), toml::to_string(&table).unwrap()).unwrap();
    let db = MaterialDb::open(&dir).unwrap();
    let opt = db.get("x").unwrap().optical().unwrap();
    assert_eq!(opt.n_at(450.0), Some(1.85));
    assert_eq!(opt.emission_at(450.0), Some(0.75));
    assert_eq!(opt.absorption_length_at(450.0), Some(15.0));
    // Dispersion beats the (absent) scalar, and the measured range is visible.
    let (lo, hi) = opt.refractive_index_dispersion.as_ref().unwrap().range();
    assert_eq!((lo, hi), (400.0, 500.0));
    std::fs::remove_dir_all(&dir).ok();
}

#[test]
fn decay_components_parse() {
    let table: toml::Table = toml::from_str(
        r#"
        [x]
        name = "X"
        [x.optical]
        decay_components = [{ tau_ns = 36.0, fraction = 0.9 }, { tau_ns = 600.0, fraction = 0.1 }]
        "#,
    )
    .unwrap();
    let dir = std::env::temp_dir().join("rs_materials_decay_test");
    std::fs::create_dir_all(&dir).unwrap();
    std::fs::write(dir.join("metals.toml"), toml::to_string(&table).unwrap()).unwrap();
    let db = MaterialDb::open(&dir).unwrap();
    let comps = &db.get("x").unwrap().optical().unwrap().decay_components;
    assert_eq!(comps.len(), 2);
    assert_eq!(comps[0].tau_ns, 36.0);
    assert_eq!(comps[1].fraction, 0.1);
    std::fs::remove_dir_all(&dir).ok();
}

// ---------------------------------------------------------------------------
// The raw() escape hatch — ADR-0004 §7
// ---------------------------------------------------------------------------

#[test]
fn raw_reaches_untyped_groups() {
    let db = db();
    let peek = db.get("peek").unwrap();
    let manufacturing = peek.raw().get("manufacturing").and_then(|v| v.as_table());
    assert!(
        manufacturing.is_some(),
        "raw() must reach groups this crate does not type"
    );
}

#[test]
fn raw_has_parent_fields_applied() {
    let db = db();
    let ce = db.get("lyso.Ce").unwrap();
    // `mechanical` is declared only on the parent.
    let density = ce
        .raw()
        .get("mechanical")
        .and_then(|m| m.as_table())
        .and_then(|m| m.get("density_value"))
        .and_then(|v| v.as_float());
    assert_eq!(density, Some(7.1));
}

// ---------------------------------------------------------------------------
// Surface catalogue
// ---------------------------------------------------------------------------

#[test]
fn surface_catalogue_loads_thirty_lut_entries() {
    let sdb = SurfaceDb::builtin();
    assert_eq!(sdb.family(rs_materials::LutFamily::Lbnl).len(), 21);
    assert_eq!(sdb.family(rs_materials::LutFamily::Davis).len(), 9);
}

#[test]
fn non_lut_entries_carry_a_reflector_instead_of_a_table() {
    // ADR-0004 §3: the test is measurement, not LUT-backing. These carry no
    // angular table; their measured content is the reflector's reflectance,
    // which lives on the material they name.
    let sdb = SurfaceDb::builtin();
    let non_lut: Vec<&rs_materials::Surface> =
        sdb.values().filter(|s| s.lut_family.is_none()).collect();
    assert_eq!(non_lut.len(), 2);
    for s in &non_lut {
        assert!(s.lut_surface.is_none(), "{}", s.key);
        assert!(s.reflector_material.is_some(), "{}", s.key);
    }

    let baso4 = sdb.get("diffuse.baso4_air").unwrap();
    assert_eq!(baso4.reflector_material.as_deref(), Some("baso4"));
    assert!(baso4.is_air_gap());

    // ...and the reflectance really is reachable on that material.
    let mdb = MaterialDb::builtin();
    let opt = mdb.get("baso4").unwrap().optical().unwrap();
    assert_eq!(opt.reflectivity, Some(99.9));
    let curve = opt.reflectivity_spectrum.as_ref().expect("BaSO4 spectrum");
    assert!((curve.interpolate(420.0) - 99.90).abs() < 0.01);
}

#[test]
fn readout_stack_indices_resolve() {
    // grease -> window. CS steps down (TIR at that boundary), PE steps up.
    let db = MaterialDb::builtin();
    let n = |k: &str| {
        db.get(k)
            .unwrap()
            .optical()
            .unwrap()
            .refractive_index
            .unwrap()
    };
    let grease = n("bc630");
    assert_eq!(grease, 1.465);
    assert!(n("sipm_window_silicone") < grease);
    assert!(n("sipm_window_epoxy") > grease);
}

#[test]
fn surface_lookup_by_key_and_prefix() {
    let sdb = SurfaceDb::builtin();
    let a = sdb.get("davis.polished_esr_grease").unwrap();
    let b = sdb.get("surface.davis.polished_esr_grease").unwrap();
    assert_eq!(a.key, b.key);
}

#[test]
fn surface_lookup_by_g4_finish_name() {
    let sdb = SurfaceDb::builtin();
    let s = sdb.by_lut_surface("PolishedESRGrease_LUT").unwrap();
    assert_eq!(s.key, "davis.polished_esr_grease");
    assert!(s.is_optical_contact());
    assert_eq!(s.coupling_index, Some(1.465));

    let lbnl = sdb.by_lut_surface("polishedvm2000glue").unwrap();
    assert_eq!(lbnl.coupling_index, Some(1.582));
    assert_eq!(lbnl.g4_surface_type.as_deref(), Some("dielectric_LUT"));
}

#[test]
fn air_gap_and_optical_contact_are_distinguishable() {
    let sdb = SurfaceDb::builtin();
    assert_eq!(sdb.with_coupling(rs_materials::Coupling::AirGap).len(), 21);
    assert_eq!(
        sdb.with_coupling(rs_materials::Coupling::OpticalContact)
            .len(),
        8
    );

    let air = sdb.by_lut_surface("polishedvm2000air").unwrap();
    let glue = sdb.by_lut_surface("polishedvm2000glue").unwrap();
    assert!(air.is_air_gap());
    assert!(!air.is_optical_contact());
    assert!(glue.is_optical_contact());
    assert_eq!(air.coupling_index, None);
    assert_eq!(air.reflector_material, glue.reflector_material);
}

#[test]
fn every_surface_carries_provenance() {
    let sdb = SurfaceDb::builtin();
    for s in sdb.values() {
        if s.lut_family.is_some() {
            assert!(s.source_of("lut_surface").is_some(), "{}", s.key);
            assert!(s.source_of("lut_family").is_some(), "{}", s.key);
        } else {
            // Non-LUT entries cite the reflector whose reflectance they use.
            assert!(s.source_of("reflector_material").is_some(), "{}", s.key);
        }
        if s.coupling_index.is_some() {
            assert!(s.source_of("coupling_index").is_some(), "{}", s.key);
        }
    }
}

#[test]
fn surface_absences_are_exposed() {
    let sdb = SurfaceDb::builtin();
    let s = sdb.get("davis.detector").unwrap();
    assert_eq!(s.coupling, None);
    assert_eq!(s.absent_reason("coupling").unwrap().reason, "not-measured");
}

#[test]
fn analytic_finishes_are_not_in_the_catalogue() {
    let sdb = SurfaceDb::builtin();
    for name in ["polished", "ground", "polishedbackpainted", "polishedair"] {
        assert!(
            sdb.by_lut_surface(name).is_none(),
            "{name} is not a measured surface and must not be catalogued"
        );
    }
}

#[test]
fn surface_material_refs_resolve_against_the_material_db() {
    let sdb = SurfaceDb::builtin();
    let mdb = db();
    for s in sdb.values() {
        if let Some(key) = &s.reflector_material {
            assert!(mdb.get(key).is_ok(), "{}: unknown reflector {key}", s.key);
        }
        if let Some(key) = &s.coupling_material {
            assert!(mdb.get(key).is_ok(), "{}: unknown coupling {key}", s.key);
        }
    }
}

#[test]
fn surface_db_is_send_sync() {
    fn assert_send_sync<T: Send + Sync>() {}
    assert_send_sync::<SurfaceDb>();
    assert_send_sync::<rs_materials::Surface>();
}

// ---------------------------------------------------------------------------
// Kubelka-Munk — the crosstalk channel
// ---------------------------------------------------------------------------

#[test]
fn kubelka_munk_reproduces_pattersons_published_reflectance() {
    let db = db();
    let opt = db.get("baso4").unwrap().optical().unwrap();
    for (wl, published) in [(300.0, 96.24), (500.0, 98.15), (700.0, 98.46)] {
        let got = opt.km_reflectance_infinite_at(wl).unwrap();
        assert!(
            (got - published).abs() < 0.01,
            "{wl} nm: {got} vs {published}"
        );
    }
}

#[test]
fn a_thin_septum_transmits_even_though_reflectance_has_converged() {
    // The finding that opened the crosstalk channel: "optically thick" for
    // reflectance does not mean opaque.
    let db = db();
    let opt = db.get("baso4").unwrap().optical().unwrap();
    let t02 = opt.km_transmittance_at(420.0, 0.02, 0.0).unwrap();
    assert!(t02 > 5.0, "0.2 mm septum transmits {t02}%, expected >5%");
    let t06 = opt.km_transmittance_at(420.0, 0.06, 0.0).unwrap();
    assert!(t06 < t02 && t06 > 1.0);
}

#[test]
fn the_two_baso4_reflectance_routes_disagree_and_that_is_recorded() {
    let db = db();
    let m = db.get("baso4").unwrap();
    let opt = m.optical().unwrap();
    let grum = opt.reflectivity_at(420.0).unwrap();
    let patterson = opt.km_reflectance_infinite_at(420.0).unwrap();
    assert!(grum > patterson);
    assert!((grum - 99.90).abs() < 0.01);
    assert!((patterson - 97.18).abs() < 0.05);
    let note = m
        .source_of("optical.kubelka_munk")
        .unwrap()
        .note
        .as_ref()
        .unwrap();
    assert!(note.contains("TWO-SOURCE DISAGREEMENT"));
}

#[test]
fn km_split_closes_and_matches_the_finite_reflectance() {
    let db = db();
    let opt = db.get("baso4").unwrap().optical().unwrap();
    for mm in [0.1_f64, 0.2, 0.5, 1.0] {
        let (r, t, a) = opt.km_split_at(420.0, mm / 10.0, 0.0, 0.0).unwrap();
        assert!((r + t + a - 100.0).abs() < 1e-9, "{mm} mm: {r}+{t}+{a}");
        assert!(r >= 0.0 && t >= 0.0 && a >= 0.0);
    }
    // A 0.2 mm septum reflects ~92%, well below the ~97% thick-layer limit.
    let r = opt.km_reflectance_at(420.0, 0.02, 0.0).unwrap();
    assert!((r - 91.9).abs() < 0.1, "R(0.2mm) = {r}");
    assert!(r < opt.km_reflectance_infinite_at(420.0).unwrap());
}

#[test]
fn a_long_enough_path_reaches_the_semi_infinite_limit() {
    // Pure mathematics of the accessor. 76.7 degrees is an ARBITRARY long-path
    // example, NOT a claim about any real geometry — an earlier version of this
    // test asserted it was the physical angle inside a wrapped crystal, and
    // that was retracted twice. A Lambertian septum randomises direction to a
    // mean of 48.2 degrees regardless of crystal shape; see
    // `a_thin_septum_is_not_optically_thick_at_realistic_angles`.
    let db = db();
    let opt = db.get("baso4").unwrap().optical().unwrap();
    let r_normal = opt.km_reflectance_at(420.0, 0.02, 0.0).unwrap();
    let r_grazing = opt.km_reflectance_at(420.0, 0.02, 76.7).unwrap();
    let r_inf = opt.km_reflectance_infinite_at(420.0).unwrap();
    assert!((r_normal - 91.9).abs() < 0.1, "normal: {r_normal}");
    assert!((r_grazing - 96.9).abs() < 0.1, "grazing: {r_grazing}");
    assert!(r_inf - r_grazing < 0.5);
    assert!(r_inf - r_normal > 5.0);

    let t_grazing = opt.km_transmittance_at(420.0, 0.02, 76.7).unwrap();
    assert!(
        (t_grazing - 1.35).abs() < 0.05,
        "T at 76.7 deg: {t_grazing}"
    );
}

#[test]
fn obliquity_by_angle_equals_obliquity_by_thickness() {
    let db = db();
    let opt = db.get("baso4").unwrap().optical().unwrap();
    // 1/cos(60 deg) = 2, so 0.02 cm at 60 deg == 0.04 cm at normal.
    let by_angle = opt.km_split_at(420.0, 0.02, 0.0, 60.0).unwrap();
    let by_thickness = opt.km_split_at(420.0, 0.04, 0.0, 0.0).unwrap();
    assert!((by_angle.0 - by_thickness.0).abs() < 1e-9);
    assert!((by_angle.1 - by_thickness.1).abs() < 1e-9);
}

#[test]
fn a_thin_septum_is_not_optically_thick_at_realistic_angles() {
    // A diffuse reflector erases the angular distribution it is given: after
    // one Lambertian contact the mean is <|cos|> = 2/3, i.e. 48.2 degrees, with
    // no dependence on crystal aspect ratio. At that angle a 0.2 mm septum
    // still transmits ~5%.
    let db = db();
    let opt = db.get("baso4").unwrap().optical().unwrap();
    let t_real = opt.km_transmittance_at(420.0, 0.02, 48.19).unwrap();
    let t_normal = opt.km_transmittance_at(420.0, 0.02, 0.0).unwrap();
    assert!((t_real - 5.1).abs() < 0.1, "T at Lambertian mean: {t_real}");
    assert!((t_normal - 7.6).abs() < 0.1, "T at normal: {t_normal}");

    let r_inf = opt.km_reflectance_infinite_at(420.0).unwrap();
    let r_real = opt.km_reflectance_at(420.0, 0.02, 48.19).unwrap();
    assert!(
        r_inf - r_real > 2.5,
        "still far from the semi-infinite limit"
    );
}

#[test]
fn obliquity_factor_matches_one_over_cos() {
    use rs_materials::material::obliquity_factor;
    assert!((obliquity_factor(0.0) - 1.0).abs() < 1e-12);
    assert!((obliquity_factor(60.0) - 2.0).abs() < 1e-12);
    // Lambertian mean angle -> 1.5, which is 1/<cos>. Note this is NOT the
    // mean path multiplier: <1/cos> = 2 for the same distribution.
    assert!((obliquity_factor(48.19) - 1.5).abs() < 1e-3);
    assert_eq!(obliquity_factor(90.0), 40.0);
}
