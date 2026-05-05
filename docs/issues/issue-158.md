---
type: issue
state: open
created: 2026-05-04T19:55:47Z
updated: 2026-05-04T19:55:47Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/158
comments: 0
labels: data-source
assignees: none
milestone: Data Sources & Licensing
projects: none
parent: none
children: none
synced: 2026-05-05T04:54:18.014Z
---

# [Issue 158]: [Integrate Wikidata (CC0) — SPARQL bulk fetch for elements + compounds](https://github.com/MorePET/mat/issues/158)

Wikidata QIDs are CC0 — redistribute freely with QID citation. Coverage: ~all 118 elements, common compounds, some plastics; patchy for engineering alloys.

Key property QIDs:
- P2054 density, P2101 melting point, P2102 boiling point
- P2153 Young's modulus, P2068 thermal conductivity
- P2055 electrical resistivity, P2614 refractive index
- P2056 heat capacity, P1088 Mohs hardness

Endpoint: `https://query.wikidata.org/sparql`. Pattern:
```sparql
SELECT ?material ?density WHERE {
  ?material wdt:P31/wdt:P279* wd:Q11427 ; wdt:P2054 ?density
}
```

Action: write a script in `scripts/enrich_from_wikidata.py` (already exists for base metals) extending coverage. Tag `_sources` entries with `license = "CC0"` and `wikidata = "Q..."`.
