---
type: issue
state: open
created: 2026-04-18T18:49:40Z
updated: 2026-04-18T18:49:40Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/56
comments: 0
labels: enhancement
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-04-19T04:44:05.595Z
---

# [Issue 56]: [ci: post-process release-please PRs to preserve rich CHANGELOG content](https://github.com/MorePET/mat/issues/56)

## Problem

Release-please's auto-generated CHANGELOG section is sparse — one bullet per commit subject. When contributors curate rich content under \`## Unreleased\` (per Keep-a-Changelog convention), release-please's PR opens a \`## [X.Y.Z]\` section ABOVE Unreleased with the sparse content, leaving Unreleased orphaned.

This bit us on #53 (3.0.0) — the rich migration table, mat-vis-client cache-clear note, and per-feature breakdown were curated under Unreleased but release-please's auto-generated section showed only \"3.0 vis cutover — properties.pbr removed, .vis canonical, mat-vis-client 0.4.x (#52)\" as a single line. Manual edit before merge restored it.

## Goal

**Zero manual CHANGELOG editing per release.** Whatever lives under \`## Unreleased\` at the time of the Release PR becomes the content of the new versioned section automatically.

## Proposed: small post-process workflow

Triggers on \`pull_request: types: [opened, synchronize]\` filtered to \`head: release-please--*\`. Steps:

1. Read \`## Unreleased\` block from \`CHANGELOG.md\` on the PR branch.
2. If non-empty:
   a. Replace release-please's auto-generated \`## [X.Y.Z] (DATE)\` section with \`## [X.Y.Z] - DATE\` followed by the Unreleased rich content.
   b. Remove the now-empty \`## Unreleased\` heading (or reset it to empty for the next cycle).
3. Force-push to the release-please branch using the RELEASE_APP token (so downstream CI fires).

## Tradeoffs

**Pro:** Zero recurring manual work. Rich CHANGELOG survives every release. Convention is already what Keep-a-Changelog recommends.

**Con:** Custom workflow to maintain. Force-push to bot-managed branches (release-please re-regenerates on each main push anyway, so this is the same pattern).

**Out of scope:** Solving the false-bump-from-cross-cutting-commits problem (#50, #55). That's a separate ergonomics issue and the agreed answer is "5-second close when it happens."

## Implementation pointers

- One YAML file at \`.github/workflows/release-please-changelog-fix.yml\`.
- One bash/python script in \`scripts/\` that does the CHANGELOG section swap.
- Token: reuse RELEASE_APP_ID + RELEASE_APP_PRIVATE_KEY (same as release-please.yml).
- Permissions: \`contents: write\`, \`pull-requests: write\`.

## Refs

Related: #54 (mat-vis workflow patterns to borrow), #43 (crates.io enablement), #49 (CHANGELOG bullet style)

Refs: #54
