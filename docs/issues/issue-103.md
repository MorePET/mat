---
type: issue
state: open
created: 2026-05-04T12:32:45Z
updated: 2026-05-04T12:32:45Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/103
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-05-05T04:54:35.596Z
---

# [Issue 103]: [Vis.override: tier-only change wrongly clears _finish](https://github.com/MorePET/mat/issues/103)

**Bug.** Found by independent implementation review of 3.6.0.

\`vis.override(tier=\"2k\")\` on a Vis with \`_finish=\"polished\"\` clears \`_finish\` to \`None\`, even though tier is orthogonal to which finish-map entry was selected.

### Trigger
\`\`\`python
v = Vis(source=\"ambientcg\", material_id=\"Metal012\", tier=\"1k\",
        finishes={\"polished\": {\"source\": \"ambientcg\", \"id\": \"Metal012\"}})
v.finish = \"polished\"
v2 = v.override(tier=\"2k\")
assert v2.finish == \"polished\"  # FAILS — clears to None
\`\`\`

### Cause
\`src/pymat/vis/_model.py\` — \`override\` clears \`_finish\` whenever any of the 3 identity fields change. Should restrict to \`source\` / \`material_id\` (the fields a finish entry pins).

### Fix
Compute \`finish_invalidating = bool({\"source\", \"material_id\"} & set(deltas where value differs))\`, use that gate instead of \`identity_changing\`.
