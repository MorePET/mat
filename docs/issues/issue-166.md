---
type: issue
state: open
created: 2026-05-04T19:56:02Z
updated: 2026-05-04T19:56:02Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/166
comments: 0
labels: data-source
assignees: none
milestone: Data Sources & Licensing
projects: none
parent: none
children: none
synced: 2026-05-05T04:54:14.967Z
---

# [Issue 166]: [Integrate MIL-HDBK-5J (public domain) — aerospace alloy mechanicals](https://github.com/MorePET/mat/issues/166)

MIL-HDBK-5J (2003, last free edition) is US-gov public domain; later MMPDS-02+ is commercial (Battelle) — **off-limits**. Available on everyspec.com.

Coverage: A-basis / B-basis design allowables (UTS, yield, fatigue, modulus, density) for aerospace metals: Al 2024/6061/7075, Ti-6Al-4V, stainless 17-4PH/15-5PH, Inconel 625/718, magnesium AZ91, beryllium.

Action: extract single values per material into TOMLs; cite as `source = "mil-hdbk-5j:p<page>"`. **Mark MMPDS-02+ as off-limits** in CONTRIBUTING.md to avoid accidental ingestion.

Reference: https://everyspec.com/MIL-HDBK/MIL-HDBK-0001-0099/MIL_HDBK_5J_139/
