#!/bin/bash
# ESP Curriculum Dashboard — deploy to GitHub Pages
# Double-click this file (or run it in Terminal) to push updates.
# Automatically syncs with any remote changes first so no manual pull needed.

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# Stage and commit any local changes
git add .
if git diff --cached --quiet; then
  echo "No local changes to commit."
else
  git commit -m "Update dashboard $(date '+%Y-%m-%d %H:%M')"
fi

# Pull remote changes (e.g. the daily auto-refresh commit) via rebase
# This keeps the history clean and never needs a manual pull
echo "Syncing remote changes..."
git pull --rebase origin main

# Push
echo "Pushing to GitHub..."
git push origin main

echo ""
echo "✅ Deployed! Live at:"
echo "   https://piques-smudgy.github.io/esp-curriculum-dashboard/"
echo ""
read -p "Press Enter to close…"
