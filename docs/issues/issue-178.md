---
type: issue
state: open
created: 2026-05-04T21:22:49Z
updated: 2026-05-04T21:22:49Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/178
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-05-05T04:54:10.529Z
---

# [Issue 178]: [data: 'Aluminum 6061' should resolve (currently only 'Aluminum 6061-T6' exists)](https://github.com/MorePET/mat/issues/178)

**Data gap surfaced via MCP UX testing.**

\`pymat[\"Aluminum 6061\"]\` raises KeyError. Only \`a6061 → \"Aluminum 6061-T6\"\` is registered. From an agent / human's perspective the obvious request is \"6061\" (the alloy designation); \"6061-T6\" is the temper-baked form.

## Repro

\`\`\`python
import pymat
m = pymat[\"Aluminum 6061\"]   # KeyError
m = pymat[\"6061\"]             # KeyError too
m = pymat[\"a6061\"]            # OK — but unobvious
\`\`\`

## Fix options

- Add \`Aluminum 6061\` as a parent of \`Aluminum 6061-T6\`, mirroring the \`stainless → s304\` pattern (where the alloy designation lives at parent level and tempers/grades hang below)
- Or accept \`6061\` as a grade-only lookup (\`pymat.search(\"6061\", exact=True)\` should hit)

Same problem likely applies to \`7075\` vs \`7075-T6\`, \`6063\`, etc.
