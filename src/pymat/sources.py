"""Provenance metadata for material property values (#150).

A `Source` records *where a value came from*, keyed by dotted property path
on `Material._sources` (e.g. `"mechanical.density"`). Provenance is metadata
*about* a value, not part of it — `mat.density` stays a `float`. See ADR-0003.

Allowed `license` values are not enforced here; they're enforced by the
`scripts/check_licenses.py` CI gate added in #174.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

# Short attribute aliases → fully-qualified property paths. When a caller
# writes `mat.cite("density")` we look up `mechanical.density`. Only one
# alias per property — when a name is ambiguous (e.g. "transparency"
# could be optical or visual), require the qualified form.
SHORT_ALIASES: dict[str, str] = {
    "density": "mechanical.density",
    "youngs_modulus": "mechanical.youngs_modulus",
    "yield_strength": "mechanical.yield_strength",
    "tensile_strength": "mechanical.tensile_strength",
    "shear_modulus": "mechanical.shear_modulus",
    "poissons_ratio": "mechanical.poissons_ratio",
    "thermal_conductivity": "thermal.thermal_conductivity",
    "specific_heat": "thermal.specific_heat",
    "thermal_expansion": "thermal.thermal_expansion",
    "melting_point": "thermal.melting_point",
    "resistivity": "electrical.resistivity",
    "conductivity": "electrical.conductivity",
    "refractive_index": "optical.refractive_index",
    "light_yield": "optical.light_yield",
    "decay_time": "optical.decay_time",
    # #157 moved radiation_length to NuclearProperties but this alias kept
    # pointing at `optical.` — so `mat.cite("radiation_length")` silently
    # resolved to a path no TOML writes, and fell through to `_default`.
    # Fixed in #243; the qualified form `nuclear.radiation_length` was
    # always correct and is unaffected.
    "radiation_length": "nuclear.radiation_length",
    "interaction_length": "nuclear.interaction_length",
    "moliere_radius": "nuclear.moliere_radius",
    "reflectivity": "optical.reflectivity",
    "absorption_length": "optical.absorption_length",
    "emission_spectrum": "optical.emission_spectrum",
    "emission_peak": "optical.emission_peak",
    "decay_components": "optical.decay_components",
}


@dataclass(frozen=True)
class Source:
    """Provenance for a single property value.

    Attributes:
        citation: Short BibTeX-style key (e.g. `"asm_handbook_v2"`).
        kind: One of `"doi"`, `"qid"`, `"handbook"`, `"vendor"`, `"measured"`.
        ref: The actual reference — DOI string, Wikidata QID, handbook
            citation, vendor URL, or in-house measurement record.
        license: One of `CC0`, `PD-USGov`, `CC-BY-4.0`, `CC-BY-SA-4.0`,
            `proprietary-reference-only`, `unknown`. Validated by
            `scripts/check_licenses.py` (#174).
        note: Optional human-readable note (e.g. measurement conditions).
    """

    citation: str
    kind: str
    ref: str
    license: str
    note: Optional[str] = None

    @classmethod
    def from_toml(cls, data: dict[str, Any]) -> "Source":
        """Build a Source from a TOML inline-table dict.

        Raises:
            ValueError: if any required key is missing.
        """
        missing = [k for k in ("citation", "kind", "ref", "license") if k not in data]
        if missing:
            raise ValueError(f"Source missing required keys: {missing}")
        return cls(
            citation=data["citation"],
            kind=data["kind"],
            ref=data["ref"],
            license=data["license"],
            note=data.get("note"),
        )

    def to_bibtex(self) -> str:
        """Emit a BibTeX `@misc` entry. Deterministic — same input, same output."""
        fields = [f"  citation = {{{self.citation}}}"]
        if self.kind == "doi":
            fields.append(f"  doi = {{{self.ref}}}")
        elif self.kind == "qid":
            fields.append(f"  url = {{https://www.wikidata.org/wiki/{self.ref}}}")
            fields.append(f"  note = {{Wikidata {self.ref}}}")
        elif self.kind == "vendor":
            fields.append(f"  url = {{{self.ref}}}")
        else:
            fields.append(f"  howpublished = {{{self.ref}}}")
        if self.note:
            fields.append(f"  annotation = {{{self.note}}}")
        return "@misc{" + self.citation + ",\n" + ",\n".join(fields) + "\n}"


# Why a value is missing. Deliberately a closed set — the whole point of a
# declared absence is that it can be audited, and a free-text reason cannot
# be counted. Extend the set in a PR, not in a data file.
ABSENT_REASONS: frozenset[str] = frozenset(
    {
        # Nobody has measured it (for this material, to our knowledge).
        "not-measured",
        # The property is meaningless here (e.g. `hygroscopic` for a gas).
        "not-applicable",
        # The quantity exists but cannot be decomposed the way the schema
        # asks — e.g. a lumped attenuation length that no published work
        # splits into matrix-loss and self-absorption channels.
        "not-separable",
        # Measured, but the only source forbids redistribution.
        "proprietary",
        # We intend to populate it; tracked elsewhere. Use `note` for the ref.
        "pending",
    }
)


@dataclass(frozen=True)
class Absent:
    """A declared absence for a property path (#243, ADR-0004 §6).

    The negative twin of `Source`. `None` on a property means "no value
    here" and cannot distinguish *nobody looked* from *we looked and the
    number does not exist* — but those two facts make a downstream engine
    behave very differently. A declared absence makes the second case
    visible and greppable.

    Attributes:
        reason: One of `ABSENT_REASONS`. Validated at load.
        note: Human-readable detail — what was searched, what was found
            instead, which issue tracks it.
    """

    reason: str
    note: Optional[str] = None

    @classmethod
    def from_toml(cls, path: str, data: dict[str, Any]) -> "Absent":
        """Build from a TOML inline-table. Raises on an unknown reason."""
        if "reason" not in data:
            raise ValueError(f"_absent entry {path!r} missing required key 'reason'")
        reason = data["reason"]
        if reason not in ABSENT_REASONS:
            allowed = ", ".join(sorted(ABSENT_REASONS))
            raise ValueError(
                f"_absent entry {path!r} has unknown reason {reason!r}; allowed: {allowed}"
            )
        return cls(reason=reason, note=data.get("note"))


def parse_absent_table(raw: dict[str, Any]) -> dict[str, "Absent"]:
    """Parse a `[<material>._absent]` TOML table into `{path: Absent}`."""
    out: dict[str, Absent] = {}
    for key, val in raw.items():
        if not isinstance(val, dict):
            kind = type(val).__name__
            raise ValueError(f"_absent entry {key!r} must be an inline table, got {kind}")
        out[key] = Absent.from_toml(key, val)
    return out


def resolve_path(path: str) -> str:
    """Expand a short alias (`"density"`) to its fully-qualified path
    (`"mechanical.density"`). Pass-through if already qualified or unknown."""
    if "." in path:
        return path
    return SHORT_ALIASES.get(path, path)


def parse_sources_table(raw: dict[str, Any]) -> dict[str, Source]:
    """Parse a `[<material>._sources]` TOML table into `{path: Source}`.

    The table may include `_default` plus one entry per dotted property
    path. All values must be inline tables with the required Source keys.
    """
    out: dict[str, Source] = {}
    for key, val in raw.items():
        if not isinstance(val, dict):
            kind = type(val).__name__
            raise ValueError(f"_sources entry {key!r} must be an inline table, got {kind}")
        out[key] = Source.from_toml(val)
    return out


def merge_sources(parent: dict[str, Source], child: dict[str, Source]) -> dict[str, Source]:
    """Overlay child sources on parent (child wins on key collision)."""
    return {**parent, **child}
