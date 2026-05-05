---
type: issue
state: open
created: 2026-05-04T19:50:20Z
updated: 2026-05-04T19:50:20Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/150
comments: 0
labels: enhancement, schema
assignees: none
milestone: Properties Schema Expansion
projects: none
parent: none
children: none
synced: 2026-05-05T04:54:21.161Z
---

# [Issue 150]: [Schema: `[<material>._sources]` provenance table](https://github.com/MorePET/mat/issues/150)

Replace ad-hoc inline-comment provenance with structured `[<material>._sources]` keyed by property path. Underscore prefix already filtered by `loader.py:280` — no loader change required. See conversation design notes for worked aluminum 6061 example. Includes `_default` fallback, disagreement table, and citation styles for DOI / Wikidata QID / handbook ref / vendor URL / measured-in-house. Adds `mat.density.source` Python accessor and `mat.cite()` BibTeX export. Opt-in per material; no flag-day rewrite.
