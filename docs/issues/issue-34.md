---
type: issue
state: closed
created: 2026-04-16T14:43:44Z
updated: 2026-04-17T11:06:08Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/34
comments: 2
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-04-18T04:24:33.700Z
---

# [Issue 34]: [Formalize optional-dependency extras: [cad], [sci], [viz], [matproj], [all]](https://github.com/MorePET/mat/issues/34)

> **NOTE:** Scope collapsed. See
> [comment](https://github.com/MorePET/mat/issues/34#issuecomment-4261546293)
> for the simplified picture.

## Final decision

- `uncertainties` + `periodictable` become **core deps** (not extras)
- `[cad]` removed — build123d depends on mat, not the other way
- `[sci]` removed — uncertainties is small enough for core
- `[viz]` removed — mat-vis client is pure Python, ships in wheel
- `[matproj]` removed — curation-time tool, see #36
- Only remaining extras: `[dev]` (pytest, ruff, etc.)

Net: `pip install mat` → everything works, ~2 MB.

## Acceptance

- [ ] Move uncertainties + periodictable to core dependencies
- [ ] Remove all extras except [dev]
- [ ] Update README install instructions
- [ ] CHANGELOG entry
---

# [Comment #1]() by [gerchowl]()

_Posted on April 16, 2026 at 04:04 PM_

## Simplified extras picture after mat-vis architecture review

The mat-vis design discussion has collapsed most of the extras this issue originally scoped:

**Eliminated extras:**

- **`[cad]`** — `build123d` dependency is *reversed* (they depend on us, not us on them). Not our extra to manage.
- **`[sci]`** — `uncertainties` (~59 KB) and `periodictable` (~800 KB) become **core deps**, not optional. They're tiny and used by the majority of users.
- **`[viz]`** — The mat-vis client is pure Python (~150-300 lines), ships inside the `mat` wheel itself. No `pyarrow`, no DuckDB, no binary deps. Just `urllib.request` + the JSON index + a companion rowmap for HTTP range reads. No extra needed.

**Remaining question:**

- **`[matproj]`** (pymatgen) — This is a curation-time tool, not an install-time dependency for end users. Leaning toward dropping it as an extra entirely (document it as a dev/curation requirement instead).

**Net result:** `pip install mat` gives you everything — physics, scalars, PBR textures, the works. ~2 MB wheel, no extras needed for any standard use case.

**Recommendation:** This issue's scope has largely collapsed. Suggest either closing it or converting it to a single focused task: "make `uncertainties` + `periodictable` core deps and remove `[sci]` extra."

---

# [Comment #2]() by [gerchowl]()

_Posted on April 17, 2026 at 11:06 AM_

Done on `docs/refresh-readme-2.1.0`: periodictable to core, stale extras removed. Only `[dev]` remains. Ships in 2.2.0.

