---
type: issue
state: closed
created: 2026-05-04T19:28:36Z
updated: 2026-05-04T19:44:57Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/113
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-05-05T04:54:32.968Z
---

# [Issue 113]: [pymat-mcp v0.1 — standalone MCP server (uvx-runnable)](https://github.com/MorePET/mat/issues/113)

Standalone MCP server exposing the curated material registry to AI agents that talk MCP but don't run arbitrary Python (Claude Desktop, Cursor, MCP Inspector).

## Why standalone

- **uvx UX**: end users add 3 lines of JSON to claude_desktop_config; uvx handles install+run in an isolated venv per session
- **Decoupled cadence**: MCP schema changes don't touch py-materials core
- **Industry pattern**: mirrors Anthropic's first-party servers (\`mcp-server-git\`, \`mcp-server-fetch\`, \`mcp-server-sqlite\`)
- Same-repo split (mat-vis-client precedent at \`clients/python/\`)

## Layout

\`\`\`
clients/python/pymat-mcp/
  pyproject.toml          # name="pymat-mcp", deps=["py-materials>=3.8.0", "mcp>=1.0"]
  src/pymat_mcp/
    server.py             # FastMCP entrypoint
    tools.py              # one function per tool
  tests/
  README.md
\`\`\`

## v0.1 tool list (read-only)

| Tool | Args | Returns |
|---|---|---|
| \`search_materials\` | \`query: str\`, \`limit: int = 10\` | List of \`{key, name, grade, category, density, brief}\` |
| \`get_material\` | \`key_or_name: str\` | Full property dump (mechanical, thermal, electrical, optical, manufacturing, compliance, sourcing) |
| \`list_categories\` | — | \`["aluminum", "stainless", "lyso", ...]\` |
| \`list_grades\` | \`material: str\` | Grades / tempers / treatments under a parent |
| \`compute_mass\` | \`material: str\`, \`volume_mm3: float\` | mass in grams (uses curated density) |
| \`get_appearance\` | \`material: str\` | Vis identity (\`source/material_id/tier\`), finishes, PBR scalars |
| \`to_threejs\` | \`material: str\`, optional \`finish: str\` | adapter dict |
| \`to_gltf\` | \`material: str\`, optional \`finish: str\` | adapter dict |
| \`compare_materials\` | \`keys: list[str]\`, \`properties: list[str]\` | side-by-side table |

## Out of scope for v0.1

- Writes (custom material registration)
- Live mat-vis texture fetches (return URLs instead)
- Auth / multi-tenant
- SSE / HTTP transport (stdio only — what Claude Desktop expects)

## Install + use (target UX)

\`\`\`json
{
  "mcpServers": {
    "pymat": { "command": "uvx", "args": ["pymat-mcp"] }
  }
}
\`\`\`

That's the entire install. uvx fetches \`pymat-mcp\`, transitively pulls \`py-materials\`, sets up an isolated env per session.

## Tests

- Per-tool: schema assertions + golden-material round-trips
- MCP protocol smoke: tools register cleanly, list_tools returns expected names + descriptions
- Eager-import: \`pymat_mcp\` and \`pymat_mcp.tools\` import on every Python version

## CI

- \`.github/workflows/publish-mcp.yml\` — triggered by tag \`pymat-mcp/v*\`
- Reuses \`pypi\` environment + OIDC trusted publisher (pre-registered for project name \`pymat-mcp\`)
- Mirrors py-materials' \`release.yml\` structure
