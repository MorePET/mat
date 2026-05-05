"""Temperature-dependent property curves (#148).

A `TempCurve` holds piecewise-linear `(temps_K, values)` knots for a
single property. Out-of-range temps are CLAMPED, not extrapolated —
engineering data extrapolated below its measured range is a lie, and
clamping is conservative and visibly wrong rather than subtly wrong
(per ADR-0003 §2 edge-case table).

Validation is at construction (and therefore at TOML load) — unsorted
or mismatched-length arrays raise `ValueError` immediately, not at
query time. Empty curves raise as well.

Used by sibling fields like `<prop>_curve: Optional[TempCurve]` on
the property dataclasses.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, List

logger = logging.getLogger(__name__)


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
        if not self.temps_K:
            raise ValueError("TempCurve requires at least one knot")
        if len(self.temps_K) != len(self.values):
            raise ValueError(
                f"TempCurve temps_K and values must be same length: "
                f"{len(self.temps_K)} vs {len(self.values)}"
            )
        # Strict-sorted check (ascending). Equal-adjacent knots would make
        # interpolation ambiguous; reject.
        for a, b in zip(self.temps_K, self.temps_K[1:]):
            if not a < b:
                raise ValueError(
                    f"TempCurve temps_K must be strictly sorted ascending; got {self.temps_K}"
                )

    def interpolate(self, temp_K: float) -> float:
        """Evaluate the curve at `temp_K`. Out-of-range clamps to nearest knot."""
        if temp_K <= self.temps_K[0]:
            if temp_K < self.temps_K[0]:
                logger.debug(
                    "TempCurve: T=%s K below min knot %s K; clamping",
                    temp_K,
                    self.temps_K[0],
                )
            return self.values[0]
        if temp_K >= self.temps_K[-1]:
            if temp_K > self.temps_K[-1]:
                logger.debug(
                    "TempCurve: T=%s K above max knot %s K; clamping",
                    temp_K,
                    self.temps_K[-1],
                )
            return self.values[-1]
        # Linear interp between bracketing knots
        for i in range(len(self.temps_K) - 1):
            t0, t1 = self.temps_K[i], self.temps_K[i + 1]
            if t0 <= temp_K <= t1:
                v0, v1 = self.values[i], self.values[i + 1]
                frac = (temp_K - t0) / (t1 - t0)
                return v0 + frac * (v1 - v0)
        # Unreachable — clamp branches above cover all cases
        raise RuntimeError(f"TempCurve: failed to bracket T={temp_K}")  # pragma: no cover

    @classmethod
    def from_toml(cls, raw: Any) -> "TempCurve":
        """Build from `{temps_K = [...], values = [...]}` TOML inline-table."""
        if not isinstance(raw, dict):
            raise ValueError(f"TempCurve TOML must be a table, got {type(raw).__name__}")
        if "temps_K" not in raw or "values" not in raw:
            raise ValueError(f"TempCurve TOML missing 'temps_K' or 'values': {raw}")
        return cls(temps_K=list(raw["temps_K"]), values=list(raw["values"]))
