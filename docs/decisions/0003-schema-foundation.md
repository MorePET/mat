# 0003 — Schema foundation: provenance, uncertainty, and T-curves

**Status:** Proposed (consolidated from 3 parallel reviews 2026-05-05)
**Issues:** [#150](https://github.com/MorePET/mat/issues/150) (`_sources`), [#149](https://github.com/MorePET/mat/issues/149) (`_stddev`), [#148](https://github.com/MorePET/mat/issues/148) (`_curve`), [#174](https://github.com/MorePET/mat/issues/174) (data-policy + license CI)

## Context

The Properties Schema Expansion milestone proposes three additions that gate every downstream data-source pull and material entry: provenance metadata, per-property uncertainty, and temperature-dependent curves. Three independent reviews (architecture, backwards-compat, test/CI) converged on the same overall shape but disagreed on three specific points. This ADR records the resolved design.

## Decisions

### 1. `_sources` is a sidecar `dict[str, Source]` on `Material`

Provenance is metadata *about* a value, not part of the value. Inlining it (e.g. making `density` a wrapper with `.value` and `.source`) breaks ~50 call sites that do arithmetic on `mat.density` — including `core.py:403` (`density / 1000`), `clients/python/pymat-mcp/src/pymat_mcp/tools.py:300` (`compute_mass`), and the `*_qty` Pint properties. Not worth the refactor.

```python
@dataclass(frozen=True)
class Source:
    citation: str            # BibTeX key
    kind: str                # "doi" | "qid" | "handbook" | "vendor" | "measured"
    ref: str                 # "10.x/y" | "Q123" | "ASM Handbook v2 p.62" | URL
    license: str             # CC0 | PD-USGov | CC-BY-4.0 | CC-BY-SA-4.0 | proprietary-reference-only | unknown
    note: Optional[str] = None

@dataclass
class Material:
    ...
    _sources: dict[str, Source] = field(default_factory=dict)  # keyed by dotted path
```

**Access API:**

```python
mat.source_of("mechanical.density")   # → Source | None  (resolves _default fallback)
mat.cite("mechanical.density")        # → BibTeX string
mat.cite("density")                   # → same; short-alias lookup table
mat.cite()                            # → all entries used by this material, dedup'd
```

**Inheritance:** child material's `_sources` overlays parent's (`parent._sources | self._sources`), parsed at load time. `_default` is a per-material fallback when no per-property entry exists.

`mat.density` stays a `float`. The `mat.density.source` accessor proposed in #150 is **rejected** — it is a direct break of the established API.

### 2. `_curve` lives inside its property group; access via `mat.at(T=...)` view AND existing `_at(T)` methods

```toml
[aluminum.al6061.thermal]
thermal_conductivity_value = 167
thermal_conductivity_unit = "W/(m*K)"
thermal_conductivity_curve = { temps_K = [77, 200, 293, 400, 500], values = [105, 150, 167, 180, 192] }
```

**Storage:** new optional sibling field `<prop>_curve: Optional[TempCurve] = None` on the relevant dataclass. Scalar field stays a scalar — never promote it to a callable (would break `properties.py:148` `if self.thermal_conductivity is None`, all `*_qty` math, and JSON serialization in the MCP tools).

**Access API (additive, both supported):**

```python
mat.properties.thermal.thermal_conductivity_at(233 * ureg.K)   # existing — unchanged
mat.at(T=233 * ureg.K).thermal.thermal_conductivity_qty        # new view, dispatches to interp
```

**Precedence inside `_at(T)` methods:** curve > legacy `_ref_temp + _coeff` linear > scalar. The legacy `thermal_conductivity_ref_temp` / `_coeff` stays in-place; under the hood the loader rewrites them into a synthetic 2-point `_curve` so `properties.py` has one interpolation path. Eventually the legacy fields can be removed in a separate ADR.

**Edge cases (PIN these):**

| Case | Behavior |
|---|---|
| T at exact knot | Return knot value (no float drift) |
| T between knots | Linear interp via `numpy.interp` |
| T below min knot | **Clamp** to min knot value, log debug |
| T above max knot | **Clamp** to max knot value, log debug |
| Curve with 1 point | Return that constant for any T |
| Curve absent | Fall back to scalar |
| Unsorted / mismatched-length arrays | **Raise at load time**, not query time |

Applies to: thermal_conductivity, specific_heat, thermal_expansion, youngs_modulus, yield_strength, resistivity, refractive_index, light_yield, decay_time.

### 3. `_stddev`: standardize on existing in-value ufloat form; loader sugar accepts sibling syntax

`loader.py:_parse_value` already supports `{nominal, stddev}` and `{min, max}` dicts via `uncertainties.ufloat`. Adding sibling fields (`density_stddev: Optional[float]`) means parallel mechanisms, dataclass bloat across every property, and silently-dropped-key risk per `loader.py:118-167` (HIGH-2).

**Canonical form:**

```toml
light_yield = { nominal = 33000, stddev = 1500 }
light_yield_unit = "ph/MeV"
```

**Sibling sugar (loader rewrites at parse time):**

```toml
light_yield_value = 33000
light_yield_stddev = 1500     # → folded into ufloat by loader; not a dataclass field
light_yield_unit = "ph/MeV"
```

**Double-specification (in-value `stddev` AND sibling `_stddev`) is a hard error** — `ValueError` at load time, not silent precedence.

#149 is satisfied without parallel mechanisms or dataclass bloat. ⚠️ This is a deviation from the literal issue text ("Add `<prop>_stddev` siblings to dataclasses"). Recorded here for human ack before #149 is closed.

### 4. License gate (#174): standalone script + ratchet file, NOT pytest

`scripts/check_licenses.py` (stdlib only, mirrors `scripts/generate_readme.py`):

```python
ALLOWED = {"CC0", "PD-USGov", "CC-BY-4.0", "CC-BY-SA-4.0", "proprietary-reference-only"}
RATCHET = ".github/license-ratchet.txt"   # paths exempted until #175 sweep completes

errors = []
for toml_path in DATA_DIR.glob("*.toml"):
    if str(toml_path) in load_ratchet():
        continue
    for mat_key, source_key, src in walk_sources(tomllib.load(open(toml_path, "rb"))):
        lic = src.get("license")
        if lic is None:
            errors.append(f"{toml_path}:{mat_key}._sources.{source_key} missing license")
        elif lic == "unknown":
            errors.append(f"{toml_path}:{mat_key}._sources.{source_key} license=unknown — resolve before merge")
        elif lic not in ALLOWED:
            errors.append(f"{toml_path}:{mat_key}._sources.{source_key} license={lic!r} not in allow-list")
sys.exit(1 if errors else 0)
```

Wired into:
- `.pre-commit-config.yaml` as a `local` hook (mirrors `readme-from-tests` pattern)
- `.github/workflows/ci.yml` as a `check-licenses` job in the `summary.needs` list

`.github/license-ratchet.txt` lists every TOML path exempted during the audit window. **#175's PR description must include "delete `.github/license-ratchet.txt`" as the final step** — ratchet is shorter-lived than a feature flag and prevents the worst failure mode (forgetting to flip a flag back on).

### 5. Loader changes (consolidated)

In `src/pymat/loader.py`:

- **`update_properties` (line 119)**: add `if key.startswith("_"): continue` to make existing implicit behavior explicit. Prevents silent no-op when contributors put `_sources` inside a property group.
- **`update_properties` (around line 167)**: branch — if `key.endswith("_curve")` and value is `dict` with `temps_K` + `values`, validate (sorted, equal length) and `setattr(prop_obj, key, TempCurve(...))`. Else if `key.endswith("_stddev")`, fold with sibling base value into a ufloat; raise if base is already a ufloat.
- **`_resolve_material_node` (after line 256)**: pop `_sources` from `data`, parse each entry into a `Source`, assign to `material._sources` with parent-overlay inheritance.
- **No changes** to `_parse_value`, `_parse_composition`, `STANDARD_UNITS`, the Pint layer, or any property dataclass beyond adding `<prop>_curve: Optional[TempCurve] = None` fields.

In `tests/test_toml_integrity.py`:
- Extend `_KNOWN_LEAF_KEYS` to recognize `_sources` at material-node level.
- Document that `_curve` and `_stddev` keys must live INSIDE a property group section, not at material-node level.

### 6. ufloat→float coercion at boundaries

Once #149 lands and contributors actually populate uncertainties, downstream callers that cross a JSON or build123d boundary will see `ufloat` where they expect `float`:

- `core.py:403` (`density_g_mm3 = ... .density / 1000`) → `obj.mass = ufloat(...)`
- `clients/python/pymat-mcp/src/pymat_mcp/tools.py:300` (`mass_g = volume_mm3 * (density / 1000.0)`) → `json.dumps` fails

**Fix in #149 PR:** small helper `_nominal(x: float | ufloat) -> float` that does `float(getattr(x, "nominal_value", x))`, applied at both boundary call sites. Add a regression test that `compute_mass` accepts a ufloat-density material and returns a plain float.

## PR sequence

1. **#150** `_sources` table + `Source` dataclass + `Material._sources` + loader changes + `mat.cite()` + `mat.source_of()` — does NOT add license enforcement (the field is parsed but not validated)
2. **#149** loader sugar for `_stddev` siblings + `ValueError` on double-spec + ufloat→float boundary helper
3. **#148** `TempCurve` dataclass + `<prop>_curve` fields + interpolation in `_at(T)` methods + `mat.at(T=...)` view + legacy `_ref_temp+_coeff` rewrite
4. **#174** `docs/data-policy.md` + CONTRIBUTING update + `scripts/check_licenses.py` + ratchet file + pre-commit + CI wiring (this is the gate that turns `license` from "parsed" into "required")

Each PR is its own merge; #174 must land before #175 (audit) so the gate exists before the corpus is swept.

## Cross-cutting regression test

Extend `tests/test_toml_integrity.py::test_no_deprecation_warnings_on_full_load` to also snapshot `(material_key, populated_property_count)` for every material across all categories, asserting the count is identical to a checked-in baseline `tests/baselines/property_counts.json`. If `_sources` leaks into properties, or `_stddev` siblings get treated as unknown properties, or `_curve` dicts get setattr'd as raw dicts, the count drifts and one test catches it.

## Out of scope

- Refactoring the Pint Quantity layer
- Changing `mat.density` from `float` to a wrapper
- Promoting any scalar property to a callable
- Per-source bibliographic styles beyond DOI/QID/handbook/vendor/measured (deferred to a future ADR if needed)

## Reviewer notes

This ADR consolidates three independent fresh-perspective reviews. Specific deviations from the literal issue text:

- **#149**: do NOT add `density_stddev` etc. as dataclass fields. Loader sugar only. (Architecture + compat agreed; tester accepted.)
- **#150**: do NOT add `mat.density.source` attribute. Use `mat.source_of("mechanical.density")` and `mat.cite("density")`. (Compat blocking concern; architect agreed.)
- **#148**: do NOT promote `mat.thermal_conductivity` to a callable. Curve evaluation only via `_at(T)` methods and the new `mat.at(T=...)` view. (Compat blocking concern; architect agreed.)
