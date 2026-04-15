# mat

Material database for CAD and Monte Carlo particle transport.

Shared TOML data files with language-specific packages:

| Package | Language | Registry | Import |
|---------|----------|----------|--------|
| [py-materials](https://pypi.org/project/py-materials/) | Python | PyPI | `import pymat` |
| [rs-materials](mat-rs/) | Rust | crates.io | `use rs_materials::...` |

## Features

### Python (py-materials)

- **Hierarchical Materials**: Chain grades, tempers, treatments, and vendors
- **Property Inheritance**: Children inherit parent properties unless overridden
- **Lazy Loading**: Categories load on first access
- **build123d Integration**: Apply materials to shapes with automatic mass calculation
- **PBR Rendering**: Physically-based rendering properties for visualization
- **periodictable Integration**: Auto-fill density from chemical formulas
- **Factory Functions**: Temperature/pressure-dependent materials (water, air, saline)

### Rust (rs-materials)

- **TOML Database Reader**: Loads all 7 material categories with property inheritance
- **Formula Parser**: Fractional stoichiometry (`Lu1.8Y0.2SiO5` → element/count pairs)
- **Mass/Atom Fraction Conversion**: Bidirectional with roundtrip correctness
- **Scintillator Properties**: Light yield, decay time, emission peak, refractive index
- **Thread-Safe**: `Send + Sync` for `Arc` sharing in multi-threaded transport engines

## Installation

### Python

```bash
# With uv (recommended)
uv add git+https://github.com/MorePET/mat.git@latest

# Or specify version
uv add git+https://github.com/MorePET/mat.git@v1.0.0
```

### Rust

```toml
[dependencies]
rs-materials = { git = "https://github.com/MorePET/mat.git" }
```

## Quick Start

## Creating Materials

        Create materials with convenient parameters:

```python
from pymat import Material

        # Using convenience parameters
        steel = Material(name="Steel", density=7.85)
        # With visualization color
        aluminum = Material(name="Aluminum", density=2.7, color=(0.88, 0.88, 0.88))
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
            pbr={"base_color": (0.75, 0.75, 0.77, 1.0), "metallic": 1.0}
        )        assert steel.properties.pbr.metallic == 1.0
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
        steel.apply_to(box)        assert box.color is not None
```

## Chainable Material Hierarchy

        Build hierarchies with grades, tempers, and treatments:

```python
from pymat import Material

        # Create base stainless steel
        stainless = Material(
            name="Stainless Steel",
            density=8.0,
            thermal={"melting_point": 1450}
        )

        # Add grade
        s304 = stainless.grade_("304", name="SS 304", mechanical={"yield_strength": 170})
        # Add treatment
        passivated = s304.treatment_("passivated", name="SS 304 Passivated")        assert passivated.density == 8.0  # Inherited through chain
```

## Direct Material Access

        Load materials and access them directly from the library:

```python
from pymat import stainless, aluminum, lyso

        # Direct access to materials
        s316L = stainless.s316L
        al6061 = aluminum.a6061
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
            pbr={"transmission": 0.8}  # Rendering: how transparent it looks
        )

        # Physics properties (measured)
        # Visualization properties (rendering)        assert glass.properties.pbr.transmission == 0.8
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
            pbr={"base_color": (0.0, 1.0, 1.0, 0.85), "transmission": 0.85}
        )        assert lyso_crystal.properties.pbr.transmission == 0.85
```

## Temperature-Dependent Materials

        Use factory functions for materials with properties that depend on external parameters:

```python
from pymat.factories import water

        # Water at different temperatures
        cold_water = water(4)      # Max density
        room_water = water(20)     # Room temperature
        hot_water = water(80)      # Heated
        # Verify realistic values        assert 0.95 < hot_water.density < 0.98
```

## Air at Different Conditions

        Create air material at specific temperature and pressure:

```python
from pymat.factories import air

        sea_level = air(15, 1.0)      # 15°C, 1 atm
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
        # Seawater (3.5% NaCl) at 20°C
        seawater = saline(3.5, temperature_c=20)
        # Higher concentration = higher density
        assert seawater.density > phantom.density
```

## Loading Metal Materials

        Access various metal materials from the metals category:

```python
from pymat import stainless, aluminum, copper

        # Stainless steel variants
        s304 = stainless.s304
        s316L = stainless.s316L
        # Aluminum alloys
        al6061 = aluminum.a6061
        al7075 = aluminum.a7075
        # Copper
        copper_material = copper
        assert copper_material.density == 8.96
```

## Plastic Materials

        Access plastic materials for 3D printing and engineering:

```python
from pymat import peek, pla, pc, pmma

        # Engineering plastics
        # 3D printing plastics
        # Transparent plastics        assert pc.properties.optical.transparency == 89
```

## Scintillator Crystals

        Access scintillator materials for radiation detectors:

```python
from pymat import lyso, bgo, nai

        # LYSO crystal
        # BGO crystal
        # NaI crystal
        assert nai.properties.optical.light_yield == 38000
```

## Gas Materials

        Access gases for simulation and detector design:

```python
from pymat import air, nitrogen, argon, helium, xenon

        # Common gases at STP
        # Detector gases
        assert argon.properties.compliance.radiation_resistant == True
```

## Property Inheritance

        Child materials inherit properties from parents unless overridden:

```python
from pymat import Material

        # Create material hierarchy
        root = Material(
            name="Base",
            density=7.8,
            thermal={"melting_point": 1500, "thermal_conductivity": 50}
        )

        grade1 = root.grade_("G1", mechanical={"yield_strength": 400})
        # Override inherited property
        grade2 = root.grade_("G2", thermal={"melting_point": 1600})
        assert grade2.properties.thermal.melting_point == 1600  # Overridden
```

## Automatic Mass Calculation

        Materials with density automatically calculate shape mass:

```python
from build123d import Box
        from pymat import stainless, aluminum

        # 10x10x10 mm³ box = 1000 mm³ = 1 cm³
        steel_box = Box(10, 10, 10)
        stainless.apply_to(steel_box)

        # Density = 8.0 g/cm³, Volume = 1 cm³ → Mass = 8.0 g
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
        from pymat import stainless, aluminum, lyso

        # Create shapes
        steel_part = Box(10, 10, 10)
        al_part = Box(10, 10, 10)
        crystal = Box(10, 10, 10)

        # Apply materials
        stainless.apply_to(steel_part)
        aluminum.apply_to(al_part)
        lyso.apply_to(crystal)

        # Verify colors are set
        # Colors should differ        assert crystal.color != steel_part.color
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

- **GitHub**: https://github.com/MorePET/mat
- **Issues**: https://github.com/MorePET/mat/issues
