#!/bin/bash
set -euo pipefail

# Change to project root directory (py_mat is replaced during template initialization)
PROJECT_ROOT="/workspace/py_mat"

# Ensure project directory exists
if [ ! -d "$PROJECT_ROOT" ]; then
    echo "Error: Project directory $PROJECT_ROOT does not exist"
    exit 1
fi

cd "$PROJECT_ROOT"

echo "Checking git repository status..."

# Check if we're already in a git repository
if [ -d ".git" ]; then
    echo "Git repository already initialized"
else
    echo "No git repository found, initializing..."
    git init
    git checkout -b main 2>/dev/null || git branch -M main
    echo "Git repository initialized with main branch"
fi
