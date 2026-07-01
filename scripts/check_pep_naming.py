"""Custom PEP-8 naming hook — flags trailing-single-underscore method
and function names whose stripped form isn't a Python keyword or
built-in.

PEP 8: "Trailing underscores are used by convention to avoid conflicts
with Python keyword[s], e.g. `class_`, `type_`, `id_`." Using a
trailing underscore as a general naming convention (e.g. `grade_`,
`temper_`) violates this contract and confuses readers. py-mat#218
called this out explicitly.

Ruff's `N` rule set covers most PEP-8 naming patterns but not this
one specifically — `N802` accepts any `[a-z][a-z0-9_]*` form
including `grade_`. This hook is the gap-filler.

Suppression: add ``# pymat-keep-_`` on the same line as the `def`
(short form). Long forms ``# pymat-quality: ignore trailing-underscore``
and ``# noqa: PYMAT_TRAILING_UNDERSCORE`` are also recognized.
Use only for back-compat deprecation aliases.

Run: ``python scripts/check_pep_naming.py [PATH ...]``
Exits 0 with no output on clean code, 1 with diagnostics on
violations.
"""

from __future__ import annotations

import ast
import builtins
import keyword
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path

# Names whose trailing underscore IS legitimate per PEP 8 (kw/builtin
# disambiguation). Built-ins extend keywords with the standard set
# users commonly want to shadow without losing the original (`type_`,
# `id_`, `list_`, `dict_`).
_LEGITIMATE_STRIPPED_NAMES: frozenset[str] = frozenset(keyword.kwlist) | frozenset(dir(builtins))

# Ignore directives recognized on the def line (case-insensitive).
# Short form `pymat-keep-_` is preferred — keeps the def signature on
# one line. The longer forms are recognized for back-compat with early
# call sites and humans who like reading the verb out.
_IGNORE_TOKENS = (
    "pymat-keep-_",
    "noqa: pymat_trailing_underscore",
    "pymat-quality: ignore trailing-underscore",
)


def _has_ignore_directive(source: str, lineno: int) -> bool:
    """Return True if line ``lineno`` (1-based) contains an ignore
    directive in its trailing comment.

    Walks back to the opening ``def`` line in case the signature spans
    multiple lines and the directive sits on the def line itself.
    """
    lines = source.splitlines()
    if lineno - 1 >= len(lines):
        return False
    line = lines[lineno - 1].lower()
    return any(tok in line for tok in _IGNORE_TOKENS)


def _walk_def_nodes(tree: ast.AST) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def _check_node(
    node: ast.FunctionDef | ast.AsyncFunctionDef, source: str
) -> tuple[str, int] | None:
    """Return (message, line) if the node's name violates the rule;
    else None."""
    name = node.name
    if not name.endswith("_"):
        return None
    if name.startswith("__") or name.endswith("__"):
        # Dunders / sunders use leading-and-trailing underscores; not
        # the trailing-single-underscore convention this hook targets.
        return None
    if name.startswith("_"):
        # Single-leading-underscore names (private) — skip; the trailing
        # underscore here is unusual but private API convention is
        # already a different lint axis (PEP 8 says nothing about it).
        return None

    stripped = name.rstrip("_")
    if stripped in _LEGITIMATE_STRIPPED_NAMES:
        return None  # legitimate kw/builtin disambiguation

    if _has_ignore_directive(source, node.lineno):
        return None

    msg = (
        f"PYMAT_TRAILING_UNDERSCORE: function/method `{name}` ends with `_` "
        f"but `{stripped}` is not a Python keyword or built-in. PEP 8 reserves "
        "trailing single underscore for keyword-collision avoidance only. "
        "Rename (e.g. `add_grade` for `grade_`) or add `# pymat-keep-_` on "
        "the def line if this is an intentional back-compat deprecation alias."
    )
    return msg, node.lineno


def check_path(path: Path) -> list[str]:
    """Return list of formatted violations for one .py file."""
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [f"{path}: read error: {exc}"]

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [f"{path}:{exc.lineno}: SyntaxError: {exc.msg}"]

    diagnostics: list[str] = []
    for node in _walk_def_nodes(tree):
        result = _check_node(node, source)
        if result is None:
            continue
        msg, line = result
        diagnostics.append(f"{path}:{line}: {msg}")
    return diagnostics


def _iter_files(paths: Iterable[Path]) -> Iterator[Path]:
    for p in paths:
        if p.is_dir():
            yield from sorted(p.rglob("*.py"))
        elif p.suffix == ".py":
            yield p


def main(argv: list[str]) -> int:
    if not argv:
        # Default: check src/ + tests/ if invoked without arguments.
        argv = ["src", "tests", "scripts"]
    paths = [Path(p) for p in argv if Path(p).exists()]
    diagnostics: list[str] = []
    for f in _iter_files(paths):
        diagnostics.extend(check_path(f))
    for d in diagnostics:
        print(d)
    return 1 if diagnostics else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
