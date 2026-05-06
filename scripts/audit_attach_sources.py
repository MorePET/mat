#!/usr/bin/env python3
"""One-time #175 audit: attach `_sources._default` to every TOML material.

For every material node in `src/pymat/data/*.toml` that lacks a `_sources`
table, append a `_default` placeholder Source pointing at the aggregate
curation history. This satisfies `scripts/check_licenses.py` without
fabricating per-source provenance — future per-source PRs (#158-#173)
will overwrite each entry with proper citations.

A "material node" is any TOML table that carries a `name` string field
(top-level materials, grade variants, treated finishes, etc.).

Idempotent: a node that already has `_sources._default` is skipped.

Strategy: append new `[<path>._sources._default]` sections at the end
of each TOML file. TOML is order-agnostic, so this preserves all
existing formatting and comments.

Stdlib only; safe to re-run.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterator

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "src" / "pymat" / "data"

PLACEHOLDER_CITATION = "py-mat-curation-3.x"
PLACEHOLDER_KIND = "handbook"
PLACEHOLDER_REF = (
    "py-mat curation history; values from handbook/vendor/Wikidata aggregate (pre-#175 audit)"
)
PLACEHOLDER_LICENSE = "proprietary-reference-only"


def iter_material_nodes(node: dict, prefix: str) -> Iterator[tuple[str, dict]]:
    """Yield (dotted_path, node_dict) for every material node.

    A material node is any dict with a string `name` field. Walks the
    full TOML tree, skipping underscore-prefixed keys and non-dict
    children (e.g. property arrays).
    """
    if not isinstance(node, dict):
        return
    if isinstance(node.get("name"), str):
        yield prefix, node
    for child_key, child in node.items():
        if child_key.startswith("_") or not isinstance(child, dict):
            continue
        next_prefix = f"{prefix}.{child_key}" if prefix else child_key
        yield from iter_material_nodes(child, next_prefix)


def has_default_source(node: dict) -> bool:
    """True iff this node already has a `_sources._default` entry."""
    sources = node.get("_sources")
    if not isinstance(sources, dict):
        return False
    return isinstance(sources.get("_default"), dict)


def render_default_block(material_path: str) -> str:
    """Build the `[<path>._sources._default]` TOML block as text."""
    return (
        f"[{material_path}._sources._default]\n"
        f'citation = "{PLACEHOLDER_CITATION}"\n'
        f'kind = "{PLACEHOLDER_KIND}"\n'
        f'ref = "{PLACEHOLDER_REF}"\n'
        f'license = "{PLACEHOLDER_LICENSE}"\n'
    )


def process_file(toml_path: Path) -> tuple[int, int, int]:
    """Append placeholder sources to a single TOML file.

    Returns (total_materials, already_had_default, added_default).
    """
    text = toml_path.read_text()
    data = tomllib.loads(text)

    materials = list(iter_material_nodes(data, ""))
    total = len(materials)
    skipped = 0
    additions: list[str] = []

    for path, node in materials:
        if has_default_source(node):
            skipped += 1
            continue
        additions.append(render_default_block(path))

    if not additions:
        return total, skipped, 0

    # Ensure file ends on a newline before our appended block.
    if not text.endswith("\n"):
        text += "\n"
    if not text.endswith("\n\n"):
        text += "\n"

    header = (
        "# ============================================================================\n"
        "# Provenance (#175 audit)\n"
        "# ----------------------------------------------------------------------------\n"
        "# Default _sources entries attached during the one-time #175 audit. These\n"
        "# placeholder citations point at py-mat's aggregate curation history; future\n"
        "# per-source PRs (#158-#173) overwrite individual entries with proper\n"
        "# citations (Wikidata QIDs, NIST datasets, vendor URLs, etc.).\n"
        "# ============================================================================\n"
    )
    body = "\n".join(additions)
    toml_path.write_text(text + header + "\n" + body)
    return total, skipped, len(additions)


def main() -> int:
    grand_total = 0
    grand_skipped = 0
    grand_added = 0
    print(f"Scanning {DATA_DIR.relative_to(REPO_ROOT)}/")
    for toml_path in sorted(DATA_DIR.glob("*.toml")):
        total, skipped, added = process_file(toml_path)
        grand_total += total
        grand_skipped += skipped
        grand_added += added
        rel = toml_path.relative_to(REPO_ROOT)
        print(f"  {rel}: {total} material(s), {skipped} already-defaulted, {added} added")
    print()
    print(
        f"Done. {grand_total} material(s) total; "
        f"{grand_added} new _default entries added; "
        f"{grand_skipped} already had _default."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
