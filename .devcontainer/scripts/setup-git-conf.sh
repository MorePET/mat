#!/bin/bash
set -e

# One-time setup of git configuration inside the dev container.
# Copies config files from the .conf/ staging area to their container locations
# and authenticates the GitHub CLI.
# Called from post-create.sh (postCreateCommand).

# .devcontainer is mounted at workspace root for VS Code compatibility
DEVCONTAINER_DIR="/workspace/py_mat/.devcontainer"

# ── Git configuration ──────────────────────────────────────────────────────────

echo "Setting up git configuration..."
HOST_GITCONFIG_FILE="$DEVCONTAINER_DIR/.conf/.gitconfig"
CONTAINER_GITCONFIG_FILE=$HOME"/.gitconfig"
if [ -f "$HOST_GITCONFIG_FILE" ]; then
	echo "Applying git configuration from $HOST_GITCONFIG_FILE..."
	cp "$HOST_GITCONFIG_FILE" "$CONTAINER_GITCONFIG_FILE"
else
	echo "No git config file found, skipping git setup"
	echo "Run this from host's project root: .devcontainer/scripts/copy-host-user-conf.sh"
fi

# ── SSH public key for signing ─────────────────────────────────────────────────

HOST_SSH_PUBKEY="$DEVCONTAINER_DIR/.conf/id_ed25519_github.pub"
CONTAINER_SSH_DIR="$HOME/.ssh"
if [ -f "$HOST_SSH_PUBKEY" ]; then
	echo "Applying SSH public key from $HOST_SSH_PUBKEY..."
	mkdir -p "$CONTAINER_SSH_DIR"
	cp "$HOST_SSH_PUBKEY" "$CONTAINER_SSH_DIR/id_ed25519_github.pub"
	echo "SSH public key installed at $CONTAINER_SSH_DIR/id_ed25519_github.pub"
else
	echo "Warning: No SSH public key found at $HOST_SSH_PUBKEY"
	echo "Git commit signing may not work without this file"
	echo "Run this from host's project root: .devcontainer/scripts/copy-host-user-conf.sh"
fi

# ── Allowed-signers file ──────────────────────────────────────────────────────

HOST_ALLOWED_SIGNERS_FILE="$DEVCONTAINER_DIR/.conf/allowed-signers"
CONTAINER_ALLOWED_SIGNERS_DIR="$HOME/.config/git"
if [ -f "$HOST_ALLOWED_SIGNERS_FILE" ]; then
	echo "Applying allowed-signers file from $HOST_ALLOWED_SIGNERS_FILE..."
	mkdir -p "$CONTAINER_ALLOWED_SIGNERS_DIR"
	cp "$HOST_ALLOWED_SIGNERS_FILE" "$CONTAINER_ALLOWED_SIGNERS_DIR/allowed-signers"
	echo "Allowed-signers file installed at $CONTAINER_ALLOWED_SIGNERS_DIR/allowed-signers"
else
	echo "Warning: No allowed-signers file found at $HOST_ALLOWED_SIGNERS_FILE"
	echo "Git signature verification may not work without this file"
	echo "Run this from host's project root: .devcontainer/scripts/copy-host-user-conf.sh"
fi

# ── GitHub CLI config and authentication ──────────────────────────────────────

HOST_GH_CONFIG_DIR="$DEVCONTAINER_DIR/.conf/gh"
CONTAINER_GH_CONFIG_DIR="$HOME/.config/gh"
if [ -d "$HOST_GH_CONFIG_DIR" ]; then
	echo "Applying GitHub CLI config from $HOST_GH_CONFIG_DIR..."
	mkdir -p "$CONTAINER_GH_CONFIG_DIR"
	cp -r "$HOST_GH_CONFIG_DIR"/* "$CONTAINER_GH_CONFIG_DIR/" 2>/dev/null || true
	echo "GitHub CLI config installed at $CONTAINER_GH_CONFIG_DIR"
else
	echo "No GitHub CLI config directory found, skipping GitHub CLI config setup"
fi

# Authenticate GitHub CLI using token file (if available)
# Must run AFTER copying config so the fresh token overwrites any old authentication.
GH_TOKEN_FILE="$DEVCONTAINER_DIR/.conf/.gh_token"
if [ -f "$GH_TOKEN_FILE" ] && [ -s "$GH_TOKEN_FILE" ]; then
	echo "Authenticating GitHub CLI..."
	TOKEN=$(tr -d '\n\r\t ' < "$GH_TOKEN_FILE")
	if [ -n "$TOKEN" ]; then
		if [[ ! "$TOKEN" =~ ^gho_ ]]; then
			echo "Warning: Token format appears invalid (should start with 'gho_')"
		fi

		gh auth logout 2>/dev/null || true

		if echo "$TOKEN" | gh auth login --with-token 2>/dev/null; then
			STATUS_OUTPUT=$(gh auth status 2>&1)
			if echo "$STATUS_OUTPUT" | grep -q "Logged in"; then
				echo "GitHub CLI authenticated successfully"
			else
				echo "Warning: GitHub CLI authentication may have failed"
				echo "Status: $STATUS_OUTPUT"
			fi
		else
			echo "Warning: Failed to authenticate GitHub CLI with token"
			echo "Token may be expired or invalid. Run 'gh auth login' on the host to refresh."
		fi
	fi
	rm -f "$GH_TOKEN_FILE"
	echo "Token file removed for security"
fi

# ── Git hooks and commit template ─────────────────────────────────────────────

PROJECT_ROOT="/workspace/py_mat"

echo "Setting up git hooks..."
if [ -d "$PROJECT_ROOT/.githooks" ]; then
	cd "$PROJECT_ROOT"
	git config core.hooksPath .githooks
	echo "Git hooks configured to use .githooks directory"
else
	echo "No .githooks directory found, using default git hooks"
fi

if [ -f "$PROJECT_ROOT/.gitmessage" ]; then
	cd "$PROJECT_ROOT"
	git config commit.template .gitmessage
	echo "Commit message template configured (.gitmessage)"
fi
