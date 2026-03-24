#!/bin/bash

# Post-start script - runs every time the container starts (create + restart).
# This script is called from postStartCommand in devcontainer.json.
#
# Tasks that should run on every container start:
#   - Fix Docker socket permissions
#   - Sync dependencies (fast no-op if nothing changed)

set -euo pipefail

echo "Running post-start setup..."

PROJECT_ROOT="/workspace/py_mat"

# Ensure Docker socket is accessible
sudo chmod 666 /var/run/docker.sock 2>/dev/null || true

# Sync dependencies (fast no-op if nothing changed)
echo "Syncing dependencies..."
just --justfile "$PROJECT_ROOT/justfile" --working-directory "$PROJECT_ROOT" sync

echo "Post-start setup complete"
