#!/usr/bin/env python3
"""
README generator: Extract examples from test_readme_examples.py and generate README.md

This script implements the "doc-as-tested-code" paradigm by:
1. Parsing test_readme_examples.py for docstrings and code
2. Extracting markdown documentation and code examples
3. Merging with README_TEMPLATE.md
4. Generating the final README.md

Usage:
    python scripts/generate_readme.py
"""

import re
import textwrap
from pathlib import Path
from typing import List, Tuple


def extract_docstring(source: str, func_name: str) -> str:
    """Extract the docstring from a test function, dedented."""
    pattern = rf"def {func_name}\(.*?\):\n\s+\"\"\"(.*?)\"\"\""
    match = re.search(pattern, source, re.DOTALL)
    if not match:
        return ""
    raw = match.group(1)
    # Drop the leading newline after `"""` so dedent can see a uniform
    # indent on all remaining lines, then strip any trailing whitespace.
    if raw.startswith("\n"):
        raw = raw[1:]
    return textwrap.dedent(raw).rstrip()


def extract_code_block(source: str, func_name: str) -> str:
    """
    Extract the code block after the docstring from a test function.

    Returns the code dedented to column 0 with assertion / importorskip
    scaffolding removed, so it renders as a plain, runnable Python
    snippet in the README.
    """
    pattern = rf"def {func_name}\(.*?\):\n\s+\"\"\".*?\"\"\"\n(.*?)(?=\n    def |\nclass |\Z)"
    match = re.search(pattern, source, re.DOTALL)
    if not match:
        return ""

    raw = match.group(1).rstrip()
    if not raw.strip():
        return ""

    # Dedent the entire block relative to its own leading indent. Test
    # function bodies are indented 8 spaces (4 for the class, 4 for the
    # method); `textwrap.dedent` handles arbitrary depths correctly.
    dedented = textwrap.dedent(raw)

    # Filter out pytest scaffolding that doesn't belong in a user-facing
    # example. Keep comments, blank lines, imports, asserts (they show
    # the expected return values), and actual code.
    kept: list[str] = []
    for line in dedented.splitlines():
        stripped = line.strip()
        if stripped.startswith("pytest.importorskip"):
            continue
        kept.append(line)

    # Collapse runs of blank lines left behind by filtering.
    cleaned: list[str] = []
    prev_blank = False
    for line in kept:
        if not line.strip():
            if prev_blank:
                continue
            prev_blank = True
        else:
            prev_blank = False
        cleaned.append(line)

    return "\n".join(cleaned).strip()


def parse_test_file(test_file_path: Path) -> List[Tuple[str, str, str]]:
    """
    Parse test_readme_examples.py and extract sections.

    Returns list of (section_title, markdown_content, code_content) tuples.
    """
    with open(test_file_path, "r") as f:
        source = f.read()

    examples = []

    # Find all test classes and functions
    class_pattern = r"class (Test\w+):\n\s+\"\"\"(.*?)\"\"\""
    for class_match in re.finditer(class_pattern, source, re.DOTALL):
        # Find all test functions in this class
        class_start = class_match.end()
        next_class = re.search(r"\nclass ", source[class_start:])
        class_end = class_start + next_class.start() if next_class else len(source)
        class_source = source[class_start:class_end]

        func_pattern = r"def (test_\w+)\(self"
        for func_match in re.finditer(func_pattern, class_source):
            func_name = func_match.group(1)
            func_source = class_source[func_match.start() :]

            # Extract docstring
            docstring = extract_docstring(func_source, func_name)
            code = extract_code_block(func_source, func_name)

            if docstring and code:
                examples.append((docstring, code))

    return examples


def generate_examples_section(examples: List[Tuple[str, str]]) -> str:
    """Generate markdown content from extracted examples."""
    content = ""

    for docstring, code in examples:
        content += docstring + "\n\n"

        # Wrap code in markdown block
        content += "```python\n"
        content += code + "\n"
        content += "```\n\n"

    return content.strip()


def render_readme(template_path: Path, test_file_path: Path) -> str:
    """Render the README text from the template + extracted test examples."""
    template = template_path.read_text()
    examples = parse_test_file(test_file_path)
    examples_content = generate_examples_section(examples)
    return template.replace("{{EXAMPLES_COMPREHENSIVE}}", examples_content)


def generate_readme(template_path: Path, test_file_path: Path, output_path: Path):
    """Write the rendered README to disk."""
    content = render_readme(template_path, test_file_path)
    output_path.write_text(content)
    examples = parse_test_file(test_file_path)
    print(f"Generated {output_path} with {len(examples)} examples")


def check_readme(template_path: Path, test_file_path: Path, output_path: Path) -> int:
    """Exit non-zero if README.md on disk differs from regenerated output."""
    import sys

    rendered = render_readme(template_path, test_file_path)
    existing = output_path.read_text() if output_path.exists() else ""
    if existing == rendered:
        examples = parse_test_file(test_file_path)
        print(f"README.md matches regenerated output ({len(examples)} examples)")
        return 0
    print(
        "README.md is out of date. Regenerate with:\n    python scripts/generate_readme.py",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail non-zero if README.md differs from regenerated output.",
    )
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    test_file = project_root / "tests" / "test_readme_examples.py"
    template_file = project_root / "docs" / "README_TEMPLATE.md"
    output_file = project_root / "README.md"

    if not test_file.exists():
        print(f"Error: {test_file} not found")
        exit(1)

    if not template_file.exists():
        print(f"Error: {template_file} not found")
        exit(1)

    if args.check:
        exit(check_readme(template_file, test_file, output_file))

    generate_readme(template_file, test_file, output_file)
