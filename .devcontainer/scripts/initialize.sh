#!/bin/bash

# Initialize script - runs on host before container starts
# This script is called from initializeCommand in devcontainer.json

set -euo pipefail

echo "Initializing devcontainer setup..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEVCONTAINER_DIR="$(dirname "$SCRIPT_DIR")"

# Copy host user configuration (git, ssh, gh)
"$SCRIPT_DIR/copy-host-user-conf.sh"

# Load devcontainer version from root .vig-os config
load_vig_os_config() {
    local config_file="$DEVCONTAINER_DIR/../.vig-os"
    local env_file="$DEVCONTAINER_DIR/.env"
    local devcontainer_version=""

    if [[ ! -f "$config_file" ]]; then
        return 0
    fi

    while IFS= read -r line || [[ -n "${line:-}" ]]; do
        [[ -z "${line//[[:space:]]/}" ]] && continue
        [[ "$line" =~ ^[[:space:]]*# ]] && continue

        case "$line" in
            DEVCONTAINER_VERSION=*)
                devcontainer_version="${line#*=}"
                devcontainer_version="${devcontainer_version#"${devcontainer_version%%[![:space:]]*}"}"
                devcontainer_version="${devcontainer_version%"${devcontainer_version##*[![:space:]]}"}"

                if [[ "$devcontainer_version" =~ ^\".*\"$ ]]; then
                    devcontainer_version="${devcontainer_version:1:-1}"
                elif [[ "$devcontainer_version" =~ ^\'.*\'$ ]]; then
                    devcontainer_version="${devcontainer_version:1:-1}"
                fi
                break
                ;;
        esac
    done < "$config_file"

    if [[ -z "$devcontainer_version" ]]; then
        return 0
    fi

    if [[ -f "$env_file" ]] && grep -q "^DEVCONTAINER_VERSION=" "$env_file" 2>/dev/null; then
        if [[ "$(uname -s)" == "Darwin" ]]; then
            sed -i '' "s|^DEVCONTAINER_VERSION=.*|DEVCONTAINER_VERSION=${devcontainer_version}|" "$env_file"
        else
            sed -i "s|^DEVCONTAINER_VERSION=.*|DEVCONTAINER_VERSION=${devcontainer_version}|" "$env_file"
        fi
    else
        echo "DEVCONTAINER_VERSION=${devcontainer_version}" >> "$env_file"
    fi
}

# Configure container socket path based on host OS
configure_socket_path() {
    local env_file="$DEVCONTAINER_DIR/.env"
    local socket_path=""
    local os_type=""

    # Detect OS and determine socket path by probing
    # NOTE: This devcontainer is configured for Podman by default.
    # To use Docker Desktop instead, swap the order of checks below
    # (check /var/run/docker.sock first instead of Podman socket).

    case "$(uname -s)" in
        Darwin)
            os_type="macOS"
            local uid
            uid=$(id -u)

            # Check Podman socket in VM first (Podman-first approach)
            if [[ -S "/run/user/${uid}/podman/podman.sock" ]]; then
                os_type="Podman (macOS)"
                socket_path="/run/user/${uid}/podman/podman.sock"
            # Fallback to Docker Desktop if Podman not available
            elif [[ -S "/var/run/docker.sock" ]]; then
                os_type="Docker Desktop (macOS)"
                socket_path="/var/run/docker.sock"
            else
                # Default to Podman path (created when podman machine starts)
                echo "Warning: No socket found, defaulting to Podman path"
                socket_path="/run/user/${uid}/podman/podman.sock"
            fi
            ;;
        Linux)
            os_type="Linux"
            local uid
            uid=$(id -u)

            # Check for rootless Podman socket first (Podman-first approach)
            if [[ -S "/run/user/${uid}/podman/podman.sock" ]]; then
                os_type="Podman rootless (Linux)"
                socket_path="/run/user/${uid}/podman/podman.sock"
            # Fallback to Docker socket (Docker Desktop or native Docker)
            elif [[ -S "/var/run/docker.sock" ]]; then
                os_type="Docker (Linux)"
                socket_path="/var/run/docker.sock"
            else
                # Default to rootless Podman path
                echo "Warning: No socket found, defaulting to Podman path"
                socket_path="/run/user/${uid}/podman/podman.sock"
            fi
            ;;
        *)
            echo "Warning: Unsupported OS '$(uname -s)', using default socket path"
            socket_path="/var/run/docker.sock"
            ;;
    esac

    echo "Detected: $os_type"
    echo "Configuring socket path: $socket_path"

    # Write socket path to .env file (docker-compose auto-loads this)
    # Check if CONTAINER_SOCKET_PATH is already set in .env
    if [[ -f "$env_file" ]] && grep -q "^CONTAINER_SOCKET_PATH=" "$env_file" 2>/dev/null; then
        # Update existing value
        if [[ "$(uname -s)" == "Darwin" ]]; then
            sed -i '' "s|^CONTAINER_SOCKET_PATH=.*|CONTAINER_SOCKET_PATH=${socket_path}|" "$env_file"
        else
            sed -i "s|^CONTAINER_SOCKET_PATH=.*|CONTAINER_SOCKET_PATH=${socket_path}|" "$env_file"
        fi
    else
        # Append to .env file (create if doesn't exist)
        echo "CONTAINER_SOCKET_PATH=${socket_path}" >> "$env_file"
    fi

    echo "Socket configuration complete (written to .env)"
}

load_vig_os_config
configure_socket_path

echo "Initialization complete"
