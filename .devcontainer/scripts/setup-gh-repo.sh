#!/bin/bash
set -euo pipefail

# Configure GitHub repository settings for merge commit compliance and
# detach the org-level default code security configuration (to avoid
# clashing with security workflows shipped in this workspace template).
# Called from post-create.sh (postCreateCommand) — runs once per container.
#
# Requires: gh CLI authenticated with repo admin permissions.
# Fails gracefully if gh is not authenticated or lacks permissions.

REPO=$(gh repo view --json nameWithOwner --jq '.nameWithOwner' 2>/dev/null || echo "")

if [ -z "$REPO" ]; then
	echo "Skipping repo merge settings (not in a GitHub repo or gh not authenticated)"
	exit 0
fi

echo "Configuring merge commit settings for $REPO..."

if gh api "repos/$REPO" -X PATCH \
	-f merge_commit_title=PR_TITLE \
	-f merge_commit_message=PR_BODY \
	-F allow_auto_merge=true \
	>/dev/null 2>&1; then
	echo "✓ Merge commit format: PR title + body"
	echo "✓ Auto-merge: enabled"
else
	echo "✗ Could not update repo settings (insufficient permissions?)"
	echo "  Manual setup: gh api repos/$REPO -X PATCH -f merge_commit_title=PR_TITLE -f merge_commit_message=PR_BODY -F allow_auto_merge=true"
fi

# Detach any org-level default code security configuration from this repo.
ORG="${REPO%%/*}"
REPO_ID=$(gh api "repos/$REPO" --jq '.id' 2>/dev/null || echo "")

if [ -z "$REPO_ID" ]; then
	echo "✗ Could not determine repo ID — skipping security config detachment"
else
	CONFIG_STATUS=$(gh api "repos/$REPO/code-security-configuration" --jq '.status // empty' 2>/dev/null || echo "")
	if [ -z "$CONFIG_STATUS" ] || [ "$CONFIG_STATUS" = "detached" ]; then
		echo "✓ No security config attached — nothing to detach"
	else
		echo "Detaching default code security configuration (status: $CONFIG_STATUS)..."
		if gh api "orgs/$ORG/code-security/configurations/detach" \
			-X DELETE \
			--input - <<-JSON >/dev/null 2>&1; then
{"selected_repository_ids":[$REPO_ID]}
JSON
			echo "✓ Default security configuration detached"
		else
			echo "✗ Could not detach security config (insufficient permissions?)"
			echo "  Manual: gh api orgs/$ORG/code-security/configurations/detach -X DELETE --input - <<< '{\"selected_repository_ids\":[$REPO_ID]}'"
		fi
	fi
fi
