#!/bin/bash
# Deploy script for Schlüsselkasten V2
# Pulls the latest code from GitHub, sets version.py from the current git tag,
# and restarts the systemd user service.
#
# Usage: ./deploy.sh [remote] [branch]
#   remote  Git remote to pull from (default: origin)
#   branch  Git branch to pull      (default: current branch)

set -e

# Resolve the repository directory relative to this script so the script works
# regardless of the working directory from which it is called.
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE="schluesselkasten.service"

cd "$REPO_DIR"

REMOTE="${1:-origin}"
BRANCH="${2:-$(git rev-parse --abbrev-ref HEAD)}"

# ---------------------------------------------------------------------------
# Stop service
# ---------------------------------------------------------------------------
echo "Stopping $SERVICE..."
if systemctl is-active --user --quiet "$SERVICE"; then
    systemctl --user stop "$SERVICE"
    echo "$SERVICE stopped."
else
    echo "$SERVICE was not running."
fi

# ---------------------------------------------------------------------------
# Pull latest code
# ---------------------------------------------------------------------------
echo "Pulling latest code from $REMOTE/$BRANCH..."
git pull --ff-only "$REMOTE" "$BRANCH"

# ---------------------------------------------------------------------------
# Determine version from git tag
# ---------------------------------------------------------------------------
TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")

if [ -z "$TAG" ]; then
    echo "Warning: no git tag found, version.py will not be updated."
else
    # Validate that the tag only contains characters safe for a Python string
    # (letters, digits, dots, hyphens, underscores).
    if [[ ! "$TAG" =~ ^[A-Za-z0-9._-]+$ ]]; then
        echo "Warning: tag '$TAG' contains unexpected characters; version.py will not be updated."
    else
        echo "Setting version to: $TAG"
        cat > version.py <<EOF
# Single source of truth for the software version string.
# All modules import from here instead of defining __version__ locally.

__version__ = "$TAG"
EOF
    fi
fi

# ---------------------------------------------------------------------------
# Restart service
# ---------------------------------------------------------------------------
echo "Starting $SERVICE..."
systemctl --user start "$SERVICE"
echo "Deploy complete. Service status:"
systemctl --user status "$SERVICE" --no-pager
