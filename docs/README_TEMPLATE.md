# pymat

A hierarchical material library for CAD applications with build123d integration.

## Features

- **Hierarchical Materials**: Chain grades, tempers, treatments, and vendors
- **Property Inheritance**: Children inherit parent properties unless overridden
- **Lazy Loading**: Categories load on first access
- **TOML Data Storage**: Easy-to-edit material definitions
- **build123d Integration**: Apply materials to shapes with automatic mass calculation
- **PBR Rendering**: Physically-based rendering properties for visualization
- **periodictable Integration**: Auto-fill density from chemical formulas
- **Factory Functions**: Temperature/pressure-dependent materials (water, air, saline)
- **Separation of Concerns**: Optical properties (physics) separate from PBR (visualization)

## Installation

```bash
# With uv (recommended)
uv add git+https://github.com/MorePET/py-mat.git@latest

# Or specify version
uv add git+https://github.com/MorePET/py-mat.git@v1.0.0
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

```python
from pymat import enrich_from_periodictable

material = Material(name="Aluminum Oxide", formula="Al2O3")
enrich_from_periodictable(material)
print(material.density)  # ~3.95 g/cm³
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

## Links

- **GitHub**: https://github.com/MorePET/py-mat
- **Issues**: https://github.com/MorePET/py-mat/issues
