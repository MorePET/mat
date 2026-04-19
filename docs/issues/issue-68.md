---
type: issue
state: open
created: 2026-04-18T23:01:34Z
updated: 2026-04-18T23:01:34Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/68
comments: 0
labels: question
assignees: none
milestone: 3.1.2 — post-audit follow-ups
projects: none
parent: none
children: none
synced: 2026-04-19T04:44:01.924Z
---

# [Issue 68]: [Should Vis.source_id getter emit DeprecationWarning?](https://github.com/MorePET/mat/issues/68)

## Tier 3 — documentation vs signal choice

\`Vis.source_id\` is described in \`docs/migration/v2-to-v3.md\` and
\`CHANGELOG.md\` as "deprecated" (one term) and "read-only convenience"
(another term).  The setter raises \`AttributeError\`, so writing to it is
the hard-break signal. But the getter reads silently — no
\`DeprecationWarning\` fires — even though the CHANGELOG says it's
deprecated.

## Pick a word

**Option A — emit \`DeprecationWarning\` on getter**. One release of
soft-deprecation signal for anyone reading \`vis.source_id\`, then remove
in 4.0.

**Option B — stop calling it "deprecated"**. Call it what it is: a
read-only compatibility accessor for logs/tests, not deprecated. Update
CHANGELOG wording to "retained read-only".

## Recommendation

**(B)**. py-mat's stated stance is "break cleanly, no deprecation
cycle." If \`source_id\` were truly deprecated we'd delete it. We kept
it *because* it's a useful lossless log format (\`"ambientcg/Metal012"\`
is one line). Stop calling it deprecated; call it a convenience
accessor.

## Fix scope

Update phrasing in:
- \`CHANGELOG.md\` \`[3.1.0]\` → remove "deprecated" for \`source_id\`
- \`docs/migration/v2-to-v3.md\` → same
- \`src/pymat/vis/_model.py\` property docstring

No code change.

## Labels

\`question\` because this is a documentation-language call, not a
behavior change. Re-label \`documentation\` if ready to commit to
option (B).
