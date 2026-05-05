---
type: issue
state: open
created: 2026-05-04T19:56:17Z
updated: 2026-05-04T19:56:17Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/174
comments: 0
labels: data-source
assignees: none
milestone: Data Sources & Licensing
projects: none
parent: none
children: none
synced: 2026-05-05T04:54:11.863Z
---

# [Issue 174]: [Data-licensing policy: add docs/data-policy.md + CONTRIBUTING update](https://github.com/MorePET/mat/issues/174)

Land the data licensing policy as a CONTRIBUTING.md section (or separate `docs/data-policy.md`). Draft text in conversation notes covers:

- Core legal distinction (facts vs expression; *Feist*; EU sui generis database right)
- Per-source verdicts table (CC0 / PD-USGov / CC-BY-4.0 / proprietary-reference-only)
- MUST and MUST-NOT contributor rules
- Required `license` field on `_sources` entries (depends on #150)
- "Common knowledge" handling
- LICENSES-DATA.md top-level file with attributions for CC-BY sources

Allowed `license` values: `CC0`, `PD-USGov`, `CC-BY-4.0`, `CC-BY-SA-4.0`, `proprietary-reference-only`, `unknown` (must resolve before merge).

Depends on #150 (`_sources` schema).
