"""Measured optical surface finishes — the interface catalogue (#243).

A `Surface` is **not** a `Material`. A material is a substance; a surface is a
*measured interface between substances* — a crystal face with a given
treatment, a reflector, and whatever fills the gap between them. It has no
density, no formula, and no mass, so modelling it as a `Material` would put
objects into `pymat.materials`, `search()`, and `mass_from_volume_mm3()` for
which those operations are meaningless. See ADR-0004 §2.

What it shares with materials is everything that is about *values* rather than
about substances: `Source` provenance, `Absent` declarations, `WavelengthCurve`
spectra, and parent-overlay inheritance.

## Scope — measured interfaces only

The catalogue holds the 30 measured surfaces shipped in the Geant4
`G4RealSurface` 2.2 data set: 21 LBNL LUTs (Janecek & Moses 2010) and 9 DAVIS
LUTs (Roncali & Cherry 2013). It deliberately does **not** hold Geant4's six
analytic UNIFIED/GLISUR finishes (`polished`, `ground`,
`polishedfrontpainted`, …). Those carry no measured data and no citation — they
are model selections parameterised by `sigma_alpha`, and a model selection is a
run-time policy choice belonging to the consuming engine (ADR-0004 §3).

Nor does it hold *assignments*. Which face of which crystal carries which
finish is a fact about a detector somebody built, not about matter.

## Usage

    from pymat import surfaces

    s = surfaces["davis.polished_esr_grease"]
    s.lut_surface          # 'PolishedESRGrease_LUT' — exact G4 enum spelling
    s.coupling             # 'optical_contact'
    s.coupling_index       # 1.465 (BC-630 silicone grease)
    s.cite()               # BibTeX for every source behind this entry

    surfaces(lut_family="davis")           # -> list[Surface]
    surfaces(coupling="air_gap")           # -> list[Surface]
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, overload

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover — Python 3.10 path
    import tomli as tomllib

from .curves import WavelengthCurve
from .sources import Absent, Source, merge_sources, parse_absent_table, parse_sources_table

logger = logging.getLogger(__name__)

__all__ = ["Surface", "surfaces", "load_surfaces"]

# ---------------------------------------------------------------------------
# Closed vocabularies. Validated at load — a typo in a data file is a hard
# error, not a value that quietly fails every downstream comparison.
# ---------------------------------------------------------------------------

#: How the interface reflects. `lut` means a measured angular-reflectance
#: look-up table; `specular` and `diffuse` are for cited scalar/spectral
#: reflectors that have no LUT.
MODELS = frozenset({"lut", "specular", "diffuse"})

#: Which measured LUT family the entry comes from.
LUT_FAMILIES = frozenset({"lbnl", "davis"})

#: What fills the gap between crystal face and reflector. This is the
#: distinction the brief calls out as physically load-bearing and currently
#: inexpressible: an air gap means the photon meets a crystal→air Fresnel step
#: first (large index contrast, small critical angle, strong TIR light-piping —
#: the mechanism DOI designs exploit), while optical contact means it meets the
#: coupling polymer directly.
COUPLINGS = frozenset({"air_gap", "optical_contact", "none"})

#: Crystal-face preparation the surface was measured against.
TREATMENTS = frozenset({"polished", "etched", "ground", "rough"})


@dataclass(frozen=True)
class Surface:
    """One measured optical interface.

    Every field except `key`/`name` is optional — the catalogue records what
    was measured, and an entry that lacks a number should say so via `_absent`
    rather than carry a plausible default.
    """

    key: str
    name: str

    # --- behaviour -------------------------------------------------------
    model: Optional[str] = None  # one of MODELS
    treatment: Optional[str] = None  # one of TREATMENTS

    # --- measured-LUT identity ------------------------------------------
    lut_family: Optional[str] = None  # one of LUT_FAMILIES
    #: The exact `G4OpticalSurfaceFinish` enum spelling, verbatim. This is the
    #: string a consumer matches on to find the right `.dat` file, so it is
    #: transcribed from the Geant4 header rather than normalised — hence the
    #: inconsistent casing across families (`polishedvm2000glue` for LBNL,
    #: `PolishedESRGrease_LUT` for DAVIS). Do not "fix" it.
    lut_surface: Optional[str] = None
    #: The exact `G4SurfaceType` the finish is valid with.
    g4_surface_type: Optional[str] = None
    #: Which data-set release the LUT ships in.
    lut_dataset: Optional[str] = None

    # --- the two substances being joined ---------------------------------
    #: Human label for the reflector (e.g. `"3M ESR"`, `"TiO2 paint"`).
    reflector: Optional[str] = None
    #: py-mat material key for the reflector, when one exists (e.g. `"esr"`).
    reflector_material: Optional[str] = None
    #: How the gap is filled — see `COUPLINGS`.
    coupling: Optional[str] = None
    #: py-mat material key for the coupling medium, when one exists.
    coupling_material: Optional[str] = None
    #: Refractive index of the coupling medium at the measurement wavelength.
    coupling_index: Optional[float] = None

    # --- measured optical values -----------------------------------------
    reflectivity: Optional[float] = None  # %, 0-100 (same convention as OpticalProperties)
    reflectivity_spectrum: Optional[Dict[str, List[float]]] = None
    thickness_um: Optional[float] = None

    note: Optional[str] = None

    # --- sidecars (same contract as Material) -----------------------------
    _sources: Dict[str, Source] = field(default_factory=dict, repr=False)
    _absent: Dict[str, Absent] = field(default_factory=dict, repr=False)
    #: Catalogue key of the parent node this entry inherited from, if any.
    _parent: Optional[str] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self._check_enum("model", self.model, MODELS)
        self._check_enum("treatment", self.treatment, TREATMENTS)
        self._check_enum("lut_family", self.lut_family, LUT_FAMILIES)
        self._check_enum("coupling", self.coupling, COUPLINGS)

        # A LUT entry without its enum spelling is unusable downstream, and a
        # non-LUT entry carrying one is claiming measured data it does not have.
        if self.model == "lut" and not self.lut_surface:
            raise ValueError(f"surface {self.key!r}: model='lut' requires 'lut_surface'")
        if self.lut_surface and self.model != "lut":
            raise ValueError(
                f"surface {self.key!r}: 'lut_surface' set but model is {self.model!r}, not 'lut'"
            )

        # An air gap is air. Anything else is not an air gap, and the
        # difference is exactly what this field exists to record.
        if self.coupling == "air_gap" and self.coupling_index is not None:
            if abs(self.coupling_index - 1.0) > 0.01:
                raise ValueError(
                    f"surface {self.key!r}: coupling='air_gap' but coupling_index="
                    f"{self.coupling_index}; use coupling='optical_contact' for a filled gap"
                )
        if self.coupling == "optical_contact" and self.coupling_index is None:
            raise ValueError(
                f"surface {self.key!r}: coupling='optical_contact' requires 'coupling_index' "
                f"— the index of the filling medium is the whole physical difference"
            )

        if self.reflectivity is not None:
            if not 0.0 <= self.reflectivity <= 100.0:
                raise ValueError(
                    f"surface {self.key!r}: reflectivity={self.reflectivity} out of range; "
                    f"the schema is percent (0-100), matching OpticalProperties.transparency"
                )
            # 0 < r < 1 is legal (a very dark surface) but is far more often a
            # fraction typed where a percent was meant. Warn rather than raise:
            # rejecting a legal value to catch a likely typo trades a certain
            # failure for a probable one. The value is never rewritten — a
            # silent x100 would be exactly the subtle-wrongness this schema
            # avoids elsewhere.
            if 0.0 < self.reflectivity < 1.0:
                logger.warning(
                    "surface %r: reflectivity=%s is in (0, 1). This field is PERCENT "
                    "(0-100) — 0.985 means 0.985%%, not 98.5%%. Value kept as written.",
                    self.key,
                    self.reflectivity,
                )

        if self.reflectivity_spectrum is not None:
            # Validate at load, like every other structured spectrum.
            WavelengthCurve.from_toml(self.reflectivity_spectrum, value_key="values")

    def _check_enum(self, fname: str, value: Optional[str], allowed: frozenset) -> None:
        if value is not None and value not in allowed:
            opts = ", ".join(sorted(allowed))
            raise ValueError(f"surface {self.key!r}: {fname}={value!r} not in {{{opts}}}")

    # --- accessors --------------------------------------------------------

    @property
    def reflectivity_curve(self) -> Optional[WavelengthCurve]:
        """`reflectivity_spectrum` as a `WavelengthCurve`, or None."""
        if self.reflectivity_spectrum is None:
            return None
        return WavelengthCurve.from_toml(self.reflectivity_spectrum, value_key="values")

    def reflectivity_at(self, wavelength: Any) -> Optional[float]:
        """Reflectivity (%) at a wavelength. Spectrum > scalar fallback, clamped."""
        curve = self.reflectivity_curve
        if curve is None:
            return self.reflectivity
        from .properties import _to_nm

        return curve.interpolate(_to_nm(wavelength))

    @property
    def is_optical_contact(self) -> bool:
        """True when the gap is index-filled (grease, glue, meltmount).

        The complement, `coupling == 'air_gap'`, is the case that produces
        total-internal-reflection light-piping.
        """
        return self.coupling == "optical_contact"

    def source_of(self, path: str) -> Optional[Source]:
        """Provenance for a field name, falling back to `_default`."""
        if not self._sources:
            return None
        if path in self._sources:
            return self._sources[path]
        return self._sources.get("_default")

    def absent(self, path: str) -> Optional[Absent]:
        """Declared absence for a field name, or None (#243)."""
        return self._absent.get(path) if self._absent else None

    def cite(self, path: Optional[str] = None) -> str:
        """BibTeX for one field, or for every source behind this entry."""
        if not self._sources:
            return ""
        if path is not None:
            src = self.source_of(path)
            return src.to_bibtex() if src is not None else ""
        seen: Dict[str, Source] = {}
        for src in self._sources.values():
            seen.setdefault(src.citation, src)
        return "\n\n".join(s.to_bibtex() for s in seen.values())

    def __repr__(self) -> str:
        bits = [repr(self.key)]
        if self.lut_surface:
            bits.append(f"lut={self.lut_surface}")
        if self.coupling:
            bits.append(f"coupling={self.coupling}")
        return f"Surface({', '.join(bits)})"


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

# Keys that configure the node itself rather than naming a child surface.
_FIELD_KEYS = frozenset(
    {
        "name",
        "model",
        "treatment",
        "lut_family",
        "lut_surface",
        "g4_surface_type",
        "lut_dataset",
        "reflector",
        "reflector_material",
        "coupling",
        "coupling_material",
        "coupling_index",
        "reflectivity",
        "reflectivity_spectrum",
        "thickness_um",
        "note",
        "abstract",
    }
)


def _resolve_node(
    key: str,
    data: Dict[str, Any],
    inherited: Dict[str, Any],
    parent_sources: Dict[str, Source],
    parent_absent: Dict[str, Absent],
    parent_key: Optional[str],
    out: Dict[str, Surface],
) -> None:
    """Recursively resolve one catalogue node and its children.

    Inheritance is plain overlay: a child sees every field its ancestors set
    and overrides what it re-declares. This is what makes the LBNL family — 3
    treatments x 7 wrappings sharing one citation — expressible without
    repeating the citation 21 times, which is how citations rot.
    """
    own = {k: v for k, v in data.items() if k in _FIELD_KEYS}
    merged = {**inherited, **own}

    sources = parent_sources
    if "_sources" in data:
        raw = data["_sources"]
        if not isinstance(raw, dict):
            raise ValueError(f"surface {key!r}: _sources must be a table, got {type(raw).__name__}")
        sources = merge_sources(parent_sources, parse_sources_table(raw))

    absent = parent_absent
    if "_absent" in data:
        raw_absent = data["_absent"]
        if not isinstance(raw_absent, dict):
            raise ValueError(
                f"surface {key!r}: _absent must be a table, got {type(raw_absent).__name__}"
            )
        absent = {**parent_absent, **parse_absent_table(raw_absent)}

    # Abstract nodes exist only to carry shared fields and citations down to
    # their children. They are not catalogue entries and are not registered.
    if not merged.pop("abstract", False):
        fields = {k: v for k, v in merged.items() if k != "abstract"}
        fields.setdefault("name", key)
        out[key] = Surface(key=key, _sources=sources, _absent=absent, _parent=parent_key, **fields)

    child_inherited = {k: v for k, v in merged.items() if k != "abstract"}
    # A child must not inherit its parent's identity fields — those are what
    # makes each entry distinct. Everything else (family, dataset, model,
    # citations) is exactly what we want flowing down.
    for identity in ("name", "lut_surface", "note"):
        child_inherited.pop(identity, None)

    for child_key, child_data in data.items():
        if child_key in _FIELD_KEYS or child_key.startswith("_"):
            continue
        if not isinstance(child_data, dict):
            continue
        _resolve_node(
            f"{key}.{child_key}",
            child_data,
            child_inherited,
            sources,
            absent,
            key,
            out,
        )


def load_surfaces(file_path: Path | str | None = None) -> Dict[str, Surface]:
    """Load the surface catalogue from `surfaces.toml`.

    Entries live under a top-level `[surface]` table; registry keys are the
    dotted path with that prefix stripped (`surface.davis.polished_esr_grease`
    on disk becomes `davis.polished_esr_grease`).
    """
    if file_path is None:
        file_path = Path(__file__).parent / "data" / "surfaces.toml"
    file_path = Path(file_path)
    with open(file_path, "rb") as f:
        raw = tomllib.load(f)

    out: Dict[str, Surface] = {}
    root = raw.get("surface", {})
    for key, node in root.items():
        if isinstance(node, dict):
            _resolve_node(key, node, {}, {}, {}, None, out)
    return out


# ---------------------------------------------------------------------------
# Registry — mirrors the `pymat.materials` contract (#228)
# ---------------------------------------------------------------------------

_CACHE: Optional[Dict[str, Surface]] = None


def _catalogue() -> Dict[str, Surface]:
    global _CACHE
    if _CACHE is None:
        _CACHE = load_surfaces()
    return _CACHE


def _normalise(key: str) -> str:
    """Accept `surface.davis.rough` as well as `davis.rough`.

    The `surface.` prefix is how the key is spelled on disk and how it travels
    in downstream files, so both spellings resolve.
    """
    return key[len("surface.") :] if key.startswith("surface.") else key


class _Surfaces(Mapping[str, Surface]):
    """The ``pymat.surfaces`` registry surface — Mapping + callable + filterable."""

    def __getitem__(self, key: str) -> Surface:
        cat = _catalogue()
        norm = _normalise(key)
        if norm not in cat:
            raise KeyError(
                f"Unknown surface {key!r}. The catalogue holds measured interfaces only "
                f"({len(cat)} entries); analytic UNIFIED finishes such as 'polished' or "
                f"'ground' are model selections and live in the consuming engine's config "
                f"(ADR-0004 §3)."
            )
        return cat[norm]

    def __iter__(self) -> Iterator[str]:
        return iter(_catalogue())

    def __len__(self) -> int:
        return len(_catalogue())

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and _normalise(key) in _catalogue()

    @overload
    def __call__(self, name: str, /) -> Surface: ...

    @overload
    def __call__(
        self,
        *,
        lut_family: str | None = None,
        coupling: str | None = None,
        treatment: str | None = None,
        model: str | None = None,
        reflector_material: str | None = None,
    ) -> list[Surface]: ...

    def __call__(
        self,
        name: str | None = None,
        /,
        *,
        lut_family: str | None = None,
        coupling: str | None = None,
        treatment: str | None = None,
        model: str | None = None,
        reflector_material: str | None = None,
    ) -> "Surface | list[Surface]":
        """Look up one surface by key, or filter the catalogue.

        surfaces("davis.polished_esr_grease")   # -> Surface
        surfaces(coupling="air_gap")            # -> list[Surface]
        """
        if name is not None:
            return self[name]
        criteria = {
            "lut_family": lut_family,
            "coupling": coupling,
            "treatment": treatment,
            "model": model,
            "reflector_material": reflector_material,
        }
        active = {k: v for k, v in criteria.items() if v is not None}
        return [
            s for s in _catalogue().values() if all(getattr(s, k) == v for k, v in active.items())
        ]

    def __repr__(self) -> str:
        return f"<pymat.surfaces: {len(self)} measured interfaces>"


surfaces = _Surfaces()
