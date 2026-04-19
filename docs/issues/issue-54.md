---
type: issue
state: open
created: 2026-04-18T18:37:49Z
updated: 2026-04-18T18:37:49Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/54
comments: 0
labels: enhancement
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-04-19T04:44:05.931Z
---

# [Issue 54]: [ci: adopt mat-vis workflow patterns (dry-run inputs + documented headers)](https://github.com/MorePET/mat/issues/54)

## Context

mat-vis (\`MorePET/mat-vis\`) has two workflow patterns worth borrowing for our future manual release / promotion workflows:

1. **\`workflow_dispatch\` with a \`dry-run\` boolean input.** Their \`promote-data-release.yml\` accepts a \`dry-run\` flag that runs validation steps without performing the action. Cheap safety rail.
2. **Documented workflow headers.** Their workflow files start with a clear comment block (Flow / Trigger / Inputs sections) instead of just the name. Makes the file's purpose obvious without reading the YAML.

Reference: see \`promote-data-release.yml\`, \`bake.yml\`, \`pypi.yml\` in MorePET/mat-vis.

## When this applies here

- **When \`CRATES_IO_PUBLISH_ENABLED\` flips on** (#43): the first crates.io publish workflow run benefits from a dry-run option to validate the token + crate metadata without actually publishing.
- **Future catalog/thumbnail asset releases** (if we ever ship those as GH Release assets, parallel to the wheel).
- **Future manual recovery workflows** (re-tag, re-publish, etc.).

## Proposed pattern

For new manual workflows:

\`\`\`yaml
on:
  workflow_dispatch:
    inputs:
      dry-run:
        description: 'Validate without acting'
        required: false
        default: false
        type: boolean
\`\`\`

And the header style:

\`\`\`yaml
# <Workflow purpose — one sentence>
#
# Flow:
#   1. ...
#   2. ...
#
# Trigger: <when it fires>
# Inputs: <if any>
\`\`\`

## Not adopting

- mat-vis's manual version-tagging / no-release-please model. Our release-please setup gives us automatic version bumps + CHANGELOG generation; reverting would trade one annoyance (occasional false bumps from cross-cutting commits) for several (forgotten bumps, inconsistent CHANGELOGs).
- Calver for code. Doesn't fit a code library.

## Refs

Related: #43 (crates.io enablement), #50 (the false-bump that prompted this look-around)
