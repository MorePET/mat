---
type: issue
state: closed
created: 2026-05-04T19:56:20Z
updated: 2026-05-06T21:07:39Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/176
comments: 1
labels: data-source
assignees: none
milestone: Data Sources & Licensing
projects: none
parent: none
children: none
synced: 2026-05-07T05:23:44.460Z
---

# [Issue 176]: [Tooling: `mat.cite()` API + LICENSES-DATA.md generator](https://github.com/MorePET/mat/issues/176)

Build a small `mat.sources` shim that:
- Resolves `mat.density.source` to a `Source` dataclass
- Emits BibTeX-style citation block via `mat.cite()` for any material/property
- Generates top-level `LICENSES-DATA.md` from all `_sources` entries (de-duplicated by source ID, listing required attributions for CC-BY entries)

Run the LICENSES-DATA.md generator in CI on every PR — fails if a CC-BY source is referenced but not attributed.

Depends on #150.
---

# [Comment #1]() by [gerchowl]()

_Posted on May 6, 2026 at 09:07 PM_

Both deliverables shipped earlier in the schema-foundation series:
- mat.cite() landed in #182 (#150)
- LICENSES-DATA.md auto-generator is scripts/check_licenses.py --emit-attributions from #184 (#174)

No remaining scope. Closing as duplicate.

