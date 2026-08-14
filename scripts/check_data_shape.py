#!/usr/bin/env python3
"""Structural gates on the data corpus — the two failure modes that stayed
invisible longest in #243.

Both are cheap, both are checkable without knowing what any value MEANS, and
both had to be found by accident before being written down. They run as a
pre-commit hook because they fire at the moment of the edit, which is exactly
when the adjacent thing moves.

    python scripts/check_data_shape.py            # both checks
    python scripts/check_data_shape.py --drop     # just the field check
    python scripts/check_data_shape.py --place    # just the placement check

## Check 1: no silently-dropped keys

The loader assigns with `if hasattr(prop_obj, key)`. A TOML key with no
matching dataclass field is therefore parsed, validated, and thrown away — no
error, no warning, nothing. `[esr.optical] reflectivity = 98.5` was on disk
from #147 and dropped on every single load until #243; a corpus audit then
found four more.

A value can be cited, committed, reviewed, and still not be there.

## Check 2: no key filed under the wrong section banner

`scripts/enrich_from_refractiveindex.py` appends a key at the end of a
material's span, which lands it AFTER the following section banner. It parses
correctly — it still belongs to the preceding table — so nothing fails. But it
READS as part of the next section, and the next person to insert a table beside
it captures it into theirs. That nearly happened in #243.

Fixed by hand in metals.toml, then again in scintillators.toml, before anyone
wrote it down as an invariant. Fixing the same instance twice without gating it
is its own smell.

Stdlib-only by design, like `check_licenses.py` — it parses `properties.py`
with `ast` rather than importing `pymat`, so pre-commit can run it in a clean
isolated interpreter with nothing installed.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover — Python 3.10 path
    import tomli as tomllib

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "src" / "pymat" / "data"
PROPERTIES = REPO_ROOT / "src" / "pymat" / "properties.py"

# `surfaces.toml` is not a material catalogue — its nodes are `Surface`
# entries with their own field vocabulary and loader (ADR-0004 §2).
NON_MATERIAL_TOMLS = {"surfaces.toml"}

# Keys inside a material node that are not property groups.
LEAF_KEYS = {"name", "formula", "composition", "grade", "temper", "treatment", "vendor", "tags"}
# Groups the loader knows but this check does not model field-by-field.
SKIP_GROUPS = {"vis", "custom"}


# ---------------------------------------------------------------------------
# Check 1 — every TOML key has a field to land in
# ---------------------------------------------------------------------------


def dataclass_fields() -> dict[str, set[str]]:
    """`{group_name: {field, ...}}`, read from `properties.py` via `ast`.

    Derives the group→class mapping from `AllProperties`' own annotations, so
    adding a property group needs no edit here.
    """
    tree = ast.parse(PROPERTIES.read_text())
    classes: dict[str, set[str]] = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            classes[node.name] = {
                stmt.target.id
                for stmt in node.body
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
            }
    groups: dict[str, set[str]] = {}
    for stmt in tree.body:
        if isinstance(stmt, ast.ClassDef) and stmt.name == "AllProperties":
            for item in stmt.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    ann = item.annotation
                    if isinstance(ann, ast.Name) and ann.id in classes:
                        groups[item.target.id] = classes[ann.id]
    return groups


def dropped_keys() -> list[str]:
    """Keys present in a shipped material TOML with no receiving field."""
    groups = dataclass_fields()
    problems: list[str] = []

    def walk(node: object, path: str) -> None:
        if not isinstance(node, dict):
            return
        for key, value in node.items():
            if key.startswith("_"):
                continue
            if key in groups and isinstance(value, dict):
                fields = groups[key]
                for prop in value:
                    if prop.startswith("_") or prop.endswith(("_stddev", "_unit")):
                        continue
                    base = prop[:-6] if prop.endswith("_value") else prop
                    if base not in fields:
                        problems.append(f"{path}.{key}.{base}")
            elif isinstance(value, dict) and key not in SKIP_GROUPS and key not in LEAF_KEYS:
                walk(value, f"{path}.{key}")

    for toml_path in sorted(DATA_DIR.glob("*.toml")):
        if toml_path.name in NON_MATERIAL_TOMLS:
            continue
        with open(toml_path, "rb") as fh:
            doc = tomllib.load(fh)
        for key, value in doc.items():
            walk(value, f"{toml_path.name}:{key}")
    return problems


# ---------------------------------------------------------------------------
# Check 2 — no key separated from its table by a section banner
# ---------------------------------------------------------------------------


def is_section_banner(comment: str) -> bool:
    """True for a section divider (`# ======`), false for prose.

    This distinction is what makes the check usable. Most values in these files
    carry an explanatory comment; flagging those would make the check noise,
    and a noisy check gets deleted rather than obeyed.
    """
    body = comment.lstrip("#").strip()
    return len(body) >= 8 and set(body) <= set("=-— ")


def misplaced_keys(text: str) -> list[tuple[int, str, str]]:
    """`(line_no, key, owning_table)` for keys a banner separates from their header."""
    table: str | None = None
    saw_banner = False
    depth = 0
    out: list[tuple[int, str, str]] = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if depth > 0:  # inside a multi-line array
            depth += line.count("[") - line.count("]")
            continue
        if line.startswith("["):
            table, saw_banner = line, False
            continue
        if line.startswith("#"):
            saw_banner = saw_banner or is_section_banner(line)
            continue
        if not line or "=" not in line:
            continue
        if saw_banner and table is not None:
            out.append((lineno, line.split("=")[0].strip(), table))
        depth += line.count("[") - line.count("]")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--drop", action="store_true", help="only the dropped-key check")
    parser.add_argument("--place", action="store_true", help="only the placement check")
    args = parser.parse_args()
    run_drop = args.drop or not args.place
    run_place = args.place or not args.drop

    failures = 0

    if run_drop:
        dropped = dropped_keys()
        if dropped:
            failures += 1
            print("Silently-dropped keys — parsed, then discarded by the loader:")
            for item in dropped:
                print(f"  {item}")
            print("  Add the field to the relevant dataclass in src/pymat/properties.py.\n")

    if run_place:
        offenders: list[str] = []
        for toml_path in sorted(DATA_DIR.glob("*.toml")):
            for lineno, key, table in misplaced_keys(toml_path.read_text()):
                offenders.append(f"  {toml_path.name}:{lineno}  {key!r} belongs to {table}")
        if offenders:
            failures += 1
            print("Keys filed under the wrong section banner:")
            print("\n".join(offenders))
            print("  They parse correctly but read as part of the NEXT section, and an")
            print("  insertion beside them would capture them. Move them up to their table.\n")

    if failures:
        return 1
    print("Data shape OK: no dropped keys, no misfiled keys.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
