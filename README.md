# pymat

A hierarchical material library for CAD applications and Monte Carlo particle transport, with build123d integration.

## Features

- **Hierarchical Materials**: Chain grades, tempers, treatments, and vendors
- **Property Inheritance**: Children inherit parent properties unless overridden
- **Lazy Loading**: Categories load on first access
- **TOML Data Storage**: Easy-to-edit material definitions
- **Formula Parsing + Molar Mass**: Computed from the chemical formula via `Material.molar_mass`, with fractional stoichiometry (`Lu1.8Y0.2SiO5`) and dopant suffix stripping (`LYSO:Ce`). Atomic weights mirror the Rust `rs-materials` crate for Python ↔ Rust parity.
- **build123d Integration**: Apply materials to shapes with automatic mass calculation
- **PBR Rendering via `material.vis`**: Scalars (roughness, metallic, base_color) and lazy-fetched textures from [mat-vis][mat-vis]
- **periodictable Integration**: Auto-fill composition from chemical formulas for compounds; auto-fill density for pure elements
- **Factory Functions**: Temperature/pressure-dependent materials (water, air, saline)
- **Separation of Concerns**: Optical properties (physics) separate from `vis` (visualization)
- **Python 3.10 – 3.13 supported**, core library depends only on `pint`

[mat-vis]: https://github.com/MorePET/mat-vis

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

## Creating Materials

Create materials with convenient parameters:

```python
from pymat import Material

# Using convenience parameters
steel = Material(name="Steel", density=7.85)
assert steel.density == 7.85

# With visualization color
aluminum = Material(name="Aluminum", density=2.7, color=(0.88, 0.88, 0.88))
assert aluminum.vis.base_color[:3] == (0.88, 0.88, 0.88)

# With formula
lyso = Material(name="LYSO", formula="Lu1.8Y0.2SiO5", density=7.1)
assert lyso.formula == "Lu1.8Y0.2SiO5"
```

## Using Property Groups

Define multiple properties at once using property group dictionaries:

```python
from pymat import Material

# Define steel with multiple property groups
steel = Material(
    name="Stainless Steel 304",
    mechanical={"density": 8.0, "youngs_modulus": 193, "yield_strength": 170},
    thermal={"melting_point": 1450, "thermal_conductivity": 15.1},
    vis={"base_color": (0.75, 0.75, 0.77, 1.0), "metallic": 1.0},
)

assert steel.properties.mechanical.density == 8.0
assert steel.properties.mechanical.youngs_modulus == 193
assert steel.properties.thermal.melting_point == 1450
assert steel.vis.metallic == 1.0
```

## Applying Materials to Shapes

Apply materials to build123d shapes for visualization and mass calculation:

```python
from build123d import Box

from pymat import Material

# Create material
steel = Material(name="Steel", density=7.85, color=(0.7, 0.7, 0.7))

# Create shape and apply material
box = Box(10, 10, 10)
steel.apply_to(box)

assert box.material.name == "Steel"
assert box.mass > 0
assert box.color is not None
```

## Computing Molar Mass

`Material.molar_mass` is a computed property that parses the
chemical formula and looks up each element's atomic weight.
It supports fractional stoichiometry and strips dopant
notation like `LYSO:Ce` so doped-crystal aliases work
unchanged.

Nothing is stored — it recomputes on each access. That's
intentional: molar mass is definitionally derived from
`formula` and should never drift. Missing or unknown-element
formulas return `None`. See
`docs/decisions/0001-derived-chemistry-properties-live-on-material.md`.

```python
from pymat import Material

# Pure element
iron = Material(name="Iron", formula="Fe")
assert iron.molar_mass == 55.85

# Simple compound
alumina = Material(name="Alumina", formula="Al2O3")
assert abs(alumina.molar_mass - 101.96) < 0.01

# Fractional stoichiometry (a PET-scanner scintillator)
lyso = Material(name="LYSO", formula="Lu1.8Y0.2SiO5")
assert abs(lyso.molar_mass - 440.87) < 0.1

# Dopant suffix is stripped
lyso_ce = Material(name="LYSO:Ce", formula="Lu1.8Y0.2SiO5:Ce")
assert lyso_ce.molar_mass == lyso.molar_mass

# Unit-aware companion accessor (Pint Quantity)
qty = iron.molar_mass_qty
assert qty.to("kg/mol").magnitude == pytest.approx(0.05585, abs=1e-4)

# Gracefully returns None when no formula is set
unknown = Material(name="Unknown Alloy")
assert unknown.molar_mass is None
```

## Low-level: `pymat.elements`

For callers that don't need a full `Material` object —
e.g. quick stoichiometry calculations inside a Monte Carlo
transport loop — the low-level `pymat.elements` module
exposes the same machinery directly.

The `ATOMIC_WEIGHT` table is a line-for-line mirror of the
Rust `rs-materials` crate, so Python and Rust Monte Carlo
engines get identical molar masses byte-for-byte.

```python
from pymat.elements import (
    ATOMIC_WEIGHT,
    compute_molar_mass,
    parse_formula,
)

# Atomic weight lookup
assert ATOMIC_WEIGHT["Fe"] == 55.85
assert ATOMIC_WEIGHT["Lu"] == 175.0

# Formula parser: fractional stoichiometry + repeat handling
counts = parse_formula("Lu1.8Y0.2SiO5")
assert counts == {"Lu": 1.8, "Y": 0.2, "Si": 1.0, "O": 5.0}

# Molar mass directly from a formula string
assert abs(compute_molar_mass("Al2O3") - 101.96) < 0.01
```

## Chainable Material Hierarchy

Build hierarchies with grades, tempers, and treatments:

```python
from pymat import Material

# Create base stainless steel
stainless = Material(name="Stainless Steel", density=8.0, thermal={"melting_point": 1450})

# Add grade
s304 = stainless.grade_("304", name="SS 304", mechanical={"yield_strength": 170})
assert s304.density == 8.0  # Inherited
assert s304.properties.mechanical.yield_strength == 170

# Add treatment
passivated = s304.treatment_("passivated", name="SS 304 Passivated")
assert (
    passivated.path == "stainless_steel.304.passivated"
)  # name -> lowercase with underscores
assert passivated.density == 8.0  # Inherited through chain
```

## Direct Material Access

Load materials and access them directly from the library:

```python
from pymat import aluminum, lyso, stainless

# Direct access to materials
s316L = stainless.s316L
assert s316L.grade == "316L"

al6061 = aluminum.a6061
assert al6061.density == 2.7  # Inherited from aluminum

lyso_crystal = lyso
assert "LYSO" in lyso_crystal.name
```

## Physics Properties vs Visualization

Understand the difference between measured optical properties (physics)
and rendering properties (visualization):

```python
from pymat import Material

# Create transparent material
glass = Material(
    name="Optical Glass",
    color=(0.9, 0.9, 0.9, 0.8),  # Visual: 80% opaque white
    optical={"transparency": 95, "refractive_index": 1.517},  # Physics: 95% transmission
    vis={"transmission": 0.8},  # Rendering: how transparent it looks
)

# Physics properties (measured)
assert glass.properties.optical.transparency == 95
assert glass.properties.optical.refractive_index == 1.517

# Visualization properties (rendering)
assert glass.vis.base_color[3] == 0.8  # Alpha
assert glass.vis.transmission == 0.8
```

## Scintillator-Specific Properties

Define detector crystals with optical physics properties:

```python
from pymat import Material

lyso_crystal = Material(
    name="LYSO:Ce Crystal",
    density=7.1,
    optical={
        "refractive_index": 1.82,
        "transparency": 92,
        "light_yield": 32000,  # photons/MeV
        "decay_time": 41,  # ns
        "emission_peak": 420,  # nm
    },
    vis={"base_color": (0.0, 1.0, 1.0, 0.85), "transmission": 0.85},
)

assert lyso_crystal.properties.optical.light_yield == 32000
assert lyso_crystal.properties.optical.decay_time == 41
assert lyso_crystal.vis.transmission == 0.85
```

## Temperature-Dependent Materials

Use factory functions for materials with properties that depend on external parameters:

```python
from pymat.factories import water

# Water at different temperatures
cold_water = water(4)  # Max density
room_water = water(20)  # Room temperature
hot_water = water(80)  # Heated

assert cold_water.density > room_water.density
assert room_water.density > hot_water.density

# Verify realistic values
assert 0.99 < cold_water.density < 1.01
assert 0.95 < hot_water.density < 0.98
```

## Air at Different Conditions

Create air material at specific temperature and pressure:

```python
from pymat.factories import air

sea_level = air(15, 1.0)  # 15°C, 1 atm
high_altitude = air(15, 0.5)  # 15°C, 0.5 atm (5500m)

assert sea_level.density > high_altitude.density
```

## Saline Solutions

Create solutions with specific concentration and temperature:

```python
from pymat.factories import saline, water

# Physiological saline at body temperature
phantom = saline(0.9, temperature_c=37)
# Saline is slightly denser than pure water at same temperature
pure_water_37 = water(37)
assert phantom.density > pure_water_37.density

# Seawater (3.5% NaCl) at 20°C
seawater = saline(3.5, temperature_c=20)
# Higher concentration = higher density
assert seawater.density > phantom.density
```

## Loading Metal Materials

Access various metal materials from the metals category:

```python
from pymat import aluminum, copper, stainless

# Stainless steel variants
s304 = stainless.s304
s316L = stainless.s316L
assert s304.density == s316L.density  # Same base density

# Aluminum alloys
al6061 = aluminum.a6061
_ = aluminum.a7075
assert al6061.density == 2.7

# Copper
copper_material = copper
assert copper_material.density == 8.96
```

## Plastic Materials

Access plastic materials for 3D printing and engineering:

```python
from pymat import pc, peek, pla, pmma

# Engineering plastics
assert peek.properties.manufacturing.print_nozzle_temp == 360

# 3D printing plastics
assert pla.properties.manufacturing.printable_fdm is True

# Transparent plastics
assert pmma.properties.optical.transparency == 92
assert pc.properties.optical.transparency == 89
```

## Scintillator Crystals

Access scintillator materials for radiation detectors:

```python
from pymat import bgo, lyso, nai

# LYSO crystal
assert lyso.properties.optical.light_yield == 32000
assert lyso.properties.optical.refractive_index == 1.82

# BGO crystal
assert bgo.properties.optical.light_yield == 8500

# NaI crystal
assert nai.properties.optical.light_yield == 38000
```

## Gas Materials

Access gases for simulation and detector design:

```python
from pymat import air, argon, helium, nitrogen, xenon

# Common gases at STP
assert 0.0012 < air.density < 0.0013  # g/cm³
assert nitrogen.density > helium.density  # Helium is lightest
assert xenon.density > argon.density  # Heavier noble gases

# Detector gases
assert argon.properties.compliance.radiation_resistant is True
```

## Property Inheritance

Child materials inherit properties from parents unless overridden:

```python
from pymat import Material

# Create material hierarchy
root = Material(
    name="Base", density=7.8, thermal={"melting_point": 1500, "thermal_conductivity": 50}
)

grade1 = root.grade_("G1", mechanical={"yield_strength": 400})
assert grade1.density == 7.8  # Inherited
assert grade1.properties.mechanical.yield_strength == 400  # New property
assert grade1.properties.thermal.melting_point == 1500  # Inherited

# Override inherited property
grade2 = root.grade_("G2", thermal={"melting_point": 1600})
assert grade2.properties.thermal.melting_point == 1600  # Overridden
```

## Automatic Mass Calculation

Materials with density automatically calculate shape mass:

```python
from build123d import Box

from pymat import aluminum, stainless

# 10x10x10 mm³ box = 1000 mm³ = 1 cm³
steel_box = Box(10, 10, 10)
stainless.apply_to(steel_box)

# Density = 8.0 g/cm³, Volume = 1 cm³ → Mass = 8.0 g
assert 7.9 < steel_box.mass < 8.1

# Aluminum box
al_box = Box(10, 10, 10)
aluminum.apply_to(al_box)

# Density = 2.7 g/cm³ → Mass = 2.7 g
assert 2.6 < al_box.mass < 2.8
```

## Material Visualization

Materials render with appropriate colors for visualization:

```python
from build123d import Box

from pymat import aluminum, lyso, stainless

# Create shapes
steel_part = Box(10, 10, 10)
al_part = Box(10, 10, 10)
crystal = Box(10, 10, 10)

# Apply materials
stainless.apply_to(steel_part)
aluminum.apply_to(al_part)
lyso.apply_to(crystal)

# Verify colors are set
assert steel_part.color is not None
assert al_part.color is not None
assert crystal.color is not None

# Colors should differ
assert steel_part.color != al_part.color
assert crystal.color != steel_part.color
```

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
- **Vis** (on `material.vis`): base_color, metallic, roughness, ior, transmission, textures, finishes — visual/rendering layer, fetches PBR textures from mat-vis on demand
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
    vis={
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

## Optical vs Visual Properties

**Important**: Understand the distinction between physics and visualization:

- **Optical Properties** (`properties.optical.*`): Measured/calculated physical values
  - `transparency`: % light transmission (measured)
  - `refractive_index`: optical property (measured)
  - `light_yield`: scintillator brightness (measured)

- **Visual Properties** (`material.vis.*`): Rendering/visualization parameters
  - `base_color`: RGBA values (0-1) for display
  - `transmission`: how transparent it LOOKS in renders
  - `metallic`: surface finish appearance
  - `roughness`: surface roughness appearance
  - `source` + `material_id` + `tier`: mat-vis appearance identity (since 3.1; the three fields match mat-vis-client's positional-arg signature — see [ADR-0002](docs/decisions/0002-vis-owns-identity-client-exposed.md))
  - `textures`: PBR texture maps (lazy-fetched from mat-vis once `source` + `material_id` are set)
  - `finishes`: named alternate looks (e.g. `brushed` / `polished` / `oxidized`) — each entry is an inline `{source, id}` table
  - `mtlx` (property): MaterialX document accessor (`.xml`, `.export(path)`, `.original`)
  - `client` (property): escape hatch to the shared `MatVisClient` singleton — for any operation not material-keyed

These can differ intentionally! A material might be physically transparent (95% optical transmission) but rendered opaque (0% vis.transmission) for CAD clarity.

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
