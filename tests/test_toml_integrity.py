"""TOML integrity tests — every shipped TOML parses, no field drift.

These tests are a safety net for the data files under `src/pymat/data/`.
They don't validate *correctness* of physical values (handbook data still
owns that); they validate *well-formedness*:

    - Every category declared in `_CATEGORY_BASES` has a loadable TOML.
    - Every base key in `_CATEGORY_BASES` resolves to a real material.
    - No TOML contains a `[pbr]` section (removed in 3.0).
    - No TOML uses a property-group key the loader doesn't know.
    - Every `[x.vis.finishes]` entry is a valid `source/material_id`.
    - Loading the full corpus emits zero `DeprecationWarning`s.

Catches: the class of bugs where someone renames a property group in
code but forgets a TOML, or ships a new material with a typo in a
section name, or adds a vis entry that would 404 on the CDN.
"""

from __future__ import annotations

import re
import sys
import warnings
from pathlib import Path

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover — 3.10 path
    import tomli as tomllib

from pymat import _CATEGORY_BASES, load_all
from pymat.loader import load_category

DATA_DIR = Path(__file__).resolve().parent.parent / "src" / "pymat" / "data"

# Material-catalogue TOMLs. `surfaces.toml` (#243) lives in the same directory
# but is not a material catalogue — its nodes are `Surface` entries with their
# own field vocabulary and their own loader, so the material-shape walkers below
# do not apply to it. Its integrity is covered by tests/test_surfaces.py.
NON_MATERIAL_TOMLS = {"surfaces.toml"}
MATERIAL_TOMLS = sorted(p for p in DATA_DIR.glob("*.toml") if p.name not in NON_MATERIAL_TOMLS)

# The loader accepts these top-level groups inside a material node.
# Anything else (other than child material keys + known leaf keys)
# is a typo or a drift signal.
_KNOWN_GROUPS = {
    "mechanical",
    "thermal",
    "electrical",
    "optical",
    "magnetic",
    "vacuum",
    "nuclear",
    "manufacturing",
    "compliance",
    "sourcing",
    "vis",
    "custom",
}
_KNOWN_LEAF_KEYS = {
    "name",
    "formula",
    "composition",
    "grade",
    "temper",
    "treatment",
    "vendor",
}
# Underscore-prefixed reserved keys at material-node level (#150).
# `_walk_unknown_groups` skips anything starting with `_`.

# Separate regexes per field — the slashed form conflated the two
# alphabets: source is lowercase-dashed (ambientcg, polyhaven, gpuopen),
# id can contain uppercase, digits, underscores, dots, dashes
# (Metal012, Plastic013A, metal_matte, Tiles074_A).
_SOURCE_RE = re.compile(r"^[a-z0-9_-]+$")
_MATERIAL_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


@pytest.fixture(scope="module")
def all_materials():
    """Load every category exactly once (the loader caches internally)."""
    return load_all()


class TestTOMLsAllParse:
    @pytest.mark.parametrize("category", list(_CATEGORY_BASES.keys()))
    def test_category_loads(self, category):
        """Every declared category has a file that parses and yields materials."""
        mats = load_category(category)
        assert len(mats) > 0, f"{category}: category loaded empty"

    def test_no_deprecation_warnings_on_full_load(self):
        """A full load of all TOMLs must not emit any DeprecationWarning.

        Canary for accidental reintroduction of deprecated surfaces —
        e.g. a [pbr] section sneaking into a TOML, or loader code
        re-reading `.properties.pbr`.
        """
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always", DeprecationWarning)
            # Force a fresh load through every category
            for cat in _CATEGORY_BASES:
                load_category(cat)
            dep_warnings = [w for w in captured if issubclass(w.category, DeprecationWarning)]
            assert not dep_warnings, (
                f"Full TOML load emitted {len(dep_warnings)} DeprecationWarning(s): "
                f"{[str(w.message) for w in dep_warnings]}"
            )

    def test_every_declared_base_key_resolves(self, all_materials):
        """_CATEGORY_BASES promises certain keys; the TOML must back them."""
        missing = []
        for category, base_keys in _CATEGORY_BASES.items():
            for key in base_keys:
                if key not in all_materials:
                    missing.append(f"{category}.{key}")
        assert not missing, f"Declared base materials missing from TOML: {missing}"


class TestTOMLShape:
    """Lint the raw TOML tree, not just the loaded material objects."""

    @pytest.mark.parametrize("toml_path", MATERIAL_TOMLS)
    def test_no_pbr_section(self, toml_path):
        """3.0 removed [pbr] — the loader rejects it, but catching it in the
        data files themselves gives a clearer error on contributor PRs."""
        data = tomllib.loads(toml_path.read_text())
        offenders = list(_walk_pbr_sections(data, prefix=toml_path.stem))
        assert not offenders, (
            f"{toml_path.name}: legacy [pbr] section(s) present (3.0 uses [vis]): {offenders}"
        )

    @pytest.mark.parametrize("toml_path", MATERIAL_TOMLS)
    def test_only_known_property_groups(self, toml_path):
        """Catch typos like [metals.aluminum.mechnical] — the loader would
        silently ignore the misspelled group, but the data would then be
        missing at runtime with no warning."""
        data = tomllib.loads(toml_path.read_text())
        unknown = list(_walk_unknown_groups(data, prefix=toml_path.stem))
        assert not unknown, (
            f"{toml_path.name}: unknown property-group keys "
            f"(typos? missing from _KNOWN_GROUPS?): {unknown}"
        )


class TestMaterialInvariants:
    """Every material that made it through the loader must satisfy these."""

    def test_every_material_has_name(self, all_materials):
        nameless = [k for k, m in all_materials.items() if not m.name]
        assert not nameless, f"Materials without name: {nameless}"

    def test_density_is_nonnegative_if_set(self, all_materials):
        """Density may be exactly 0.0 (vacuum) but never negative."""
        negatives = {
            k: m.density
            for k, m in all_materials.items()
            if m.density is not None and m.density < 0
        }
        assert not negatives, f"Materials with negative density: {negatives}"

    def test_vis_finishes_have_valid_shape(self, all_materials):
        """Every finish value must be {source, id} with both fields valid.

        Malformed entries get rejected at load time by Vis.from_toml,
        so this is a belt-and-braces check — any finish that made it
        through loading must also pass the per-field regexes.
        """
        bad = []
        for key, mat in all_materials.items():
            for finish_name, entry in (mat.vis.finishes or {}).items():
                if not isinstance(entry, dict):
                    bad.append(f"{key}.vis.finishes.{finish_name} = {entry!r} (not a dict)")
                    continue
                src = entry.get("source")
                mid = entry.get("id")
                if not src or not _SOURCE_RE.match(src):
                    bad.append(f"{key}.vis.finishes.{finish_name}.source = {src!r}")
                if not mid or not _MATERIAL_ID_RE.match(mid):
                    bad.append(f"{key}.vis.finishes.{finish_name}.id = {mid!r}")
        assert not bad, f"Malformed vis finishes: {bad}"

    def test_vis_pbr_scalars_in_range(self, all_materials):
        """Sanity-check PBR scalars — metallic/roughness in [0, 1], ior > 0."""
        out_of_range = []
        for key, mat in all_materials.items():
            v = mat.vis
            if v.metallic is not None and not 0.0 <= v.metallic <= 1.0:
                out_of_range.append(f"{key}.vis.metallic = {v.metallic}")
            if v.roughness is not None and not 0.0 <= v.roughness <= 1.0:
                out_of_range.append(f"{key}.vis.roughness = {v.roughness}")
            if v.ior is not None and v.ior <= 0:
                out_of_range.append(f"{key}.vis.ior = {v.ior}")
            if v.transmission is not None and not 0.0 <= v.transmission <= 1.0:
                out_of_range.append(f"{key}.vis.transmission = {v.transmission}")
        assert not out_of_range, f"Out-of-range PBR scalars: {out_of_range}"


# ---------------------------------------------------------------------
# Walkers — reusable for the parametrized tests above
# ---------------------------------------------------------------------


def _walk_pbr_sections(node, prefix: str):
    """Yield dotted paths to every `pbr` key anywhere in the TOML tree."""
    if not isinstance(node, dict):
        return
    for key, value in node.items():
        path = f"{prefix}.{key}"
        if key == "pbr" and isinstance(value, dict):
            yield path
        if isinstance(value, dict):
            yield from _walk_pbr_sections(value, path)


def _walk_unknown_groups(node, prefix: str):
    """Yield dotted paths to top-level property-group keys we don't recognize.

    A material node can contain any mix of:
    - Leaf material metadata (name, formula, …)
    - Known property groups (mechanical, thermal, …, vis)
    - Nested child materials (sub-dicts that themselves look like material
      nodes — identified by having their own ``name`` field)

    Anything else at material-node depth is a typo or rename drift.
    """
    if not isinstance(node, dict):
        return
    for key, value in node.items():
        path = f"{prefix}.{key}"
        if not isinstance(value, dict):
            continue
        if key.startswith("_"):
            # Reserved underscore-prefixed keys (#150 _sources, future _curve etc.)
            continue
        if _looks_like_material_node(value):
            # Child material — recurse without flagging
            yield from _walk_unknown_groups(value, path)
            continue
        if key in _KNOWN_GROUPS or key in _KNOWN_LEAF_KEYS:
            continue
        yield path


def _looks_like_material_node(d: dict) -> bool:
    """Heuristic: a child material has a `name` string at its own level."""
    return isinstance(d.get("name"), str)


# ---------------------------------------------------------------------------
# Structural invariants (#243)
# ---------------------------------------------------------------------------
# These check the SHAPE of the file rather than the meaning of its values.
#
# Motivation: three latent defects in this branch were positional — invisible
# to any test of the thing itself, and visible only when something adjacent
# moved. The enricher appends a key at the end of a material's span, which
# lands it AFTER the following section banner; it parses correctly, so nothing
# fails, but it is filed under the wrong heading and the next person to insert
# a table beside it captures it into their own.
#
# Fixed by hand twice (metals.toml, then scintillators.toml) before being
# written down as an invariant. A structural property is checkable without
# knowing what any key means, which is what makes this class routinizable at
# all: "every key is adjacent to its table header" needs no domain knowledge.


def _is_section_banner(comment: str) -> bool:
    """True for a section-divider comment (`# ======`), false for prose.

    This is the whole subtlety of the check. A prose comment before a key is
    normal and desirable — most values in these files carry one. A BANNER
    before a key means the key sits on the far side of a section boundary from
    the table it actually belongs to. Only the second is a defect.
    """
    body = comment.lstrip("#").strip()
    return len(body) >= 8 and set(body) <= set("=-— ")


def _keys_separated_from_their_header(text: str):
    """Yield (line_no, key, table) for keys a SECTION BANNER separates from
    their table header.

    Such a key parses as part of the preceding table but reads as part of the
    following section. Correct to the machine, misleading to a human, and a
    trap for the next person who inserts a table beside it.
    """
    table = None
    saw_banner = False
    depth = 0
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        # Skip continuation lines inside multi-line arrays.
        if depth > 0:
            depth += line.count("[") - line.count("]")
            continue
        if line.startswith("["):
            table = line
            saw_banner = False
            continue
        if line.startswith("#"):
            if _is_section_banner(line):
                saw_banner = True
            continue
        if not line or "=" not in line:
            continue
        if saw_banner and table is not None:
            yield n, line.split("=")[0].strip(), table
        depth += line.count("[") - line.count("]")


class TestStructuralPlacement:
    @pytest.mark.parametrize("toml_path", sorted(DATA_DIR.glob("*.toml")))
    def test_no_key_is_separated_from_its_table_by_a_banner(self, toml_path):
        offenders = list(_keys_separated_from_their_header(toml_path.read_text()))
        assert not offenders, (
            f"{toml_path.name}: key(s) filed under the wrong heading — they parse "
            f"as part of the preceding table but read as part of the following "
            f"section, and an insertion beside them would capture them:\n"
            + "\n".join(f"  line {n}: {k!r} actually belongs to {t}" for n, k, t in offenders)
        )

    def test_the_check_detects_a_planted_misplacement(self):
        """Auditing the auditor: a structural check that cannot fail is worth
        nothing, so prove it fires on the historical defect shape."""
        planted = (
            "[a.optical]\nrefractive_index = 1.5\n\n"
            "# ====================\n# SECTION B\n# ====================\n"
            'absorption_length = 200.0\n\n[b]\nname = "B"\n'
        )
        found = list(_keys_separated_from_their_header(planted))
        assert len(found) == 1
        assert found[0][1] == "absorption_length"
        assert found[0][2] == "[a.optical]"

    def test_prose_comments_do_not_trip_it(self):
        """Most values in these files carry an explanatory comment. Flagging
        those would make the check unusable, and an unusable check gets
        deleted rather than obeyed."""
        ok = (
            "[a.optical]\n"
            "# Refractive index at the sodium D line, per the vendor sheet.\n"
            "refractive_index = 1.5\n"
            "# A second explanatory note, several words long.\n"
            "light_yield = 32000\n"
        )
        assert list(_keys_separated_from_their_header(ok)) == []

    def test_multiline_arrays_do_not_trip_it(self):
        """`decay_components` spans lines; its continuations are not keys."""
        arr = (
            "[a.optical]\n"
            "decay_components = [\n"
            "    { tau_ns = 12.0, fraction = 0.3 },\n"
            "    { tau_ns = 42.0, fraction = 0.7 },\n"
            "]\n"
        )
        assert list(_keys_separated_from_their_header(arr)) == []
