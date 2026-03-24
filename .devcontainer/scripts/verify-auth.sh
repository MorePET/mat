#!/bin/bash
set -e

# Verify authentication state inside the dev container.
# Checks that the SSH agent has the signing key and that gh is authenticated.
# Safe to run on every attach/reconnect — read-only, no side effects.
# Called from post-attach.sh (postAttachCommand).

DEVCONTAINER_DIR="/workspace/py_mat/.devcontainer"
SSH_PUBKEY="$DEVCONTAINER_DIR/.conf/id_ed25519_github.pub"

# ── SSH agent verification ─────────────────────────────────────────────────────
# VS Code/Cursor forwards the host SSH agent into the container.
# We verify the signing key is accessible so git commit signing works.

verify_ssh_agent() {
	echo "Verifying SSH agent for git signing..."

	if [ ! -f "$SSH_PUBKEY" ]; then
		echo "Skipping SSH agent verification (no signing key in .conf/)"
		return
	fi

	EXPECTED_FINGERPRINT=$(ssh-keygen -l -f "$SSH_PUBKEY" 2>/dev/null | awk '{print $2}' || echo "")
	EXPECTED_KEY_COMMENT=$(ssh-keygen -l -f "$SSH_PUBKEY" 2>/dev/null | awk '{for(i=3;i<=NF;i++) printf "%s ", $i; print ""}' | sed 's/ $//' || echo "")

	if [ -z "$EXPECTED_FINGERPRINT" ]; then
		echo "✗ Warning: Could not determine signing key fingerprint"
		return
	fi

	echo "Looking for signing key: $EXPECTED_FINGERPRINT ($EXPECTED_KEY_COMMENT)"

	# Check if the current SSH_AUTH_SOCK has the signing key
	if [ -n "${SSH_AUTH_SOCK:-}" ] && [ -S "$SSH_AUTH_SOCK" ]; then
		if ssh-add -l 2>/dev/null | grep -q "$EXPECTED_FINGERPRINT"; then
			echo "✓ Git signing key is accessible in SSH agent"
			return
		fi
		echo "✗ Git signing key NOT found in current SSH agent ($SSH_AUTH_SOCK)"
		echo "Available keys:"
		ssh-add -l 2>/dev/null || echo "  (none)"
	else
		echo "✗ SSH_AUTH_SOCK is not set or socket does not exist"
	fi

	# Scan all available SSH agent sockets for the signing key
	echo ""
	echo "Scanning available SSH agent sockets..."
	local found_socket=""
	local socket_count=0

	for sock in /tmp/cursor-remote-ssh-*.sock /tmp/ssh-*/agent.* /run/user/*/openssh_agent; do
		[ ! -S "$sock" ] 2>/dev/null && continue
		socket_count=$((socket_count + 1))

		echo "  Socket #$socket_count: $sock"
		if KEYS=$(SSH_AUTH_SOCK="$sock" ssh-add -l 2>/dev/null) && [ -n "$KEYS" ]; then
			if echo "$KEYS" | grep -q "$EXPECTED_FINGERPRINT"; then
				found_socket="$sock"
				echo "    ✓ CONTAINS SIGNING KEY"
			fi
		else
			echo "    (no keys or not accessible)"
		fi
	done

	if [ $socket_count -eq 0 ]; then
		echo "  No SSH agent sockets found"
	fi

	if [ -n "$found_socket" ]; then
		export SSH_AUTH_SOCK="$found_socket"
		echo ""
		echo "✓ Updated SSH_AUTH_SOCK=$SSH_AUTH_SOCK"
	else
		echo ""
		echo "✗ Could not find SSH agent socket with signing key"
		echo "  Git commit signing may not work. Ensure SSH agent forwarding is enabled."
	fi
}

# ── GitHub CLI verification ────────────────────────────────────────────────────

verify_gh_auth() {
	echo "Verifying GitHub CLI authentication..."

	if ! command -v gh >/dev/null 2>&1; then
		echo "✗ gh not found"
		return
	fi

	if gh auth status >/dev/null 2>&1; then
		echo "✓ GitHub CLI is authenticated"
	else
		echo "✗ GitHub CLI is NOT authenticated"
		echo "  Run on the host: .devcontainer/scripts/copy-host-user-conf.sh"
		echo "  Then rebuild/restart the container."
	fi
}

# ── Main ───────────────────────────────────────────────────────────────────────

verify_ssh_agent
echo ""
verify_gh_auth
