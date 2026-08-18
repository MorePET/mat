"""Piecewise-linear property curves.

Two flavours, one interpolation rule:

- `TempCurve` — temperature-dependent properties (#148). Knots are
  `(temps_K, values)`.
- `WavelengthCurve` — wavelength-dependent optical properties (#243).
  Knots are `(wavelengths_nm, values)`.

Out-of-range abscissae are CLAMPED, not extrapolated — engineering data
extrapolated beyond its measured range is a lie, and clamping is
conservative and visibly wrong rather than subtly wrong (per ADR-0003 §2
edge-case table). ADR-0004 §4 extends the same rule to wavelength: a
dispersion table measured over 400-700 nm says nothing about 250 nm, and
a Sellmeier fit evaluated outside its stated validity range is worse than
useless because it looks like data.

Validation is at construction (and therefore at TOML load) — unsorted or
mismatched-length arrays raise `ValueError` immediately, not at query
time. Empty curves raise as well.

Used by sibling fields like `<prop>_curve: Optional[TempCurve]` and by
the wavelength accessors (`n_at`, `absorption_length_at`, `emission_at`)
on `OpticalProperties`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)


def _validate_knots(xs: Sequence[float], ys: Sequence[float], cls: str, x_name: str) -> None:
    """Shared knot validation for every piecewise-linear curve.

    Raises `ValueError` on empty, length-mismatched, or non-strictly-ascending
    abscissae. Equal-adjacent knots make interpolation ambiguous; reject them.
    """
    if not xs:
        raise ValueError(f"{cls} requires at least one knot")
    if len(xs) != len(ys):
        raise ValueError(f"{cls} {x_name} and values must be same length: {len(xs)} vs {len(ys)}")
    for a, b in zip(xs, xs[1:]):
        if not a < b:
            raise ValueError(f"{cls} {x_name} must be strictly sorted ascending; got {list(xs)}")


def _interp_clamped(
    xs: Sequence[float], ys: Sequence[float], x: float, cls: str, x_name: str, unit: str
) -> float:
    """Evaluate a piecewise-linear curve at `x`, clamping outside the knot range."""
    if x <= xs[0]:
        if x < xs[0]:
            logger.debug(
                "%s: %s=%s %s below min knot %s %s; clamping", cls, x_name, x, unit, xs[0], unit
            )
        return ys[0]
    if x >= xs[-1]:
        if x > xs[-1]:
            logger.debug(
                "%s: %s=%s %s above max knot %s %s; clamping", cls, x_name, x, unit, xs[-1], unit
            )
        return ys[-1]
    for i in range(len(xs) - 1):
        x0, x1 = xs[i], xs[i + 1]
        if x0 <= x <= x1:
            y0, y1 = ys[i], ys[i + 1]
            return y0 + (x - x0) / (x1 - x0) * (y1 - y0)
    # Unreachable — the clamp branches above cover every case.
    raise RuntimeError(f"{cls}: failed to bracket {x_name}={x}")  # pragma: no cover


def _require_table(raw: Any, cls: str) -> dict:
    if not isinstance(raw, dict):
        raise ValueError(f"{cls} TOML must be a table, got {type(raw).__name__}")
    return raw


@dataclass(frozen=True)
class TempCurve:
    """Piecewise-linear temperature-dependent property curve.

    Attributes:
        temps_K: Strictly-sorted ascending temperatures in Kelvin.
        values: Property values at each knot, same length as `temps_K`.
    """

    temps_K: List[float]
    values: List[float]

    def __post_init__(self) -> None:
        _validate_knots(self.temps_K, self.values, "TempCurve", "temps_K")

    def interpolate(self, temp_K: float) -> float:
        """Evaluate the curve at `temp_K`. Out-of-range clamps to nearest knot."""
        return _interp_clamped(self.temps_K, self.values, temp_K, "TempCurve", "T", "K")

    @classmethod
    def from_toml(cls, raw: Any) -> "TempCurve":
        """Build from `{temps_K = [...], values = [...]}` TOML inline-table."""
        raw = _require_table(raw, "TempCurve")
        if "temps_K" not in raw or "values" not in raw:
            raise ValueError(f"TempCurve TOML missing 'temps_K' or 'values': {raw}")
        return cls(temps_K=list(raw["temps_K"]), values=list(raw["values"]))


# Value-column spellings accepted by `WavelengthCurve.from_toml` when no
# explicit `value_key` is given, in priority order. The non-canonical ones
# exist because the structured optical slots shipped in #153 / #164 before
# this primitive did, and their on-disk shape is load-bearing:
#   refractive_index_dispersion = {wavelengths_nm = [...], n = [...]}
#   emission_spectrum           = {wavelengths_nm = [...], intensities = [...]}
_WL_VALUE_KEYS: Tuple[str, ...] = ("values", "n", "intensities")


@dataclass(frozen=True)
class WavelengthCurve:
    """Piecewise-linear wavelength-dependent optical property curve (#243).

    The wavelength twin of `TempCurve`. Same clamping contract, same
    load-time validation. Wavelengths are always nanometres — the schema
    spells the abscissa `wavelengths_nm` everywhere, so there is no unit
    ambiguity to resolve at load.

    Attributes:
        wavelengths_nm: Strictly-sorted ascending wavelengths in nm.
        values: Property values at each knot, same length as `wavelengths_nm`.
    """

    wavelengths_nm: List[float]
    values: List[float]

    def __post_init__(self) -> None:
        _validate_knots(self.wavelengths_nm, self.values, "WavelengthCurve", "wavelengths_nm")

    def interpolate(self, wavelength_nm: float) -> float:
        """Evaluate at `wavelength_nm`. Out-of-range clamps to nearest knot."""
        return _interp_clamped(
            self.wavelengths_nm, self.values, wavelength_nm, "WavelengthCurve", "lambda", "nm"
        )

    @property
    def range_nm(self) -> Tuple[float, float]:
        """`(min, max)` of the measured range — the span outside which
        `interpolate` clamps. Downstream resamplers (e.g. strata's parquet
        emitter) use this to record where the data actually stops."""
        return (self.wavelengths_nm[0], self.wavelengths_nm[-1])

    @classmethod
    def from_toml(cls, raw: Any, value_key: Optional[str] = None) -> "WavelengthCurve":
        """Build from a `{wavelengths_nm = [...], <values> = [...]}` table.

        Args:
            raw: The TOML inline-table.
            value_key: Explicit name of the ordinate column. When omitted,
                the first of `values` / `n` / `intensities` present in the
                table wins. Two or more present at once is a hard error —
                silently picking one would make the file's meaning depend
                on this function's internals.
        """
        raw = _require_table(raw, "WavelengthCurve")
        if "wavelengths_nm" not in raw:
            raise ValueError(f"WavelengthCurve TOML missing 'wavelengths_nm': {raw}")

        if value_key is not None:
            if value_key not in raw:
                raise ValueError(f"WavelengthCurve TOML missing {value_key!r}: {raw}")
            key = value_key
        else:
            present = [k for k in _WL_VALUE_KEYS if k in raw]
            if not present:
                accepted = ", ".join(repr(k) for k in _WL_VALUE_KEYS)
                raise ValueError(
                    f"WavelengthCurve TOML has no value column (accepted: {accepted}): {raw}"
                )
            if len(present) > 1:
                raise ValueError(
                    f"WavelengthCurve TOML is ambiguous — multiple value columns "
                    f"{present}; pass value_key explicitly: {raw}"
                )
            key = present[0]

        return cls(wavelengths_nm=list(raw["wavelengths_nm"]), values=list(raw[key]))
