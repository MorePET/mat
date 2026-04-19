#!/usr/bin/env python3
"""One-shot migrator: rewrite slashed `[vis.finishes]` values to inline tables.

3.0 stored finishes as:

    [stainless.vis.finishes]
    brushed = "ambientcg/Metal012"
    polished = "ambientcg/Metal049A"

3.1 stores them as inline tables so `Vis` holds `source` + `material_id` as
two fields matching mat-vis-client's `(source, material_id)` signature
end-to-end (see ADR-0002):

    [stainless.vis.finishes]
    brushed = { source = "ambientcg", id = "Metal012" }
    polished = { source = "ambientcg", id = "Metal049A" }

This script does a line-oriented rewrite of every `src/pymat/data/*.toml`.
The rewrite is line-oriented (not tomllib-roundtrip) because tomllib emits
its own style that re-wraps long lines, reorders tables, and loses the
column-aligned blocks that make the data files readable. We only want to
rewrite the finish-value lines; everything else stays byte-identical.

Idempotent: a line already in inline-table form is left alone.

Usage:
    python scripts/migrate_toml_finishes.py            # rewrites in place
    python scripts/migrate_toml_finishes.py --check    # non-zero if anything would change
    python scripts/migrate_toml_finishes.py --diff     # show what would change, don't write
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "src" / "pymat" / "data"

# Matches a slashed-string finish value inside a [*.vis.finishes] section.
# We track section context separately (this regex runs only when we know
# we're inside a finishes table) so the pattern itself just catches the
# assignment.
#
# Groups:
#   1 — leading whitespace + `key =`
#   2 — quote char (single or double)
#   3 — source
#   4 — material_id
#   5 — trailing content (comments)
_SLASHED_FINISH_RE = re.compile(
    r"""^(\s*[A-Za-z_][A-Za-z0-9_]*\s*=\s*)"""  # key =
    r"""(['"])"""  # quote
    r"""([a-z0-9_-]+)"""  # source
    r"""/"""  # slash
    r"""([A-Za-z0-9_.-]+)"""  # material_id
    r"""\2"""  # closing quote (matches opener)
    r"""(\s*(?:#.*)?)$"""  # trailing (optional comment)
)

# Matches the start of a finishes table header: [anything.vis.finishes]
# Possibly nested (e.g. [stainless.s304.vis.finishes], though none in
# the current corpus — stay permissive).
_FINISHES_SECTION_RE = re.compile(r"^\s*\[[^\]]*\.vis\.finishes\]\s*$")

# Matches any new section header; used to know when we've left a
# finishes table.
_SECTION_RE = re.compile(r"^\s*\[")


def migrate_text(text: str) -> tuple[str, list[str]]:
    """Rewrite finish-value lines in a TOML file text.

    Returns (new_text, list_of_rewritten_line_descriptions).
    The descriptions are plain strings suitable for --diff / logging.
    """
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    rewritten: list[str] = []
    in_finishes = False

    for lineno, line in enumerate(lines, start=1):
        stripped = line.rstrip("\n\r")

        if _FINISHES_SECTION_RE.match(stripped):
            in_finishes = True
            out.append(line)
            continue

        if _SECTION_RE.match(stripped):
            # Any other section header closes the finishes block
            in_finishes = False
            out.append(line)
            continue

        if not in_finishes:
            out.append(line)
            continue

        # We're inside a [*.vis.finishes] block. Look for slashed-string values.
        m = _SLASHED_FINISH_RE.match(stripped)
        if not m:
            out.append(line)
            continue

        prefix, _quote, source, material_id, trailing = m.groups()
        new_line = f'{prefix}{{ source = "{source}", id = "{material_id}" }}{trailing}\n'
        out.append(new_line)
        rewritten.append(f"  line {lineno}: {stripped.strip()} -> {new_line.strip()}")

    return "".join(out), rewritten


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if any file would change. Don't write.",
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="Print the changes that would be made. Don't write.",
    )
    args = parser.parse_args()

    toml_paths = sorted(DATA_DIR.glob("*.toml"))
    if not toml_paths:
        print(f"No TOMLs found under {DATA_DIR}", file=sys.stderr)
        return 1

    any_changed = False
    for path in toml_paths:
        original = path.read_text()
        new, rewritten = migrate_text(original)
        if new == original:
            continue
        any_changed = True

        rel = path.relative_to(DATA_DIR.parent.parent.parent)
        print(f"{rel}: {len(rewritten)} finish line(s) rewritten")
        if args.diff:
            for desc in rewritten:
                print(desc)
        if not (args.check or args.diff):
            path.write_text(new)

    if args.check and any_changed:
        print("\nRun `python scripts/migrate_toml_finishes.py` to apply.", file=sys.stderr)
        return 1

    if not any_changed:
        print("All TOMLs already use inline-table finishes. Nothing to do.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
