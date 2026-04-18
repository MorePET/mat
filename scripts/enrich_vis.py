#!/usr/bin/env python3
"""Propose [vis] mappings for materials that don't have one.

Uses tag-based matching against the mat-vis index — the ambientcg
and polyhaven tags ("brushed", "silver", "oak", "concrete", etc.)
give far better signal than category alone.

Usage:
    python scripts/enrich_vis.py                # preview
    python scripts/enrich_vis.py -o proposed.toml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pymat import load_all, vis


# Per-material tag heuristics — richer than category-only matching
# Each tuple: (category, required_tags_to_try_in_order)
# Multiple tag sets are tried; first non-empty result wins.
MATERIAL_HINTS: dict[str, tuple[str, list[list[str]]]] = {
    # Metals — finish matters
    "stainless": ("metal", [["brushed", "silver", "steel"], ["silver", "steel"], ["metal"]]),
    "s304": ("metal", [["brushed", "silver", "steel"], ["silver", "steel"]]),
    "s316L": ("metal", [["brushed", "silver", "steel"], ["silver", "steel"]]),
    "s303": ("metal", [["brushed", "silver", "steel"], ["silver", "steel"]]),
    "s17_4PH": ("metal", [["brushed", "silver", "steel"], ["silver", "steel"]]),
    "electropolished": ("metal", [["clean", "silver", "smooth"], ["smooth", "silver"]]),
    "passivated": ("metal", [["brushed", "silver"], ["silver", "steel"]]),
    "aluminum": ("metal", [["clean", "silver"], ["silver", "metal"]]),
    "a6061": ("metal", [["clean", "silver"], ["silver"]]),
    "a7075": ("metal", [["clean", "silver"], ["silver"]]),
    "a2024": ("metal", [["clean", "silver"], ["silver"]]),
    "a6063": ("metal", [["clean", "silver"], ["silver"]]),
    "copper": ("metal", [["copper", "clean", "shiny"], ["copper"]]),
    "OFHC": ("metal", [["copper", "clean"], ["copper"]]),
    "brass": ("metal", [["brass", "gold"], ["bronze"], ["copper", "gold"]]),
    "tungsten": ("metal", [["iron"], ["metal"]]),
    "pure": ("metal", [["iron"], ["metal"]]),
    "W90": ("metal", [["iron"], ["metal"]]),
    "lead": ("metal", [["grey", "metal", "smooth"], ["metal"]]),
    "titanium": ("metal", [["clean", "silver"], ["silver"]]),
    "grade5": ("metal", [["clean", "silver"], ["silver"]]),
    # Plastics — mostly matte, colored
    "peek": ("plastic", [["plastic"]]),
    "delrin": ("plastic", [["plastic"]]),
    "nylon": ("plastic", [["plastic"]]),
    "pla": ("plastic", [["plastic"]]),
    "abs": ("plastic", [["plastic"]]),
    "petg": ("plastic", [["plastic"]]),
    "ptfe": ("plastic", [["white", "plastic"], ["plastic"]]),
    "pmma": ("plastic", [["plastic"]]),
    "pe": ("plastic", [["plastic"]]),
    "pc": ("plastic", [["plastic"]]),
    "ultem": ("plastic", [["plastic"]]),
    "torlon": ("plastic", [["plastic"]]),
    "vespel": ("plastic", [["plastic"]]),
    "tpu": ("plastic", [["plastic"]]),
    "pctfe": ("plastic", [["plastic"]]),
    "esr": ("plastic", [["white"], ["plastic"]]),
    # Ceramics
    "alumina": ("ceramic", [["white", "clean"], ["ceramic"]]),
    "macor": ("ceramic", [["white"], ["ceramic"]]),
    "zirconia": ("ceramic", [["white"], ["ceramic"]]),
    "glass": ("ceramic", [["glass"]]),  # fallback since glass is rare
}


def _hints_for(key: str, name: str) -> tuple[str | None, list[list[str]]]:
    """Return (category, list of tag sets to try in order)."""
    key_lower = key.lower()
    name_lower = name.lower()

    for k, (cat, tag_sets) in MATERIAL_HINTS.items():
        if k.lower() in key_lower or k.lower() in name_lower:
            return cat, tag_sets

    # Generic category hints as fallback
    if any(w in name_lower for w in ["steel", "iron", "alloy"]):
        return "metal", [["silver", "steel"], ["metal"]]
    if any(w in name_lower for w in ["wood", "ply", "mdf"]):
        return "wood", [["wood"]]
    if "concrete" in name_lower:
        return "concrete", [["concrete"]]
    if any(w in name_lower for w in ["stone", "rock", "marble"]):
        return "stone", [["stone"]]

    return None, [[]]


def propose_mappings(limit_per_material: int = 3) -> list[dict]:
    """Generate vis mapping proposals using tag-based matching."""
    materials = load_all()
    proposals = []

    for key, mat in materials.items():
        if mat.vis.source_id is not None:
            continue

        category, tag_sets = _hints_for(key, mat.name)
        if not category:
            continue

        # Try tag sets in order, first match wins
        candidates = []
        tags_used = None
        for tags in tag_sets:
            try:
                results = vis.search(
                    category=category,
                    tags=tags if tags else None,
                    limit=limit_per_material,
                )
            except ConnectionError:
                continue
            if results:
                candidates = results
                tags_used = tags
                break

        if not candidates:
            continue

        # Format source_id as "source/id"
        for c in candidates:
            if "source" in c and "id" in c and "/" not in c["id"]:
                c["id"] = f"{c['source']}/{c['id']}"

        proposals.append({
            "material_key": key,
            "material_name": mat.name,
            "category": category,
            "tags_matched": tags_used,
            "candidates": candidates,
        })

    return proposals


def format_toml(proposals: list[dict]) -> str:
    """Format proposals as TOML [vis] sections."""
    lines = ["# Auto-generated vis mapping proposals (tag-based matching)", ""]

    for p in proposals:
        key = p["material_key"]
        top = p["candidates"][0]
        alts = p["candidates"][1:]

        lines.append(f"# {p['material_name']} — matched on tags {p['tags_matched']}")
        lines.append(f"# top tags: {', '.join(top.get('tags', [])[:6])}")
        if alts:
            lines.append(f"# alternatives: {[c['id'] for c in alts]}")
        lines.append(f"[{key}.vis.finishes]")
        lines.append(f'default = "{top["id"]}"')
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", "-o", help="Write proposals to file")
    args = parser.parse_args()

    proposals = propose_mappings()

    if not proposals:
        print("No unmapped materials found (or mat-vis index unavailable)")
        return

    toml_text = format_toml(proposals)

    if args.output:
        Path(args.output).write_text(toml_text)
        print(f"Wrote {len(proposals)} proposals to {args.output}", file=sys.stderr)
    else:
        print(toml_text)
        print(f"\n# {len(proposals)} materials proposed", file=sys.stderr)


if __name__ == "__main__":
    main()
