#!/bin/bash

# Post-attach script - runs each time a tool attaches to the container.
# This script is called from postAttachCommand in devcontainer.json.
#
# Lightweight checks and dependency sync:
#   - Verify SSH agent has the signing key
#   - Verify GitHub CLI is authenticated
#   - Sync dependencies (fast no-op if nothing changed)

set -euo pipefail

echo "Running post-attach checks..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="/workspace/py_mat"

"$SCRIPT_DIR/verify-auth.sh"

# Sync Python dependencies if pyproject.toml changed (fast, only installs missing deps)
# Use --no-install-project since new projects may not have source code yet
if [[ -f "$PROJECT_ROOT/pyproject.toml" ]]; then
    uv sync --all-extras --no-install-project --quiet
fi

"$SCRIPT_DIR/version-check.sh" || true

echo "Post-attach setup complete"
