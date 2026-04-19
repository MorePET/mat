"""
End-to-end example: Material with physics + PBR, Three.js JSON output.

Demonstrates the `pymat.pbr` Protocol-based integration from ADR-0002.
Works with both the lite in-tree backend (no extra deps) and the rich
`threejs-materials` backend (install `pip install py-materials[pbr]`).

Run:
    python examples/pbr_integration.py

Outputs:
    - Physics properties to stdout
    - Three.js MeshPhysicalMaterial dict to stdout
    - Writes the JSON to `examples/output/` for downstream viewer
      consumption

This example deliberately avoids pulling in `build123d` or
`ocp_vscode` — it's the minimal py-materials-only demo. For the full
integration with build123d's `Shape.material` and live rendering in
`ocp_vscode`, see the matching example on the build123d fork:
`gerchowl/build123d@feature/pymat-material-integration:examples/pbr_material_pymat.py`,
which composes all three libraries.
"""

from __future__ import annotations

import json
from pathlib import Path

from pymat import Material
from pymat.pbr import PbrSource

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def build_steel_with_lite_pbr() -> Material:
    """
    Build a `Material` using only the native in-tree PBR backend.

    This path works with `pip install py-materials` — no extras
    needed. Physics users get a usable material with basic PBR
    scalar values; no texture maps.
    """
    return Material(
        name="Stainless Steel 304",
        density=8.0,
        formula="Fe",  # dominant element, approximated for molar mass
        mechanical={"youngs_modulus": 193, "yield_strength": 170},
        thermal={"melting_point": 1450, "thermal_conductivity": 15.1},
        pbr={
            "base_color": (0.75, 0.75, 0.77, 1.0),
            "metallic": 1.0,
            "roughness": 0.35,
        },
    )


def build_steel_with_rich_pbr() -> Material | None:
    """
    Build a `Material` using the rich `threejs-materials` backend.

    Requires `pip install py-materials[pbr]`. Downloads the
    "Stainless Steel Brushed" MaterialX material from
    matlib.gpuopen.com on first run and caches it for subsequent
    runs. Returns None if the extra is not installed.
    """
    try:
        from pymat.pbr import PbrProperties  # type: ignore[attr-defined]
    except ImportError:
        return None

    return Material(
        name="Brushed Stainless Steel",
        density=8.0,
        formula="Fe",
        mechanical={"youngs_modulus": 193, "yield_strength": 170},
        thermal={"melting_point": 1450, "thermal_conductivity": 15.1},
        pbr_source=PbrProperties.from_gpuopen("Stainless Steel Brushed"),
    )


def report(material: Material, label: str) -> dict:
    """Print a summary of a Material and return its Three.js dict."""
    print(f"\n=== {label} ===")
    print(f"  name:          {material.name}")
    print(f"  density:       {material.density} g/cm³")
    print(f"  formula:       {material.formula}")
    print(f"  molar mass:    {material.molar_mass} g/mol")
    print(f"  pbr_source set: {material.pbr_source is not None}")

    three_js = material.to_three_js_material_dict()
    print("  Three.js dict:")
    print(json.dumps(three_js, indent=4, sort_keys=True))

    # Sanity: whichever backend is active, it conforms to the Protocol.
    source: PbrSource = (
        material.pbr_source if material.pbr_source is not None else material.properties.pbr
    )
    assert isinstance(source, PbrSource), (
        f"Active PBR backend {type(source).__name__} does not conform to PbrSource"
    )
    return three_js


def main() -> int:
    lite_steel = build_steel_with_lite_pbr()
    lite_dict = report(lite_steel, "Lite backend (zero extra deps)")
    (OUTPUT_DIR / "steel_lite.json").write_text(
        json.dumps(lite_dict, indent=2, sort_keys=True) + "\n"
    )

    rich_steel = build_steel_with_rich_pbr()
    if rich_steel is not None:
        rich_dict = report(rich_steel, "Rich backend (threejs-materials)")
        (OUTPUT_DIR / "steel_rich.json").write_text(
            json.dumps(rich_dict, indent=2, sort_keys=True) + "\n"
        )
    else:
        print(
            "\n=== Rich backend skipped ===\n"
            "  Install `pip install py-materials[pbr]` to fetch MaterialX\n"
            "  materials from ambientcg / polyhaven / gpuopen / physicallybased.info."
        )

    print(f"\nJSON written to {OUTPUT_DIR.resolve()}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
