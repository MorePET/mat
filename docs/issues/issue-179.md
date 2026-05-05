---
type: issue
state: open
created: 2026-05-04T21:23:02Z
updated: 2026-05-04T21:23:02Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/179
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-05-05T04:54:10.235Z
---

# [Issue 179]: [search: fuzzy threshold too tight — heavy typos return empty](https://github.com/MorePET/mat/issues/179)

**DX gap surfaced via MCP UX testing.**

\`pymat.search(\"Stinless Stl 304\")\` returns \`[]\`. Both \`i\`s elided + \"Stl\" abbreviation. A human's intent is obvious; an agent's mistype is recoverable.

## Repro

\`\`\`python
>>> pymat.search(\"Stinless Stl 304\")
[]
>>> pymat.search(\"Stainless 304\")
[...]   # works
>>> pymat.search(\"Stnls Stl\")
[]      # fails
\`\`\`

## Fix

Inspect \`src/pymat/search.py\` — the current scorer / threshold. Two non-mutually-exclusive options:

1. Lower the score threshold for short queries (current threshold over-penalizes when \`len(query) < ~10\`).
2. Add abbreviation tolerance (\`Stl\` → \`Steel\`, \`Alu\` → \`Aluminum\`) for engineering vocabulary. Probably overkill; option 1 is enough.

## Why it matters

The MCP \`get_material\` tool already returns \`{\"error\": ..., \"did_you_mean\": [...]}\` envelopes — but the suggestion list is built from \`pymat.search\`, so an empty search makes the envelope unhelpful. Agents end up with no recovery path.

Catches the same class of UX hole as #178 (data gaps); fix is on the search side.
