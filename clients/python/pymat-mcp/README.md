# pymat-mcp

MCP server exposing the [py-materials](https://github.com/MorePET/mat) curated
material registry to AI agents — Claude Desktop, Cursor, MCP Inspector, any
MCP-compatible client.

> "Aluminum 6061-T6 yield strength?" — agent calls `get_material` instead of
> guessing. CAD prompts that need real density / mechanical properties stop
> hallucinating.

## Install

Zero-install via `uvx`:

```json
{
  "mcpServers": {
    "pymat": {
      "command": "uvx",
      "args": ["pymat-mcp"]
    }
  }
}
```

That's it. `uvx` fetches `pymat-mcp` (which transitively pulls
`py-materials`) and runs it in an isolated venv per session.

For a pinned version: `"args": ["pymat-mcp@0.1.0"]`.

For programmatic use, `pip install pymat-mcp` works too — the package is
fully a normal Python module.

## Tools

| Tool | What |
|---|---|
| `search_materials(query, limit=10)` | Fuzzy lookup → list of brief rows |
| `get_material(key_or_name)` | Full property dump (mechanical / thermal / electrical / optical / manufacturing / compliance / sourcing) + visual identity |
| `list_categories()` | Top-level groups (aluminum, stainless, lyso, …) |
| `list_grades(material)` | Children (grades / tempers / treatments) |
| `compute_mass(material, volume_mm3)` | Mass in grams from a build123d-style volume |
| `get_appearance(material)` | Vis dict — mat-vis identity, finishes, PBR scalars |
| `to_threejs(material, finish=None)` | Three.js MeshPhysicalMaterial init dict |
| `to_gltf(material, finish=None)` | glTF 2.0 material node |
| `compare_materials(keys, properties=None)` | Side-by-side property comparison |

All tools are read-only. Errors come back as `{"error": "...", "did_you_mean": [...]}` rather than exceptions.

## Example agent prompts

- *"What's the yield strength of 17-4 PH H1025? Use the materials database."*
- *"I have a 50×50×10 mm 6061 plate; what's the mass?"*
- *"Give me a Three.js material dict for stainless steel with a polished finish."*
- *"Compare density and thermal conductivity for 6061, 7075, and copper."*

## Logging

Logs to stderr only (stdout is the MCP transport channel). Bump verbosity:

```bash
PYMAT_MCP_LOG=DEBUG uvx pymat-mcp
```

## Development

```bash
git clone https://github.com/MorePET/mat
cd mat/clients/python/pymat-mcp
uv sync --all-extras
uv run pytest -v
```

To exercise the server interactively:

```bash
uvx mcp dev pymat-mcp     # MCP Inspector — point-and-click tool calls
```

## Links

- Source: <https://github.com/MorePET/mat/tree/main/clients/python/pymat-mcp>
- Issues: <https://github.com/MorePET/mat/issues>
- py-materials (the wrapped library): <https://github.com/MorePET/mat>
- MCP spec: <https://spec.modelcontextprotocol.io>
