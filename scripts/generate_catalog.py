#!/usr/bin/env python3
"""Generate a markdown material catalog with thumbnails from mat-vis.

Outputs a docs/catalog/ tree with per-category index pages and
per-material detail pages, each with a small thumbnail PNG from
the mat-vis color texture.

Usage:
    python scripts/generate_catalog.py                    # generate to docs/catalog/
    python scripts/generate_catalog.py --output /tmp/cat  # custom output dir
    python scripts/generate_catalog.py --skip-thumbnails  # text only, no vis fetch

Called by .github/workflows/catalog.yml on push to dev.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pymat import load_all

log = logging.getLogger("catalog")

THUMB_TIER = "128"  # mat-vis hosts 128/256/512 thumbnail tiers
CATEGORIES_ORDER = [
    "metals", "scintillators", "ceramics", "plastics",
    "electronics", "liquids", "gases",
]


def _fetch_thumbnail(source: str, material_id: str) -> bytes:
    """Fetch a thumbnail PNG from mat-vis's thumbnail tier.

    mat-vis hosts 128/256/512 tiers as pre-baked small textures —
    no Pillow resize needed, just fetch the color channel at the
    thumbnail tier.
    """
    try:
        from pymat import vis
        textures = vis.fetch(source, material_id, tier=THUMB_TIER)
        return textures.get("color", b"")
    except Exception as exc:
        log.debug("thumbnail fetch failed for %s/%s: %s", source, material_id, exc)
        return b""


def _format_value(key: str, value, unit: str | None = None) -> str:
    """Format a property value for markdown."""
    if value is None:
        return "—"
    if isinstance(value, float):
        formatted = f"{value:.4g}"
    else:
        formatted = str(value)
    if unit:
        formatted += f" {unit}"
    return formatted


def _material_page(mat, thumb_path: str | None, category: str) -> str:
    """Generate markdown for a single material detail page."""
    lines = [f"# {mat.name}", ""]

    if thumb_path:
        lines.append(f"![{mat.name}]({thumb_path})")
        lines.append("")

    # Identity
    lines.append("## Identity")
    lines.append("")
    lines.append(f"| Field | Value |")
    lines.append(f"|---|---|")
    if mat.formula:
        lines.append(f"| Formula | `{mat.formula}` |")
    if mat.grade:
        lines.append(f"| Grade | {mat.grade} |")
    if mat.temper:
        lines.append(f"| Temper | {mat.temper} |")
    if mat.treatment:
        lines.append(f"| Treatment | {mat.treatment} |")
    lines.append("")

    # Mechanical
    mech = mat.properties.mechanical
    if mech.density is not None or mech.youngs_modulus is not None:
        lines.append("## Mechanical Properties")
        lines.append("")
        lines.append("| Property | Value |")
        lines.append("|---|---|")
        if mech.density is not None:
            lines.append(f"| Density | {mech.density} g/cm³ |")
        if mech.youngs_modulus is not None:
            lines.append(f"| Young's Modulus | {mech.youngs_modulus} GPa |")
        if mech.yield_strength is not None:
            lines.append(f"| Yield Strength | {mech.yield_strength} MPa |")
        if mech.tensile_strength is not None:
            lines.append(f"| Tensile Strength | {mech.tensile_strength} MPa |")
        if mech.poissons_ratio is not None:
            lines.append(f"| Poisson's Ratio | {mech.poissons_ratio} |")
        if mech.hardness_vickers is not None:
            lines.append(f"| Hardness (Vickers) | {mech.hardness_vickers} |")
        lines.append("")

    # Thermal
    therm = mat.properties.thermal
    if therm.melting_point is not None:
        lines.append("## Thermal Properties")
        lines.append("")
        lines.append("| Property | Value |")
        lines.append("|---|---|")
        if therm.melting_point is not None:
            lines.append(f"| Melting Point | {therm.melting_point} °C |")
        if therm.thermal_conductivity is not None:
            lines.append(f"| Thermal Conductivity | {therm.thermal_conductivity} W/(m·K) |")
        if therm.specific_heat is not None:
            lines.append(f"| Specific Heat | {therm.specific_heat} J/(kg·K) |")
        lines.append("")

    # PBR
    pbr = mat.properties.pbr
    lines.append("## PBR (Rendering)")
    lines.append("")
    lines.append("| Property | Value |")
    lines.append("|---|---|")
    lines.append(f"| Base Color | `{pbr.base_color}` |")
    lines.append(f"| Metallic | {pbr.metallic} |")
    lines.append(f"| Roughness | {pbr.roughness} |")
    if pbr.ior != 1.5:
        lines.append(f"| IOR | {pbr.ior} |")
    if pbr.transmission > 0:
        lines.append(f"| Transmission | {pbr.transmission} |")
    lines.append("")

    # Vis
    if mat.vis.source_id:
        lines.append("## Visual (mat-vis)")
        lines.append("")
        lines.append(f"| Field | Value |")
        lines.append(f"|---|---|")
        lines.append(f"| Source ID | `{mat.vis.source_id}` |")
        if mat.vis.finish:
            lines.append(f"| Finish | {mat.vis.finish} |")
        if mat.vis.finishes:
            finishes = ", ".join(mat.vis.finishes.keys())
            lines.append(f"| Available Finishes | {finishes} |")
        lines.append("")

    # Composition
    if mat.composition:
        lines.append("## Composition")
        lines.append("")
        lines.append("| Element | Fraction |")
        lines.append("|---|---|")
        for el, frac in sorted(
            mat.composition.items(),
            key=lambda x: -(getattr(x[1], "nominal_value", x[1])),
        ):
            nominal = getattr(frac, "nominal_value", frac)
            stddev = getattr(frac, "std_dev", None)
            if stddev and stddev > 0:
                lines.append(f"| {el} | {nominal:.4g} ± {stddev:.4g} |")
            else:
                lines.append(f"| {el} | {nominal:.4g} |")
        lines.append("")

    return "\n".join(lines)


def _fmt_density(mat) -> str:
    d = mat.properties.mechanical.density
    return f"{d} g/cm³" if d else "—"


def _fmt_yield(mat) -> str:
    y = mat.properties.mechanical.yield_strength
    return f"{y} MPa" if y else "—"


def _fmt_tensile(mat) -> str:
    t = mat.properties.mechanical.tensile_strength
    return f"{t} MPa" if t else "—"


def _fmt_modulus(mat) -> str:
    e = mat.properties.mechanical.youngs_modulus
    return f"{e} GPa" if e else "—"


def _fmt_melting(mat) -> str:
    mp = mat.properties.thermal.melting_point
    return f"{mp} °C" if mp is not None else "—"


def _fmt_k(mat) -> str:
    k = mat.properties.thermal.thermal_conductivity
    return f"{k} W/m·K" if k else "—"


def _fmt_ior(mat) -> str:
    n = mat.properties.optical.refractive_index
    return f"{n}" if n else "—"


# Per-category columns chosen by audience
# Metals: mechanical + thermal (engineering primary)
# Plastics: density + thermal (operating temp matters)
# Scintillators: density + optical (physics primary)
# Gases/liquids: density + thermal
# Default: density + mechanical
_CATEGORY_COLUMNS: dict[str, list[tuple[str, callable]]] = {
    "metals": [
        ("Density", _fmt_density),
        ("Yield", _fmt_yield),
        ("Tensile", _fmt_tensile),
        ("E", _fmt_modulus),
        ("T_melt", _fmt_melting),
    ],
    "plastics": [
        ("Density", _fmt_density),
        ("Yield", _fmt_yield),
        ("T_melt", _fmt_melting),
        ("k", _fmt_k),
    ],
    "scintillators": [
        ("Density", _fmt_density),
        ("n (IOR)", _fmt_ior),
    ],
    "ceramics": [
        ("Density", _fmt_density),
        ("E", _fmt_modulus),
        ("T_melt", _fmt_melting),
    ],
    "electronics": [
        ("Density", _fmt_density),
    ],
    "liquids": [
        ("Density", _fmt_density),
        ("n (IOR)", _fmt_ior),
    ],
    "gases": [
        ("Density", _fmt_density),
    ],
}


def _category_index(category: str, materials: list, has_thumbnails: bool) -> str:
    """Generate markdown index for a category — columns tuned per audience."""
    lines = [f"# {category.title()}", ""]
    lines.append(f"{len(materials)} materials. Click a name for full properties.")
    lines.append("")

    cols = _CATEGORY_COLUMNS.get(category, [("Density", _fmt_density)])

    # Header
    header = ["Material"]
    if has_thumbnails:
        header.append("Preview")
    header.extend(c[0] for c in cols)
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")

    # Rows
    for mat, key in materials:
        row = [f"[{mat.name}]({key}.md)"]
        if has_thumbnails:
            if (THUMBS_EXIST := (mat.vis.source_id is not None)):
                row.append(f"![]({'thumbs/' + key + '.png'})")
            else:
                row.append("—")
        for _, fmt in cols:
            row.append(fmt(mat))
        lines.append("| " + " | ".join(row) + " |")

    lines.append("")
    return "\n".join(lines)


def _root_index(categories: dict[str, list]) -> str:
    """Generate root README with links to categories."""
    lines = ["# Material Catalog", ""]
    lines.append("Auto-generated from py-mat TOML data + mat-vis textures.")
    lines.append("")
    lines.append("| Category | Materials |")
    lines.append("|---|---|")
    for cat, mats in categories.items():
        lines.append(f"| [{cat.title()}]({cat}/README.md) | {len(mats)} |")
    lines.append("")
    return "\n".join(lines)


def generate(output_dir: Path, skip_thumbnails: bool = False) -> None:
    """Generate the full catalog."""
    output_dir.mkdir(parents=True, exist_ok=True)
    all_materials = load_all()

    # Group by category (from the TOML key hierarchy)
    from pymat import _CATEGORY_BASES
    categories: dict[str, list] = {}

    for category, base_keys in _CATEGORY_BASES.items():
        mats_in_cat = []
        for key in base_keys:
            mat = all_materials.get(key)
            if mat:
                mats_in_cat.append((mat, key))
                # Also add children
                for child_key, child_mat in mat._children.items():
                    mats_in_cat.append((child_mat, f"{key}-{child_key}"))
        if mats_in_cat:
            categories[category] = mats_in_cat

    # Fetch thumbnails from mat-vis's thumbnail tier (128px, pre-baked)
    thumb_count = 0
    if not skip_thumbnails:
        for category, mats in categories.items():
            thumb_dir = output_dir / category / "thumbs"
            thumb_dir.mkdir(parents=True, exist_ok=True)
            for mat, key in mats:
                if not mat.vis.source_id:
                    continue
                thumb_path = thumb_dir / f"{key}.png"
                if thumb_path.exists():
                    thumb_count += 1
                    continue
                parts = mat.vis.source_id.split("/", 1)
                if len(parts) != 2:
                    continue
                source, material_id = parts
                thumb_bytes = _fetch_thumbnail(source, material_id)
                if thumb_bytes:
                    thumb_path.write_bytes(thumb_bytes)
                    thumb_count += 1
                    log.info("thumbnail: %s", key)

    has_thumbnails = thumb_count > 0

    # Generate pages
    for category, mats in categories.items():
        cat_dir = output_dir / category
        cat_dir.mkdir(parents=True, exist_ok=True)

        # Category index
        (cat_dir / "README.md").write_text(_category_index(category, mats, has_thumbnails))

        # Per-material pages
        for mat, key in mats:
            thumb_rel = f"thumbs/{key}.png" if (cat_dir / "thumbs" / f"{key}.png").exists() else None
            page = _material_page(mat, thumb_rel, category)
            (cat_dir / f"{key}.md").write_text(page)

    # Root index
    (output_dir / "README.md").write_text(_root_index(categories))

    total_mats = sum(len(m) for m in categories.values())
    print(f"Catalog: {total_mats} materials, {len(categories)} categories, {thumb_count} thumbnails")
    print(f"Output: {output_dir}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", "-o", default="docs/catalog", help="Output directory")
    parser.add_argument("--skip-thumbnails", action="store_true", help="Skip vis texture fetch")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    generate(Path(args.output), skip_thumbnails=args.skip_thumbnails)


if __name__ == "__main__":
    main()
