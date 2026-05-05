---
type: issue
state: open
created: 2026-05-04T12:32:55Z
updated: 2026-05-04T12:32:55Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/104
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-05-05T04:54:35.243Z
---

# [Issue 104]: [Vis.override: caller-supplied finishes= dict not deep-copied](https://github.com/MorePET/mat/issues/104)

**Bug.** Found by independent implementation review of 3.6.0.

\`override\` deep-copies \`self.finishes\` (via \`deepcopy(self)\`) but stores any caller-supplied \`finishes=\` delta by reference. Diverges from the docstring promise and from \`merge_from_toml\`.

### Trigger
\`\`\`python
caller_dict = {\"matte\": {\"source\": \"x\", \"id\": \"y\"}}
v2 = v.override(finishes=caller_dict)
caller_dict[\"matte\"][\"id\"] = \"TAMPERED\"
assert v2.finishes[\"matte\"][\"id\"] == \"y\"  # FAILS — observes \"TAMPERED\"
\`\`\`

### Fix
Inside the loop that applies remaining deltas, deepcopy the value when \`k == \"finishes\"\`. Or route the whole \`finishes=\` path through \`Vis.from_toml({\"finishes\": ...})\` like \`merge_from_toml\` does (re-validates the slashed-string guard too).
