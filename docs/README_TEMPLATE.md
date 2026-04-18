# pymat

A hierarchical material library for CAD applications and Monte Carlo particle transport, with build123d integration.

## Features

- **Hierarchical Materials**: Chain grades, tempers, treatments, and vendors
- **Property Inheritance**: Children inherit parent properties unless overridden
- **Lazy Loading**: Categories load on first access
- **TOML Data Storage**: Easy-to-edit material definitions
- **Formula Parsing + Molar Mass**: Computed from the chemical formula via `Material.molar_mass`, with fractional stoichiometry (`Lu1.8Y0.2SiO5`) and dopant suffix stripping (`LYSO:Ce`). Atomic weights mirror the Rust `rs-materials` crate for Python ↔ Rust parity.
- **build123d Integration**: Apply materials to shapes with automatic mass calculation
- **PBR Rendering**: Physically-based rendering properties for visualization
- **periodictable Integration**: Auto-fill composition from chemical formulas for compounds; auto-fill density for pure elements
- **Factory Functions**: Temperature/pressure-dependent materials (water, air, saline)
- **Separation of Concerns**: Optical properties (physics) separate from PBR (visualization)
- **Python 3.10 – 3.13 supported**, core library depends only on `pint`

## Installation

```bash
# From PyPI (recommended)
pip install py-materials
# or: uv add py-materials

# From the main branch (development)
pip install git+https://github.com/MorePET/mat.git@main

# With optional extras
pip install "py-materials[periodictable]"    # auto-fill from chemical formulas
pip install "py-materials[build123d]"        # build123d Shape integration (Python <= 3.12)
pip install "py-materials[all]"              # everything above
```

## Quick Start

{{EXAMPLES_COMPREHENSIVE}}

## Material Categories

- **Metals**: Stainless steel, aluminum, copper, tungsten, lead, titanium, brass
- **Scintillators**: LYSO, BGO, NaI, CsI, LaBr3, PWO, plastic scintillators
- **Plastics**: PEEK, Delrin, Ultem, PTFE, ESR, Nylon, PLA, ABS, PETG, TPU, PMMA, PE, PC
- **Ceramics**: Alumina, Macor, Zirconia, Glass (borosilicate, fused silica, BK7)
- **Electronics**: FR4, Rogers, Kapton, copper PCB, solder, ferrite
- **Liquids**: Water, Heavy Water, Mineral Oil, Glycerol, Silicone Oil
- **Gases**: Air, Nitrogen, Oxygen, Argon, CO₂, Helium, Hydrogen, Neon, Xenon, Methane, Vacuum

## Property Groups

Each material can have properties organized in these domains:

- **Mechanical**: density, Young's modulus, yield strength, hardness
- **Thermal**: melting point, thermal conductivity, expansion coefficient
- **Electrical**: resistivity, conductivity, dielectric constant
- **Optical**: refractive index, transparency, light yield (PHYSICS - measured values)
- **PBR**: base color, metallic, roughness (VISUALIZATION - rendering appearance)
- **Manufacturing**: machinability, printability, weldability
- **Compliance**: RoHS, REACH, food-safe, biocompatible
- **Sourcing**: cost, availability, suppliers

## Advanced Usage

### Custom Materials

Create materials using property group dictionaries:

```python
from pymat import Material

my_material = Material(
    name="Custom Alloy",
    mechanical={
        "density": 8.1,
        "youngs_modulus": 200,
        "yield_strength": 450
    },
    pbr={
        "base_color": (0.7, 0.7, 0.75, 1.0),
        "metallic": 1.0,
        "roughness": 0.4
    }
)
```

### Loading from TOML

```python
from pymat import load_toml

materials = load_toml("my_materials.toml")
my_material = materials["my_material"]
```

### Enrichment from Chemical Formulas

`enrich_from_periodictable` reads the material's `formula`, populates
the `composition` dict (element → atom count), and sets the density
**only for pure elements** — compound density is not derivable from
`periodictable`'s dataset and requires a crystallographic source like
Materials Project. Molar mass is always available regardless, via the
computed `Material.molar_mass` property (see the Quick Start).

```python
from pymat import Material, enrich_from_periodictable

# Pure element — density is set
iron = Material(name="Iron", formula="Fe")
enrich_from_periodictable(iron)
assert iron.density == 7.874            # set from periodictable
assert iron.molar_mass == 55.85         # computed from formula

# Compound — composition is set, density is not
alumina = Material(name="Alumina", formula="Al2O3")
enrich_from_periodictable(alumina)
assert alumina.composition == {"Al": 2, "O": 3}
assert alumina.molar_mass == 101.96     # computed from formula
assert alumina.density is None          # use enrich_from_matproj for compounds
```

## Optical vs PBR Properties

**Important**: Understand the distinction between physics and visualization:

- **Optical Properties** (`optical.*`): Measured/calculated physical values
  - `transparency`: % light transmission (measured)
  - `refractive_index`: optical property (measured)
  - `light_yield`: scintillator brightness (measured)

- **PBR Properties** (`pbr.*`): Rendering/visualization parameters
  - `base_color`: RGBA values (0-1) for display
  - `transmission`: how transparent it LOOKS in renders
  - `metallic`: surface finish appearance
  - `roughness`: surface roughness appearance

These can differ intentionally! A material might be physically transparent (95% optical transmission) but rendered opaque (0% pbr transmission) for CAD clarity.

## License

MIT

## Design Decisions (ADRs)

Non-trivial architectural decisions live under `docs/decisions/` as
lightweight ADRs. They explain why the code is shaped the way it is
and the conditions under which the decision should be revisited.

- [ADR-0001 — Derived chemistry properties live on `Material`](docs/decisions/0001-derived-chemistry-properties-live-on-material.md)
  (why `molar_mass` is a computed `@property`, not a stored field)

## Links

- **GitHub**: https://github.com/MorePET/mat
- **Issues**: https://github.com/MorePET/mat/issues
- **PyPI**: https://pypi.org/project/py-materials/
- **Rust crate** (`rs-materials`): https://crates.io/crates/rs-materials
