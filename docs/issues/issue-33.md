---
type: issue
state: open
created: 2026-04-16T14:43:19Z
updated: 2026-04-17T11:06:31Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/33
comments: 1
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-04-18T04:24:34.106Z
---

# [Issue 33]: [Elemental composition + scalar properties: support ranges / uncertainties (ufloat)](https://github.com/MorePET/mat/issues/33)

## Context

Surfaced during the build123d material-system roadmap discussion
([gumyr/build123d#598](https://github.com/gumyr/build123d/issues/598)):
real-world material data comes with **ranges**, not scalars.

- **Alloy grade specs** define windows (6063 Si: 0.2–0.6%, Fe: 0–0.35%,
  Cu: 0–0.1%, ...). Collapsing these to midpoints throws away the
  spec.
- **Material certificates** report measured values with uncertainties
  (density = 8.03 ± 0.02 g/cm³ on a cert). Nuclear-medicine /
  particle-transport workflows need these for dose uncertainty
  propagation.
- **Scalar mechanical/thermal/optical properties** have the same
  shape — yield strength, thermal conductivity, refractive index all
  carry measurement error in primary sources.

Current schema stores everything as `float`:

- `composition: Dict[str, float]` (`src/pymat/core.py:93`)
- `properties.mechanical.yield_strength: float` (and siblings)

## Proposal

**Accept both scalar and range/uncertainty values throughout, with
a dict-canonical serialization and lazy `uncertainties` import.**

### Storage (TOML-serializable, no new deps required at read-time)

```toml
# Scalar (current — unchanged)
[aluminum.a6061]
composition = { Al = 0.972, Mg = 0.01, Si = 0.006, ... }

# With uncertainty / range — dict form
[aluminum.a6063.composition]
Si = { nominal = 0.4, min = 0.2, max = 0.6 }
Fe = { nominal = 0.175, min = 0.0, max = 0.35 }
```

Accepted value forms at load time:

- `0.4` — plain scalar (today).
- `{ nominal = x, stddev = s }` — measurement with std dev.
- `{ nominal = x, min = a, max = b }` — spec window (asymmetric ok).
- `{ min = a, max = b }` — range without declared nominal → mean.

### Runtime behavior

- **Core install** (`pip install mat`) — ranges collapse to nominal;
  access is always `.nominal_value` + optional `.bounds`. No math on
  uncertainties; downstream arithmetic treats values as scalars.
- **`pip install mat[sci]`** — pulls `uncertainties` (~59 KB, pure
  Python, zero deps). Loader returns `ufloat` objects; arithmetic
  propagates errors correctly (`density * volume` keeps the error
  bar).

Same pattern mat already uses for `pint`: the serialized form is
explicit, the rich in-memory representation is optional.

## Footprint

`uncertainties==3.2.3`:
- 59 KB wheel, pure Python, zero runtime deps.
- Python ≥ 3.8.

Trivially cheap as a `[sci]` extra; overkill to force on every user.

## Out of scope (filed separately)

Extras refactor (`[cad]`, `[sci]`, `[viz]`, `[matproj]`) — see
companion issue. This issue is just about the data layer.

## Acceptance

- [ ] Loader accepts scalar OR `{nominal, stddev}` OR `{min, max}`
      dict forms for composition entries.
- [ ] Same for scalar properties in the mechanical / thermal /
      optical / electrical groups (pick a starting subset — density,
      yield_strength, refractive_index are the highest-value).
- [ ] `Material.composition` returns `dict[str, float]` on bare
      install, `dict[str, ufloat]` when `[sci]` is installed.
- [ ] At least one documented example using a real grade spec
      (6063 Al or 316L stainless).
- [ ] Tests covering both import-paths.

## References

- Thread: [gumyr/build123d#598](https://github.com/gumyr/build123d/issues/598)
  — @jwagenet's split-schema proposal, @gerchowl's 6063 range
  example.
- `uncertainties` docs: https://pythonhosted.org/uncertainties/
---

# [Comment #1]() by [gerchowl]()

_Posted on April 17, 2026 at 11:06 AM_

Deferred from 2.2.0 to 2.3.0. The `[sci]` extra was removed (periodictable moved to core), but uncertainties itself hasn't been added to core deps yet. The data-layer work (range/ufloat support in TOML + loader) is the main effort.

