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
from pathlib import Path
from typing import List, Tuple


def extract_docstring(source: str, func_name: str) -> str:
    """Extract the docstring from a test function."""
    # Find the function definition
    pattern = rf"def {func_name}\(.*?\):\n\s+\"\"\"(.*?)\"\"\""
    match = re.search(pattern, source, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


def extract_code_block(source: str, func_name: str) -> str:
    """Extract the code block after the docstring from a test function."""
    # Find the function definition
    pattern = rf"def {func_name}\(.*?\):\n\s+\"\"\".*?\"\"\"\n(.*?)(?=\n    def |\nclass |\Z)"
    match = re.search(pattern, source, re.DOTALL)
    if match:
        code = match.group(1).strip()
        # Remove pytest.importorskip lines
        code = re.sub(r"\s*pytest\.importorskip\(.*?\)\n", "", code)
        # Remove assert statements
        code = re.sub(r"\s*assert .*?\n", "", code)
        return code.strip()
    return ""


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


def generate_readme(template_path: Path, test_file_path: Path, output_path: Path):
    """Generate README.md from template and extracted examples."""
    # Read template
    with open(template_path, "r") as f:
        template = f.read()

    # Parse test file
    examples = parse_test_file(test_file_path)

    # Generate examples section
    examples_content = generate_examples_section(examples)

    # Replace placeholder in template
    readme_content = template.replace("{{EXAMPLES_COMPREHENSIVE}}", examples_content)

    # Write README
    with open(output_path, "w") as f:
        f.write(readme_content)

    print(f"Generated {output_path} with {len(examples)} examples")


if __name__ == "__main__":
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

    generate_readme(template_file, test_file, output_file)
