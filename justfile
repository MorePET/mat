# ===============================================================================
# MAIN JUSTFILE - Orchestrates all recipe sources
# ===============================================================================

# Show available commands
[group('info')]
help:
    @just --list

# Import devcontainer-managed base recipes (replaced on upgrade)

import '.devcontainer/justfile.devc'
import '.devcontainer/justfile.gh'

# Import team-shared project recipes (git-tracked, preserved on upgrade)

import? 'justfile.project'

# Import personal recipes (gitignored, preserved on upgrade)

import? 'justfile.local'
