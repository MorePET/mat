#!/bin/bash
set -euo pipefail

# py_mat is replaced during template initialization
PROJECT_ROOT="/workspace/py_mat"

# Run only if pre-commit hooks are not already installed
if [ -d "$PROJECT_ROOT/.pre-commit-cache" ]; then
	echo "Pre-commit hooks already installed, skipping"
	exit 0
fi

if [ -f "$PROJECT_ROOT/.pre-commit-config.yaml" ]; then
    echo "Setting up pre-commit hooks (this may take a few minutes)..."
    cd "$PROJECT_ROOT"
    pre-commit install-hooks || {
        echo "⚠️  Pre-commit install failed"
        echo "    You can manually run 'pre-commit install-hooks' later"
        exit 1
    }
    echo "Pre-commit hooks installed successfully"
else
    echo "No .pre-commit-config.yaml found, skipping"
fi
