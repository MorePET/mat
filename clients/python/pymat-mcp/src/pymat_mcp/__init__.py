"""pymat-mcp — MCP server exposing py-materials to AI agents.

Standalone PyPI package (`pip install pymat-mcp` or `uvx pymat-mcp`).
The library it wraps is ``py-materials`` (the ``pymat`` Python package)
— installed as a transitive dep.

Entry point::

    pymat-mcp                 # stdio transport, the form Claude Desktop expects

Programmatic use is via the ``pymat_mcp.tools`` functions, which return
plain dicts and are independently testable without an MCP runtime.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("pymat-mcp")
except PackageNotFoundError:
    __version__ = "0.0.0+dev"

__all__ = ["__version__"]
