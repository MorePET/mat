//! Dump every material's resolved fields, one line each, for cross-checking
//! against the Python loader.
//!
//! This exists so that `tests/test_rs_python_parity.py` can prove the two
//! loaders resolve the same TOML to the same values. The two sides drifting
//! apart — the Rust crate silently lagging the Python schema — is the failure
//! this repo has already been bitten by (#157, and again in the strata brief of
//! 2026-08-14), so it is worth a gate rather than a convention.
//!
//! Output is intentionally dumb and line-oriented: `key|field=value|...`, with
//! values rendered via `{:?}` so `None` and `Some(x)` are unambiguous.
//!
//!     cargo run --example dump_parity

fn main() {
    let db = rs_materials::MaterialDb::builtin();
    let mut keys: Vec<&str> = db.keys().collect();
    keys.sort_unstable();

    for key in keys {
        let m = db.get(key).expect("key came from the db");
        let o = m.optical();
        let n = m.nuclear();
        let t = m.thermal();
        println!(
            "{key}|name={}|formula={:?}|density={:?}|grade={:?}|temper={:?}|treatment={:?}\
             |vendor={:?}|n={:?}|ly={:?}|dt={:?}|rt={:?}|ep={:?}|refl={:?}|transp={:?}\
             |abs={:?}|reabs={:?}|matrix={:?}|reemit={:?}|dopant={:?}|dopant_pct={:?}\
             |hygro={:?}|radlen={:?}|intlen={:?}|activity={:?}|melt={:?}|tc={:?}|tags={}",
            m.name,
            m.formula,
            m.density,
            m.grade,
            None::<String>, // temper is not yet typed on the Rust side
            m.treatment,
            m.vendor,
            o.and_then(|x| x.refractive_index),
            o.and_then(|x| x.light_yield),
            o.and_then(|x| x.decay_time),
            o.and_then(|x| x.rise_time),
            o.and_then(|x| x.emission_peak),
            o.and_then(|x| x.reflectivity),
            o.and_then(|x| x.transparency),
            o.and_then(|x| x.absorption_length),
            o.and_then(|x| x.absorption_length_reabs),
            o.and_then(|x| x.absorption_length_matrix),
            o.and_then(|x| x.reemit_qe),
            o.and_then(|x| x.dopant.clone()),
            o.and_then(|x| x.dopant_pct),
            o.and_then(|x| x.hygroscopic),
            n.and_then(|x| x.radiation_length),
            n.and_then(|x| x.interaction_length),
            n.and_then(|x| x.intrinsic_activity_bq_per_g),
            t.and_then(|x| x.melting_point),
            t.and_then(|x| x.thermal_conductivity),
            m.tags.join(","),
        );
    }
}
