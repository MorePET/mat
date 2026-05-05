---
type: issue
state: open
created: 2026-05-04T19:56:18Z
updated: 2026-05-04T19:56:19Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/175
comments: 0
labels: data-source
assignees: none
milestone: Data Sources & Licensing
projects: none
parent: none
children: none
synced: 2026-05-05T04:54:11.544Z
---

# [Issue 175]: [One-time audit: classify existing TOML sources by license](https://github.com/MorePET/mat/issues/175)

Before formalizing the policy, audit current state:

1. Extract every source reference from existing TOMLs (inline comments + any informal source fields) into a flat list
2. Classify each against the per-source verdicts table (#data-policy issue): `safe` / `cite-only` / `replace`
3. Flag for replacement: any value whose **only** source is CRC, ASM, vendor datasheet, or paywalled paper *and* was bulk-imported from a table (not single-fact extraction)
4. Backfill the new `_sources` schema with `license` tags; default `unknown` where unclear; open follow-up issues per material
5. Add CI check rejecting `license = "unknown"` or missing license field on new `_sources` entries

Depends on #150 (`_sources` schema) and the data-policy doc.
