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

# The loader accepts these top-level groups inside a material node.
# Anything else (other than child material keys + known leaf keys)
# is a typo or a drift signal.
_KNOWN_GROUPS = {
    "mechanical",
    "thermal",
    "electrical",
    "optical",
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

_SOURCE_ID_RE = re.compile(r"^[a-z0-9_-]+/[A-Za-z0-9_.-]+$")


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

    @pytest.mark.parametrize("toml_path", sorted(DATA_DIR.glob("*.toml")))
    def test_no_pbr_section(self, toml_path):
        """3.0 removed [pbr] — the loader rejects it, but catching it in the
        data files themselves gives a clearer error on contributor PRs."""
        data = tomllib.loads(toml_path.read_text())
        offenders = list(_walk_pbr_sections(data, prefix=toml_path.stem))
        assert not offenders, (
            f"{toml_path.name}: legacy [pbr] section(s) present (3.0 uses [vis]): {offenders}"
        )

    @pytest.mark.parametrize("toml_path", sorted(DATA_DIR.glob("*.toml")))
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

    def test_vis_finishes_use_valid_source_ids(self, all_materials):
        """Every finish value must look like `source/material_id` — anything
        else is a paste error that would 404 on the CDN at fetch time."""
        bad = []
        for key, mat in all_materials.items():
            for finish_name, source_id in (mat.vis.finishes or {}).items():
                if not _SOURCE_ID_RE.match(source_id):
                    bad.append(f"{key}.vis.finishes.{finish_name} = {source_id!r}")
        assert not bad, f"Malformed vis source_ids: {bad}"

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
