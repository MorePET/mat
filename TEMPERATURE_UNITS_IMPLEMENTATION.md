# Temperature-Dependent Properties & Unit Handling with Pint

## Problem Statement

Many material properties are temperature-dependent, but currently stored as single values without:
1. **Reference temperature** - At what temperature is this value valid?
2. **Temperature coefficients** - How does it change with temperature?
3. **Units** - Is melting_point in °C, °F, or K?

### Current State
```python
melting_point = 1450  # What unit? What temperature?
thermal_conductivity = 50  # W/(m·K) - but at what temperature?
density = 8.0  # g/cm³ - but at what temperature?
```

### Temperature-Dependent Properties
- **Density**: Changes with temperature (thermal expansion)
- **Thermal conductivity**: Varies significantly with temperature
- **Young's modulus**: Decreases with temperature
- **Electrical resistivity**: Increases with temperature (metals)
- **Specific heat**: Varies with temperature
- **Yield strength**: Decreases with temperature

## Solution: Pint Integration

**Decision**: Use `pint` library for unit-aware quantities.

### Why Pint?
- ✅ **No scipy dependency** - Lightweight, pure Python
- ✅ **Self-contained** - Has its own unit definitions and conversion rules
- ✅ **Automatic conversions** - `(100 * ureg.degC).to(ureg.kelvin)`
- ✅ **Dimensional checking** - Prevents unit mismatches
- ✅ **Extensible** - Can add custom units/constants
- ✅ **Array support** - Works with numpy (optional)

### How Pint Works
- Pint does **NOT** use `scipy.constants` internally
- Has its own comprehensive unit registry
- Uses conversion graph for unit transformations
- Includes physical constants (speed of light, Planck constant, etc.)

## Implementation Plan

### 1. Add Pint Dependency
```toml
# pyproject.toml
dependencies = [
    "pint>=0.20",
    # ... existing deps
]
```

### 2. Update Property Classes

**Option A: Store as Quantity objects directly**
```python
from pint import UnitRegistry
ureg = UnitRegistry()

@dataclass
class ThermalProperties:
    melting_point: Optional[ureg.Quantity] = None
    thermal_conductivity: Optional[ureg.Quantity] = None
    thermal_conductivity_ref_temp: Optional[ureg.Quantity] = None
    thermal_conductivity_coeff: Optional[float] = None  # 1/K
```

**Option B: Store as (value, unit) and reconstruct**
```python
@dataclass
class ThermalProperties:
    melting_point_value: Optional[float] = None
    melting_point_unit: str = "degC"

    def melting_point(self) -> Optional[ureg.Quantity]:
        if self.melting_point_value is None:
            return None
        return self.melting_point_value * ureg(self.melting_point_unit)
```

### 3. Temperature-Dependent Property Pattern

For properties that vary with temperature:
```python
@dataclass
class ThermalProperties:
    # Reference value at standard temperature
    thermal_conductivity: Optional[ureg.Quantity] = None  # W/(m·K) at T_ref
    thermal_conductivity_ref_temp: Optional[ureg.Quantity] = None  # Default: 20°C
    thermal_conductivity_coeff: Optional[float] = None  # Linear coefficient (1/K)

    def thermal_conductivity_at(self, temp: ureg.Quantity) -> Optional[ureg.Quantity]:
        """Calculate thermal conductivity at given temperature."""
        if self.thermal_conductivity is None:
            return None
        T_ref = self.thermal_conductivity_ref_temp or (20 * ureg.degC)
        coeff = self.thermal_conductivity_coeff or 0.0
        # Linear: k(T) = k(T_ref) * (1 + coeff * (T - T_ref))
        delta_T = temp.to(T_ref.units) - T_ref
        return self.thermal_conductivity * (1 + coeff * delta_T.magnitude)
```

### 4. TOML Serialization

Pint `Quantity` objects don't serialize directly. Store as value + unit:

```toml
[steel.thermal]
melting_point_value = 1450
melting_point_unit = "degC"

thermal_conductivity_value = 50.0
thermal_conductivity_unit = "W/(m*K)"
thermal_conductivity_ref_temp_value = 20.0
thermal_conductivity_ref_temp_unit = "degC"
thermal_conductivity_coeff = 0.001
```

Then reconstruct in loader:
```python
if "melting_point_value" in data:
    value = data["melting_point_value"]
    unit = data.get("melting_point_unit", "degC")
    props.melting_point = value * ureg(unit)
```

### 5. Standard Units

Define standard units for consistency:

```python
STANDARD_UNITS = {
    "temperature": "degC",  # or "K" for physics
    "density": "g/cm^3",
    "pressure": "MPa",
    "stress": "MPa",
    "modulus": "GPa",
    "thermal_conductivity": "W/(m*K)",
    "specific_heat": "J/(kg*K)",
    "thermal_expansion": "1/K",
    "resistivity": "ohm*m",
    "conductivity": "S/m",
}
```

## Files to Modify

1. **`src/pymat/properties.py`**
   - Update property classes to use `Quantity` or (value, unit) pattern
   - Add temperature-dependent property methods

2. **`src/pymat/loader.py`**
   - Handle TOML deserialization of unit-aware values
   - Reconstruct `Quantity` objects from value + unit

3. **`pyproject.toml`**
   - Add `pint>=0.20` dependency

4. **`src/pymat/core.py`**
   - Update `Material` class to handle `Quantity` objects
   - Add helper methods for temperature-dependent calculations

5. **`tests/test_properties.py`** (new)
   - Test unit conversions
   - Test temperature-dependent calculations
   - Test TOML serialization/deserialization

## Example Usage

```python
from pint import UnitRegistry
from pymat import Material

ureg = UnitRegistry()

# Create material with unit-aware properties
steel = Material(
    name="Steel",
    thermal={
        "melting_point": 1450 * ureg.degC,
        "thermal_conductivity": 50 * ureg.W / (ureg.m * ureg.K),
        "thermal_conductivity_ref_temp": 20 * ureg.degC,
        "thermal_conductivity_coeff": 0.001  # 1/K
    }
)

# Automatic unit conversions
mp_k = steel.properties.thermal.melting_point.to(ureg.kelvin)
mp_f = steel.properties.thermal.melting_point.to(ureg.degF)

# Temperature-dependent calculations
k_at_100C = steel.properties.thermal.thermal_conductivity_at(100 * ureg.degC)
```

## Key Considerations

1. **Backward Compatibility**: Existing TOML files without units should assume standard units
2. **Default Units**: Define sensible defaults (e.g., temperatures in °C, SI units for others)
3. **Density Calculation**: Use thermal expansion coefficient to calculate density at different temperatures
4. **Factory Functions**: Keep `water(temperature_c)`, `air(temp, pressure)` - they already handle units
5. **Performance**: Pint is fast, but consider caching conversions if needed

## Testing Checklist

- [ ] Unit conversions work correctly
- [ ] Temperature-dependent calculations are accurate
- [ ] TOML serialization/deserialization preserves units
- [ ] Backward compatibility with existing TOML files
- [ ] Dimensional checking prevents unit mismatches
- [ ] Integration with build123d (mass calculations use correct density units)

## References

- Pint documentation: https://pint.readthedocs.io/
- Pint GitHub: https://github.com/hgrecco/pint
- Current pymat version: v1.0.0
- Location: `/Users/larsgerchow/Projects/py-mat`
