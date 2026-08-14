//! Piecewise-linear property curves — the Rust mirror of `pymat.curves`.
//!
//! One type covers both axes. On the Python side `TempCurve` and
//! `WavelengthCurve` are distinct so that `_at(T)` and `n_at(lambda)` cannot be
//! confused at a call site; here the axis is fixed by the field the curve hangs
//! off, so a single `Curve` with a documented abscissa unit is enough.
//!
//! **Out-of-range abscissae are CLAMPED, not extrapolated.** This mirrors
//! ADR-0003 §2 / ADR-0004 §4: data extrapolated past its measured range is a
//! lie, and clamping is conservative and visibly wrong rather than subtly
//! wrong. Use [`Curve::range`] to find out where the measurement actually
//! stops — a resampler that silently clamps a 128-node grid onto a curve
//! measured over 60 nm has fabricated the other 68 nodes.

/// A piecewise-linear curve over a strictly-ascending abscissa.
///
/// `xs` is Kelvin for temperature curves and nanometres for wavelength curves.
#[derive(Debug, Clone, PartialEq)]
pub struct Curve {
    xs: Vec<f64>,
    ys: Vec<f64>,
}

impl Curve {
    /// Build a curve, validating the knots.
    ///
    /// Returns `None` when the knots are empty, length-mismatched, or not
    /// strictly ascending — the same three conditions that raise `ValueError`
    /// at load time on the Python side.
    pub fn new(xs: Vec<f64>, ys: Vec<f64>) -> Option<Self> {
        if xs.is_empty() || xs.len() != ys.len() {
            return None;
        }
        // `partial_cmp` rather than `>=` so NaN is rejected too: `a >= b` is
        // false for NaN, which would let a NaN knot through validation.
        if xs
            .windows(2)
            .any(|w| !matches!(w[0].partial_cmp(&w[1]), Some(std::cmp::Ordering::Less)))
        {
            return None;
        }
        Some(Self { xs, ys })
    }

    /// Evaluate at `x`. Outside the knot range this CLAMPS to the nearest knot.
    pub fn interpolate(&self, x: f64) -> f64 {
        if x <= self.xs[0] {
            return self.ys[0];
        }
        if x >= self.xs[self.xs.len() - 1] {
            return self.ys[self.ys.len() - 1];
        }
        // Knots are strictly ascending, so partition_point gives the first
        // index with xs[i] > x; the bracketing pair is (i-1, i).
        let i = self.xs.partition_point(|&k| k <= x);
        let (x0, x1) = (self.xs[i - 1], self.xs[i]);
        let (y0, y1) = (self.ys[i - 1], self.ys[i]);
        y0 + (x - x0) / (x1 - x0) * (y1 - y0)
    }

    /// `(min, max)` of the measured abscissa — the span outside which
    /// [`Curve::interpolate`] clamps.
    pub fn range(&self) -> (f64, f64) {
        (self.xs[0], self.xs[self.xs.len() - 1])
    }

    /// True when `x` falls inside the measured range (i.e. the result of
    /// `interpolate(x)` is interpolated rather than clamped).
    pub fn covers(&self, x: f64) -> bool {
        let (lo, hi) = self.range();
        (lo..=hi).contains(&x)
    }

    /// The knot abscissae.
    pub fn xs(&self) -> &[f64] {
        &self.xs
    }

    /// The knot ordinates.
    pub fn ys(&self) -> &[f64] {
        &self.ys
    }

    /// Number of knots.
    pub fn len(&self) -> usize {
        self.xs.len()
    }

    /// Always false — a `Curve` cannot be constructed empty.
    pub fn is_empty(&self) -> bool {
        false
    }

    /// Resample onto a uniform grid of `n` points spanning `lo..=hi`.
    ///
    /// Convenience for downstream flattening (strata resamples every spectrum
    /// onto a shared lambda grid). Values outside the measured range are
    /// clamped — check [`Curve::covers`] first if that matters.
    pub fn resample(&self, lo: f64, hi: f64, n: usize) -> Vec<f64> {
        if n == 0 {
            return Vec::new();
        }
        if n == 1 {
            return vec![self.interpolate(lo)];
        }
        let step = (hi - lo) / (n - 1) as f64;
        (0..n)
            .map(|i| self.interpolate(lo + step * i as f64))
            .collect()
    }

    /// Parse from a TOML table of the form `{ <x_key> = [...], <y_key> = [...] }`.
    pub fn from_toml(table: &toml::Table, x_key: &str, y_key: &str) -> Option<Self> {
        let xs = float_array(table.get(x_key)?)?;
        let ys = float_array(table.get(y_key)?)?;
        Self::new(xs, ys)
    }

    /// Parse a wavelength curve, accepting every value-column spelling used
    /// on disk: `values`, `n` (dispersion), `intensities` (emission spectra).
    pub fn from_wavelength_toml(table: &toml::Table) -> Option<Self> {
        for y_key in ["values", "n", "intensities"] {
            if table.contains_key(y_key) {
                return Self::from_toml(table, "wavelengths_nm", y_key);
            }
        }
        None
    }

    /// Parse a temperature curve (`{ temps_K = [...], values = [...] }`).
    pub fn from_temp_toml(table: &toml::Table) -> Option<Self> {
        Self::from_toml(table, "temps_K", "values")
    }
}

/// Coerce a TOML array of numbers (ints or floats) to `Vec<f64>`.
pub(crate) fn float_array(value: &toml::Value) -> Option<Vec<f64>> {
    value
        .as_array()?
        .iter()
        .map(|v| v.as_float().or_else(|| v.as_integer().map(|i| i as f64)))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn interpolates_between_knots() {
        let c = Curve::new(vec![400.0, 500.0], vec![1.0, 2.0]).unwrap();
        assert!((c.interpolate(450.0) - 1.5).abs() < 1e-12);
    }

    #[test]
    fn returns_exact_knot_values() {
        let c = Curve::new(vec![400.0, 500.0, 600.0], vec![1.0, 2.0, 3.0]).unwrap();
        assert_eq!(c.interpolate(400.0), 1.0);
        assert_eq!(c.interpolate(500.0), 2.0);
        assert_eq!(c.interpolate(600.0), 3.0);
    }

    #[test]
    fn clamps_outside_range() {
        let c = Curve::new(vec![400.0, 500.0], vec![1.8, 1.7]).unwrap();
        assert_eq!(c.interpolate(100.0), 1.8);
        assert_eq!(c.interpolate(900.0), 1.7);
    }

    #[test]
    fn single_knot_is_constant() {
        let c = Curve::new(vec![420.0], vec![1.82]).unwrap();
        assert_eq!(c.interpolate(1.0), 1.82);
        assert_eq!(c.interpolate(420.0), 1.82);
        assert_eq!(c.interpolate(9000.0), 1.82);
    }

    #[test]
    fn rejects_invalid_knots() {
        assert!(Curve::new(vec![], vec![]).is_none());
        assert!(Curve::new(vec![1.0, 2.0], vec![1.0]).is_none());
        assert!(Curve::new(vec![2.0, 1.0], vec![1.0, 2.0]).is_none());
        // Equal adjacent knots make interpolation ambiguous.
        assert!(Curve::new(vec![1.0, 1.0], vec![1.0, 2.0]).is_none());
    }

    #[test]
    fn range_and_covers() {
        let c = Curve::new(vec![400.0, 600.0], vec![1.0, 2.0]).unwrap();
        assert_eq!(c.range(), (400.0, 600.0));
        assert!(c.covers(500.0));
        assert!(!c.covers(300.0));
        assert!(!c.covers(700.0));
    }

    #[test]
    fn resample_hits_endpoints() {
        let c = Curve::new(vec![0.0, 10.0], vec![0.0, 10.0]).unwrap();
        let g = c.resample(0.0, 10.0, 11);
        assert_eq!(g.len(), 11);
        assert_eq!(g[0], 0.0);
        assert_eq!(g[10], 10.0);
        assert!((g[5] - 5.0).abs() < 1e-12);
    }

    #[test]
    fn many_knots_bracket_correctly() {
        let xs: Vec<f64> = (0..100).map(|i| i as f64).collect();
        let ys: Vec<f64> = (0..100).map(|i| (i * 2) as f64).collect();
        let c = Curve::new(xs, ys).unwrap();
        assert!((c.interpolate(50.5) - 101.0).abs() < 1e-12);
        assert!((c.interpolate(0.5) - 1.0).abs() < 1e-12);
        assert!((c.interpolate(98.5) - 197.0).abs() < 1e-12);
    }
}
