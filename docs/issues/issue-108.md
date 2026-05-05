---
type: issue
state: closed
created: 2026-05-04T12:33:58Z
updated: 2026-05-04T15:22:36Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/108
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-05-05T04:54:33.713Z
---

# [Issue 108]: [DX: typed kwargs for Vis.override via Unpack[TypedDict] (3.12+)](https://github.com/MorePET/mat/issues/108)

\`Vis.override(**deltas: Any)\` gives zero IDE completion. \`dataclasses.replace(v, rough<TAB>)\` gets surfaced \`roughness\` because the stdlib has special-cased type stubs for it. Override loses that.

### Fix

- Define \`VisDeltas(TypedDict, total=False)\` listing every public field + \`finish\`.
- Add a \`@overload\` with \`**deltas: Unpack[VisDeltas]\` gated on \`sys.version_info >= (3, 12)\`.
- Fall back to \`**deltas: Any\` on 3.10 / 3.11.

### Why

Every IDE-using consumer pays the no-completion tax forever otherwise. Pyright/Pylance respect \`Unpack[TypedDict]\` per PEP 692.

### Out of scope

Doesn't fix the runtime kwarg validation — \`fields(self)\` introspection stays.
