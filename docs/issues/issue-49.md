---
type: issue
state: open
created: 2026-04-18T16:48:41Z
updated: 2026-04-18T16:48:41Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/49
comments: 0
labels: enhancement
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-04-19T04:44:06.265Z
---

# [Issue 49]: [ci: reconcile CHANGELOG bullet style between release-please and pymarkdown](https://github.com/MorePET/mat/issues/49)

## Problem

Release-please emits \`-\` (dash) list markers in generated CHANGELOG entries. The project's \`pymarkdown\` pre-commit hook (running in fix mode, \`.pymarkdown\` uses default \`md004.style\`) normalizes bullets to \`*\` (asterisk) to match existing historical entries. Result: every Release PR triggers a 100+ line pymarkdown auto-fix diff, which the pre-commit hook flags as a CI failure.

First surfaced on PR #48 (2.1.1 release). Worked around by committing the pymarkdown fix directly to the release-please branch, but that will recur on every subsequent release.

## Root cause

- Release-please's changelog template uses \`-\` bullets and offers no built-in toggle to change this.
- Pymarkdown \`md004\` in \`.pymarkdown\` has no explicit \`style\` config, so it defaults to \`consistent\` / \`asterisk\` depending on file content.
- Pre-commit hook runs with \`args: ["fix"]\` → auto-modifies files → reports failure when changes are made.

## Fix options

1. **Canonicalize to \`-\` everywhere** (preferred — aligns with release-please output):
   - Mass-rewrite \`CHANGELOG.md\` from \`*\` to \`-\`
   - Set \`.pymarkdown\` → \`plugins.md004.style: "dash"\`
   - No more per-release churn
2. **Canonicalize to \`*\` everywhere**: release-please output still writes \`-\` → pymarkdown still rewrites → CI still fails. Doesn't work unless we also change pre-commit to \`scan\` mode (option 3).
3. **Switch pre-commit from \`fix\` to \`scan\`**: reports issues but doesn't modify files. Broader impact — affects all markdown lint behavior, not just CHANGELOG.

## Recommendation

(1). Single follow-up PR after #48 merges:
- \`CHANGELOG.md\` — batch replace \`^\* \` → \`- \` (178 lines)
- \`.pymarkdown\` — add \`"md004": { "style": "dash" }\`
- One commit, \`ci: canonicalize CHANGELOG bullet style to dash\`

Refs: #48
