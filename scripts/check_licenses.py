#!/usr/bin/env python3
"""Validate _sources licenses across every TOML in src/pymat/data/.

Walks each `[<material>._sources]` block (recursively, including nested
property-group sub-tables), verifies every entry has a `license` in the
allowed set, and blocks merge if anything is missing or `unknown`.

Honors `.github/license-ratchet.txt` during the #175 audit window — paths
listed there (one per line, repo-relative) are exempted until the audit
completes; the ratchet file is deleted as the final step of #175.

Stdlib-only by design — runs in pre-commit and CI without extra deps.

Usage:
    python scripts/check_licenses.py            # validate, exit 1 on issues
    python scripts/check_licenses.py --emit-attributions  # print LICENSES-DATA.md content

See docs/data-policy.md for the full policy.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterator

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover — Python 3.10 path
    import tomli as tomllib

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "src" / "pymat" / "data"
RATCHET = REPO_ROOT / ".github" / "license-ratchet.txt"

ALLOWED = {
    "CC0",
    "PD-USGov",
    "CC-BY-4.0",
    "CC-BY-SA-4.0",
    "proprietary-reference-only",
}
# `unknown` is parseable but rejected — transitional value, blocked at merge.

# Licenses requiring attribution in LICENSES-DATA.md.
ATTRIBUTION_REQUIRED = {"CC-BY-4.0", "CC-BY-SA-4.0"}


def load_ratchet() -> set[str]:
    """Read the ratchet file (one repo-relative path per line, # comments OK)."""
    if not RATCHET.exists():
        return set()
    out = set()
    for line in RATCHET.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            out.add(line)
    return out


def walk_sources(node: dict, prefix: str) -> Iterator[tuple[str, str, dict]]:
    """Yield (material_path, source_key, source_dict) for every _sources entry.

    Walks the TOML tree recursively. `_sources` may appear at the material
    node or inside a property group (e.g. `[mat.thermal._sources]`).
    """
    if not isinstance(node, dict):
        return
    sources = node.get("_sources")
    if isinstance(sources, dict):
        for key, val in sources.items():
            if isinstance(val, dict):
                yield prefix, key, val
    for child_key, child in node.items():
        if child_key.startswith("_") or not isinstance(child, dict):
            continue
        yield from walk_sources(child, f"{prefix}.{child_key}")


def validate() -> int:
    """Validate licenses across the data corpus. Returns exit code."""
    ratchet = load_ratchet()
    errors: list[str] = []

    for toml_path in sorted(DATA_DIR.glob("*.toml")):
        try:
            rel = str(toml_path.relative_to(REPO_ROOT))
        except ValueError:
            # Test contexts may point DATA_DIR outside the repo; fall back
            # to the absolute path for the ratchet lookup.
            rel = str(toml_path)
        if rel in ratchet:
            continue
        try:
            data = tomllib.loads(toml_path.read_text())
        except tomllib.TOMLDecodeError as e:
            errors.append(f"{rel}: TOML parse error: {e}")
            continue

        for mat_path, src_key, src in walk_sources(data, toml_path.stem):
            location = f"{rel}:{mat_path}._sources.{src_key}"
            lic = src.get("license")
            if lic is None:
                errors.append(f"{location}: missing 'license' field")
            elif lic == "unknown":
                errors.append(f"{location}: license='unknown' — must resolve before merge")
            elif lic not in ALLOWED:
                allowed_str = ", ".join(sorted(ALLOWED))
                errors.append(f"{location}: license={lic!r} not in allow-list ({allowed_str})")

    if errors:
        print(f"License validation failed — {len(errors)} issue(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        print("\nSee docs/data-policy.md for allowed values.", file=sys.stderr)
        return 1
    print(f"License check passed: scanned {len(list(DATA_DIR.glob('*.toml')))} TOML file(s).")
    return 0


def emit_attributions() -> int:
    """Print the LICENSES-DATA.md content to stdout. Deterministic — sorted by citation."""
    cc_sources: dict[str, dict] = {}  # citation -> source dict (dedup)
    for toml_path in sorted(DATA_DIR.glob("*.toml")):
        try:
            data = tomllib.loads(toml_path.read_text())
        except tomllib.TOMLDecodeError:
            continue
        for _, _, src in walk_sources(data, toml_path.stem):
            lic = src.get("license")
            if lic in ATTRIBUTION_REQUIRED:
                citation = src.get("citation")
                if citation and citation not in cc_sources:
                    cc_sources[citation] = src

    print("# Data attributions")
    print()
    print("Auto-generated by `scripts/check_licenses.py --emit-attributions`.")
    print("Do not edit by hand — re-run the script and commit the result.")
    print()
    print("This file lists every CC-BY and CC-BY-SA source whose values appear in the")
    print("py-materials data corpus. Per the licenses, attribution is required.")
    print()
    if not cc_sources:
        print("_(no CC-BY sources currently in use)_")
        return 0
    print("| Citation | License | Reference |")
    print("|---|---|---|")
    for citation in sorted(cc_sources):
        src = cc_sources[citation]
        ref = src.get("ref", "")
        lic = src["license"]
        print(f"| `{citation}` | {lic} | {ref} |")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--emit-attributions",
        action="store_true",
        help="Print LICENSES-DATA.md content to stdout instead of validating.",
    )
    args = parser.parse_args()
    if args.emit_attributions:
        return emit_attributions()
    return validate()


if __name__ == "__main__":
    sys.exit(main())
