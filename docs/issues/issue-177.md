---
type: issue
state: closed
created: 2026-05-04T21:22:37Z
updated: 2026-05-04T21:28:07Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/177
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-05-05T04:54:10.823Z
---

# [Issue 177]: [pymat-mcp: to_threejs/to_gltf leak raw texture bytes (4MB+ responses)](https://github.com/MorePET/mat/issues/177)

**Critical.** Found via live MCP test of 0.1.1 against Claude Code.

\`mcp__pymat__to_threejs(\"Stainless Steel 304\", finish=\"polished\")\` returned a **4 444 052-character** JSON payload — the underlying \`pymat.vis.to_threejs(material)\` adapter returns a dict whose \`map\`, \`normalMap\`, \`roughnessMap\`, \`metalnessMap\` fields are raw PNG bytes. The MCP server pipes that straight through.

Agents will not survive one such response. The MCP context budget for a single tool call is typically <100 KB.

## Fix

In \`clients/python/pymat-mcp/src/pymat_mcp/tools.py\`:

1. \`to_threejs\` / \`to_gltf\` strip texture-bytes fields from the adapter dict.
2. Return either:
   - **URLs** the agent can fetch themselves (preferred — mat-vis ships per-file HTTP URLs since 0.6.0), OR
   - **Texture-handle tuples**: \`{\"source\": ..., \"material_id\": ..., \"tier\": ..., \"channel\": ...}\` the agent can pass to a future \`fetch_texture\` tool.
3. PBR scalars + glTF \`pbrMetallicRoughness\` numbers stay — those are what the agent reasons about.

## Tests

Add a byte-budget assertion: every tool's serialized output must be < 100 KB. Catches the next time a refactor smuggles bytes back in.

## Scope

Breaking contract change for the affected tools — \`pymat-mcp 0.2.0\` (minor bump).
