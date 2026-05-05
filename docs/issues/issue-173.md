---
type: issue
state: open
created: 2026-05-04T19:56:15Z
updated: 2026-05-04T19:56:15Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/173
comments: 0
labels: data-source
assignees: none
milestone: Data Sources & Licensing
projects: none
parent: none
children: none
synced: 2026-05-05T04:54:12.237Z
---

# [Issue 173]: [Off-limits sources — document in CONTRIBUTING.md](https://github.com/MorePET/mat/issues/173)

Sources that are **NOT** redistributable. Cite as reference only; never paste tables, figures, or scanned values:

- **CRC Handbook** (Taylor & Francis) — proprietary
- **ASM Handbook** (ASM International) — proprietary
- **MatWeb** — proprietary aggregator, no redistribution
- **MMPDS-02+** (Battelle, post-MIL-HDBK-5J) — commercial
- **Vendor datasheets**: Saint-Gobain/Luxium, Eljen, Furukawa, C&A, Kuraray, Rogers, Isola — proprietary, all-rights-reserved
- **CIE booklets** — sold; use [colour-science](https://www.colour-science.org/) (BSD-3) instead for re-licensed colorimetric data
- **Paywalled academic papers** — cite DOI; never embed figures/tables

Action: add a "Sources off-limits for redistribution" section to CONTRIBUTING.md (or new docs/data-policy.md). Include guidance: "Re-typing a single value from a vendor datasheet with attribution = fact extraction (acceptable); copying tables = infringement risk."
