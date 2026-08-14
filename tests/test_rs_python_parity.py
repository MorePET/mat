"""The Python loader and the Rust loader must resolve the same TOML identically.

Both `src/pymat/loader.py` and `mat-rs/src/db.rs` parse the same data files
independently. Nothing structural stops them drifting apart, and they have:
#157 moved `radiation_length` to `nuclear` and the Rust side lagged; the strata
brief of 2026-08-14 was filed largely because the Rust crate had fallen years
behind the Python schema.

Conventions did not catch that. A gate does.

This test drives `cargo run --example dump_parity`, resolves the same materials
through Python, and diffs field by field. It SKIPS when cargo or the crate is
unavailable, so a Python-only checkout is unaffected; CI runs both toolchains.

If this fails, the two loaders disagree about what the data means. Python is the
source of truth (ADR-0004 §7) — fix the Rust side unless Python is the one that
is wrong, which has happened.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

import pymat

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "mat-rs" / "Cargo.toml"

pytestmark = pytest.mark.skipif(
    shutil.which("cargo") is None or not MANIFEST.exists(),
    reason="cargo or the mat-rs crate is unavailable; parity gate runs in CI",
)

# Rust field name -> how to read the same value from a Python Material.
# `temper` is dumped as None by the example because the Rust side does not type
# it yet; it is excluded rather than compared against a known-constant None,
# which would pass vacuously and hide the day someone adds it.
FIELDS = {
    "name": lambda m: m.name,
    "formula": lambda m: m.formula,
    "density": lambda m: m.properties.mechanical.density,
    "grade": lambda m: m.grade,
    "treatment": lambda m: m.treatment,
    "vendor": lambda m: m.vendor,
    "n": lambda m: m.properties.optical.refractive_index,
    "ly": lambda m: m.properties.optical.light_yield,
    "dt": lambda m: m.properties.optical.decay_time,
    "rt": lambda m: m.properties.optical.rise_time,
    "ep": lambda m: m.properties.optical.emission_peak,
    "refl": lambda m: m.properties.optical.reflectivity,
    "transp": lambda m: m.properties.optical.transparency,
    "abs": lambda m: m.properties.optical.absorption_length,
    "reabs": lambda m: m.properties.optical.absorption_length_reabs,
    "matrix": lambda m: m.properties.optical.absorption_length_matrix,
    "reemit": lambda m: m.properties.optical.reemit_qe,
    "dopant": lambda m: m.properties.optical.dopant,
    "dopant_pct": lambda m: m.properties.optical.dopant_pct,
    "hygro": lambda m: m.properties.optical.hygroscopic,
    "radlen": lambda m: m.properties.nuclear.radiation_length,
    "intlen": lambda m: m.properties.nuclear.interaction_length,
    "activity": lambda m: m.properties.nuclear.intrinsic_activity_Bq_per_g,
    "melt": lambda m: m.properties.thermal.melting_point,
    "tc": lambda m: m.properties.thermal.thermal_conductivity,
    # Tags are the one leaf key that UNIONS with the parent instead of
    # replacing it (#132). Compared as a joined string so ordering is part of
    # the contract — parent context first, then the child's own labels.
    "tags": lambda m: ",".join(m.tags),
}


def _parse_rust_value(raw: str):
    """Turn a Rust `{:?}` rendering into a Python value."""
    if raw == "None":
        return None
    if raw.startswith("Some(") and raw.endswith(")"):
        raw = raw[5:-1]
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1]
    if raw == "true":
        return True
    if raw == "false":
        return False
    try:
        return float(raw)
    except ValueError:
        return raw


def _normalise(value):
    """Coerce for comparison: ufloat -> nominal, int -> float."""
    value = getattr(value, "nominal_value", value)
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    return value


@pytest.fixture(scope="module")
def rust_materials() -> dict[str, dict[str, object]]:
    proc = subprocess.run(
        ["cargo", "run", "--quiet", "--manifest-path", str(MANIFEST), "--example", "dump_parity"],
        capture_output=True,
        text=True,
        timeout=600,
    )
    if proc.returncode != 0:
        pytest.fail(f"cargo run --example dump_parity failed:\n{proc.stderr[-4000:]}")

    out: dict[str, dict[str, object]] = {}
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("|")
        fields = {}
        for chunk in parts[1:]:
            key, _, raw = chunk.partition("=")
            fields[key] = _parse_rust_value(raw)
        out[parts[0]] = fields
    return out


@pytest.fixture(scope="module")
def python_materials() -> dict[str, object]:
    """Every material keyed by its dotted path, mirroring the Rust key scheme."""
    pymat.load_all()

    def walk(mat, key, out):
        out[key] = mat
        for child_key, child in mat._children.items():
            walk(child, f"{key}.{child_key}", out)

    out: dict[str, object] = {}
    for bases in pymat._CATEGORY_BASES.values():
        for base in bases:
            mat = pymat.registry.get(base)
            if mat is not None:
                walk(mat, base, out)
    return out


class TestLoaderParity:
    def test_rust_dump_is_non_empty(self, rust_materials):
        assert len(rust_materials) > 100, "the Rust dump looks truncated"

    def test_every_python_material_exists_in_rust(self, python_materials, rust_materials):
        """Every material Python resolves must also resolve in Rust.

        The reverse does not hold: `_CATEGORY_BASES` does not list every
        top-level TOML key, so the Rust side legitimately sees more.
        """
        missing = sorted(set(python_materials) - set(rust_materials))
        # `inconel625`/`inconel718`/`OFHC` are declared as category bases but
        # live nested in the TOML, so their dotted paths differ. They are
        # reachable in both; only the path spelling differs.
        missing = [m for m in missing if m not in {"inconel625", "inconel718", "OFHC"}]
        assert not missing, f"materials Python resolves but Rust does not: {missing}"

    def test_all_fields_agree(self, python_materials, rust_materials):
        shared = sorted(set(python_materials) & set(rust_materials))
        assert shared, "no overlap — the key schemes have diverged entirely"

        disagreements = []
        for key in shared:
            mat = python_materials[key]
            rust = rust_materials[key]
            for field, read in FIELDS.items():
                if field not in rust:
                    continue
                py_value = _normalise(read(mat))
                rs_value = _normalise(rust[field])
                if isinstance(py_value, float) and isinstance(rs_value, float):
                    if abs(py_value - rs_value) < 1e-9:
                        continue
                elif py_value == rs_value:
                    continue
                disagreements.append(f"  {key}.{field}: python={py_value!r} rust={rs_value!r}")

        assert not disagreements, (
            "the Python and Rust loaders disagree about the same TOML "
            f"({len(disagreements)} field(s)). Python is the source of truth "
            "(ADR-0004 §7).\n" + "\n".join(disagreements[:40])
        )

    def test_the_fields_that_regressed_before_are_covered(self, rust_materials):
        """Pin the specific values behind past drift, so a future refactor that
        breaks them fails here with a recognisable name.

        - `radiation_length` moved optical -> nuclear in #157.
        - `esr.reflectivity` was dropped by both loaders until #243.
        - Root-material `grade`/`vendor` were dropped by Python until #243 (an
          operator-precedence bug this very parity check surfaced).
        """
        assert rust_materials["lyso"]["radlen"] == 1.14
        assert rust_materials["esr"]["refl"] == 98.5
        assert rust_materials["beryllium"]["grade"] == "S-200F"
        assert rust_materials["esr"]["vendor"] == "3M"
        assert pymat.beryllium.grade == "S-200F"
        assert pymat.esr.vendor == "3M"

    def test_child_tags_union_with_the_parent(self, rust_materials):
        """A child declares only what is new and inherits the rest. Replacing
        rather than unioning made s316L claim 4 tags where py-mat reports 7."""
        parent = rust_materials["stainless"]["tags"]
        child = rust_materials["stainless.s316L"]["tags"]
        assert parent == "ferrous,stainless,corrosion-resistant"
        assert child.startswith(parent), "child tags must keep the parent's, in order, first"
        assert "316-family" in child
        assert child == ",".join(pymat.stainless.s316L.tags)
