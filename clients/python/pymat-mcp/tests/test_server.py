"""Smoke test for the FastMCP server: every expected tool registers,
each has a description, schemas import cleanly.

We don't run the stdio transport — that's an integration concern
deferred to ``mcp dev`` / MCP Inspector. The test here just verifies
the FastMCP wiring is intact (decorator names match, descriptions
are non-empty) so an agent inspecting the tool list before calling
one gets sensible metadata.
"""

from __future__ import annotations

import pytest

EXPECTED_TOOLS = {
    "search_materials",
    "get_material",
    "list_categories",
    "list_grades",
    "list_finishes",
    "compute_mass",
    "get_appearance",
    "to_threejs",
    "to_gltf",
    "compare_materials",
}


@pytest.fixture(scope="module")
def server():
    """Import the server lazily so the FastMCP runtime cost only hits
    once per session."""
    from pymat_mcp import server as server_module

    return server_module.mcp


@pytest.mark.asyncio
async def test_all_expected_tools_registered(server):
    """Every tool in the issue scope is registered and discoverable."""
    tool_list = await server.list_tools()
    names = {t.name for t in tool_list}
    missing = EXPECTED_TOOLS - names
    assert not missing, f"missing tools: {missing}"


@pytest.mark.asyncio
async def test_every_tool_has_a_description(server):
    """An agent reading ``list_tools`` should see useful descriptions
    so it picks the right tool — empty / one-line descriptions are
    a UX regression."""
    tool_list = await server.list_tools()
    for tool in tool_list:
        assert tool.description, f"tool {tool.name!r} has no description"
        assert len(tool.description) > 30, (
            f"tool {tool.name!r} description too short: {tool.description!r}"
        )


@pytest.mark.asyncio
async def test_every_tool_has_input_schema(server):
    """Tool schemas are how the agent knows what args to pass.
    Missing/malformed schema → the LLM has to guess."""
    tool_list = await server.list_tools()
    for tool in tool_list:
        schema = tool.inputSchema
        assert schema is not None, f"tool {tool.name!r} has no inputSchema"
        # FastMCP-generated schemas have type=object with a properties dict
        assert schema.get("type") == "object", (
            f"tool {tool.name!r} schema is not an object: {schema}"
        )


def test_server_module_imports():
    """Eager-import smoke — the server module loads without side effect
    (no stdio transport started, no network)."""
    from pymat_mcp import server  # noqa: F401


def test_main_callable():
    """The console-script entry point is callable. We don't actually
    invoke it (would block on stdio); just verify the symbol exists."""
    from pymat_mcp.server import main

    assert callable(main)
