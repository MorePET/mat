#!/bin/bash
###############################################################################
# version-check.sh - Devcontainer Update Checker
#
# Checks for new vigOS devcontainer releases and notifies the user.
# Designed to fail gracefully (silent on errors) and respect user preferences.
#
# USAGE:
#   ./version-check.sh                  # Check and notify (silent on error)
#   ./version-check.sh check            # Check with verbose output
#   ./version-check.sh on|enable        # Enable notifications
#   ./version-check.sh off|disable      # Disable notifications
#   ./version-check.sh mute <dur>       # Mute for duration (e.g., 7d, 1w)
#   ./version-check.sh interval <dur>   # Set check interval
#   ./version-check.sh config           # Display current configuration
#
# DURATIONS: And (days), Nw (weeks), Nh (hours), Nm (minutes)
#
# CONFIGURATION:
#   Stored in .devcontainer/.local/version-check.conf (gitignored)
###############################################################################

set -euo pipefail

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEVCONTAINER_DIR="$(dirname "$SCRIPT_DIR")"

# Local config directory (gitignored)
LOCAL_DIR="$DEVCONTAINER_DIR/.local"
CONFIG_FILE="$LOCAL_DIR/version-check.conf"
LAST_CHECK_FILE="$LOCAL_DIR/.last-check"
MUTED_UNTIL_FILE="$LOCAL_DIR/.muted-until"
CACHE_FILE="$LOCAL_DIR/.latest-version"

# API endpoint
GITHUB_API="https://api.github.com/repos/vig-os/devcontainer/releases/latest"

# Defaults
DEFAULT_CHECK_INTERVAL=86400  # 24 hours in seconds
DEFAULT_ENABLED="true"

# Runtime
VERBOSE=false
SILENT_FAIL=true

# Colors
CYAN='\033[0;36m'
YELLOW='\033[0;33m'
GREEN='\033[0;32m'
BOLD='\033[1m'
NC='\033[0m'

# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

# Silent exit on error (no output)
fail_silent() {
    exit 0
}

# Print only if verbose mode
log_verbose() {
    if $VERBOSE; then
        echo "$1"
    fi
}

# Ensure local directory exists
ensure_local_dir() {
    if [[ ! -d "$LOCAL_DIR" ]]; then
        mkdir -p "$LOCAL_DIR"
    fi
}

# Parse duration string to seconds (e.g., 7d, 1w, 12h, 30m)
parse_duration() {
    local duration="$1"
    local num="${duration%[dhwm]}"
    local unit="${duration: -1}"

    if ! [[ "$num" =~ ^[0-9]+$ ]]; then
        return 1
    fi

    case "$unit" in
        m) echo $((num * 60)) ;;
        h) echo $((num * 3600)) ;;
        d) echo $((num * 86400)) ;;
        w) echo $((num * 604800)) ;;
        *) return 1 ;;
    esac
}

# Format seconds to human-readable duration
format_duration() {
    local seconds="$1"
    if [[ $seconds -ge 604800 ]]; then
        echo "$((seconds / 604800)) week(s)"
    elif [[ $seconds -ge 86400 ]]; then
        echo "$((seconds / 86400)) day(s)"
    elif [[ $seconds -ge 3600 ]]; then
        echo "$((seconds / 3600)) hour(s)"
    else
        echo "$((seconds / 60)) minute(s)"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

# Load config (creates default if missing)
load_config() {
    ensure_local_dir

    # Default values
    CHECK_ENABLED="$DEFAULT_ENABLED"
    CHECK_INTERVAL="$DEFAULT_CHECK_INTERVAL"

    if [[ -f "$CONFIG_FILE" ]]; then
        # Source config file (simple key=value format)
        while IFS='=' read -r key value; do
            [[ -z "$key" || "$key" =~ ^# ]] && continue
            case "$key" in
                enabled) CHECK_ENABLED="$value" ;;
                interval) CHECK_INTERVAL="$value" ;;
            esac
        done < "$CONFIG_FILE"
    fi
}

# Save config
save_config() {
    ensure_local_dir
    cat > "$CONFIG_FILE" << EOF
# Devcontainer version check configuration
# This file is gitignored and local to your machine
enabled=$CHECK_ENABLED
interval=$CHECK_INTERVAL
EOF
}

# Check if currently muted
is_muted() {
    if [[ -f "$MUTED_UNTIL_FILE" ]]; then
        local muted_until
        muted_until=$(cat "$MUTED_UNTIL_FILE")
        local now
        now=$(date +%s)
        if [[ $now -lt $muted_until ]]; then
            return 0  # Still muted
        fi
        # Mute expired, remove file
        rm -f "$MUTED_UNTIL_FILE"
    fi
    return 1  # Not muted
}

# Check if enough time passed since last check
should_check() {
    if [[ ! -f "$LAST_CHECK_FILE" ]]; then
        return 0  # Never checked, should check
    fi

    local last_check
    last_check=$(cat "$LAST_CHECK_FILE")
    local now
    now=$(date +%s)
    local elapsed=$((now - last_check))

    if [[ $elapsed -ge $CHECK_INTERVAL ]]; then
        return 0  # Interval passed, should check
    fi

    return 1  # Too soon
}

# Record check timestamp
record_check() {
    ensure_local_dir
    date +%s > "$LAST_CHECK_FILE"
}

# ═══════════════════════════════════════════════════════════════════════════════
# VERSION DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

# Get current installed version from root .vig-os config
get_current_version() {
    local config_file="$DEVCONTAINER_DIR/../.vig-os"
    local line
    local version=""

    if [[ ! -f "$config_file" ]]; then
        return 1
    fi

    while IFS= read -r line || [[ -n "$line" ]]; do
        [[ -z "${line//[[:space:]]/}" ]] && continue
        [[ "$line" =~ ^[[:space:]]*# ]] && continue

        case "$line" in
            DEVCONTAINER_VERSION=*)
                version="${line#*=}"
                version="${version#"${version%%[![:space:]]*}"}"
                version="${version%"${version##*[![:space:]]}"}"

                if [[ "$version" =~ ^\".*\"$ ]]; then
                    version="${version:1:-1}"
                elif [[ "$version" =~ ^\'.*\'$ ]]; then
                    version="${version:1:-1}"
                fi
                break
                ;;
        esac
    done < "$config_file"

    if [[ -z "$version" || "$version" == "dev" || "$version" == "latest" ]]; then
        return 1  # Not a pinned version
    fi

    echo "$version"
}

# Fetch latest version from GitHub API
fetch_latest_version() {
    local response

    # Use curl with timeout, fail silently on any error
    response=$(curl -fsSL --connect-timeout 3 --max-time 5 "$GITHUB_API" 2>/dev/null) || return 1

    # Extract tag_name (e.g., "v1.0.0")
    local tag
    tag=$(echo "$response" | grep -o '"tag_name": *"[^"]*"' | head -1 | cut -d'"' -f4)

    if [[ -z "$tag" ]]; then
        return 1
    fi

    # Remove 'v' prefix if present
    echo "${tag#v}"
}

# Compare versions (returns 0 if $1 < $2, meaning update available)
version_lt() {
    local v1="$1"
    local v2="$2"

    # Simple string comparison for semver (works for X.Y.Z format)
    if [[ "$v1" == "$v2" ]]; then
        return 1  # Same version
    fi

    # Use sort -V for proper version comparison
    local lowest
    lowest=$(printf '%s\n%s\n' "$v1" "$v2" | sort -V | head -1)

    [[ "$v1" == "$lowest" ]]
}

# ═══════════════════════════════════════════════════════════════════════════════
# NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════════════════════

# Display update available notification
notify_update() {
    local current="$1"
    local latest="$2"

    echo ""
    echo -e "${BOLD}${CYAN}🚀 Devcontainer Update Available${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "  Current: ${YELLOW}$current${NC}  →  Latest: ${GREEN}$latest${NC}"
    echo ""
    echo -e "  Run from a ${BOLD}host terminal${NC} (not inside the container):"
    echo ""
    echo -e "    ${BOLD}just devcontainer-upgrade${NC}"
    echo ""
    echo -e "  Or without just:"
    echo ""
    echo -e "    curl -sSf https://vig-os.github.io/devcontainer/install.sh | sh -s -- --force ."
    echo ""
    echo -e "  After upgrading, rebuild the container in VS Code."
    echo ""
    echo -e "  Mute: ${BOLD}just check 7d${NC}    Disable: ${BOLD}just check off${NC}"
    echo ""
}

# ═══════════════════════════════════════════════════════════════════════════════
# COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

cmd_check() {
    load_config

    # Check if enabled
    if [[ "$CHECK_ENABLED" != "true" ]]; then
        log_verbose "Version check disabled"
        return 0
    fi

    # Check if muted
    if is_muted; then
        local muted_ts
        muted_ts=$(cat "$MUTED_UNTIL_FILE")
        log_verbose "Notifications muted until $(date -d @"$muted_ts" 2>/dev/null || date -r "$muted_ts")"
        return 0
    fi

    # Check if we should check (interval throttling)
    if ! $VERBOSE && ! should_check; then
        log_verbose "Check interval not reached"
        return 0
    fi

    # Get current version
    local current
    current=$(get_current_version) || {
        log_verbose "Could not determine current version (dev/latest/not found)"
        return 0
    }

    log_verbose "Current version: $current"

    # Fetch latest version
    local latest
    latest=$(fetch_latest_version) || {
        log_verbose "Could not fetch latest version from GitHub"
        $SILENT_FAIL && fail_silent
        return 1
    }

    log_verbose "Latest version: $latest"

    # Record that we checked
    record_check

    # Cache latest version
    ensure_local_dir
    echo "$latest" > "$CACHE_FILE"

    # Compare versions
    if version_lt "$current" "$latest"; then
        notify_update "$current" "$latest"
    else
        log_verbose "You're up to date!"
    fi
}

cmd_mute() {
    local duration="$1"

    local seconds
    seconds=$(parse_duration "$duration") || {
        echo "Invalid duration format: $duration"
        echo "Use: And (days), Nw (weeks), Nh (hours), Nm (minutes)"
        echo "Examples: 7d, 1w, 12h, 30m"
        return 1
    }

    ensure_local_dir
    local until_ts=$(($(date +%s) + seconds))
    echo "$until_ts" > "$MUTED_UNTIL_FILE"

    echo "✓ Update notifications muted for $(format_duration "$seconds")"
}

cmd_enable() {
    load_config
    CHECK_ENABLED="true"
    save_config
    rm -f "$MUTED_UNTIL_FILE"
    echo "✓ Update notifications enabled"
}

cmd_disable() {
    load_config
    CHECK_ENABLED="false"
    save_config
    echo "✓ Update notifications disabled"
}

cmd_set_interval() {
    local duration="$1"

    local seconds
    seconds=$(parse_duration "$duration") || {
        echo "Invalid duration format: $duration"
        echo "Use: And (days), Nw (weeks), Nh (hours), Nm (minutes)"
        return 1
    }

    load_config
    CHECK_INTERVAL="$seconds"
    save_config

    echo "✓ Check interval set to $(format_duration "$seconds")"
}

cmd_show_config() {
    load_config

    echo "Devcontainer Update Check Configuration"
    echo "───────────────────────────────────────"
    echo "Enabled:        $CHECK_ENABLED"
    echo "Check interval: $(format_duration "$CHECK_INTERVAL")"

    if [[ -f "$MUTED_UNTIL_FILE" ]]; then
        local muted_until
        muted_until=$(cat "$MUTED_UNTIL_FILE")
        local now
        now=$(date +%s)
        if [[ $now -lt $muted_until ]]; then
            local remaining=$((muted_until - now))
            echo "Muted for:      $(format_duration "$remaining") remaining"
        fi
    fi

    if [[ -f "$LAST_CHECK_FILE" ]]; then
        local last_check
        last_check=$(cat "$LAST_CHECK_FILE")
        # Cross-platform date formatting
        if date --version >/dev/null 2>&1; then
            echo "Last check:     $(date -d @"$last_check" '+%Y-%m-%d %H:%M:%S')"
        else
            echo "Last check:     $(date -r "$last_check" '+%Y-%m-%d %H:%M:%S')"
        fi
    else
        echo "Last check:     never"
    fi

    # Show current and latest versions if known
    local current
    current=$(get_current_version 2>/dev/null) || current="unknown"
    echo "Current ver:    $current"

    if [[ -f "$CACHE_FILE" ]]; then
        echo "Latest ver:     $(cat "$CACHE_FILE")"
    fi

    echo "───────────────────────────────────────"
    echo "Config file:    $CONFIG_FILE"
}

cmd_help() {
    sed -n '/^###############################################################################$/,/^###############################################################################$/p' "$0" | sed '1d;$d'
}

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

main() {
    # Default: silent check
    if [[ $# -eq 0 ]]; then
        SILENT_FAIL=true
        cmd_check
        exit 0
    fi

    # Parse arguments
    case "${1:-}" in
        check)
            VERBOSE=true
            SILENT_FAIL=false
            cmd_check
            ;;
        mute)
            [[ -z "${2:-}" ]] && { echo "Usage: $0 mute <duration>"; exit 1; }
            cmd_mute "$2"
            ;;
        on|enable)
            cmd_enable
            ;;
        off|disable)
            cmd_disable
            ;;
        interval)
            [[ -z "${2:-}" ]] && { echo "Usage: $0 interval <duration>"; exit 1; }
            cmd_set_interval "$2"
            ;;
        config|status)
            cmd_show_config
            ;;
        --help|-h|help)
            cmd_help
            ;;
        *)
            echo "Unknown option: $1"
            cmd_help
            exit 1
            ;;
    esac
}

main "$@"
