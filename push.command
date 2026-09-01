#!/bin/bash
# ESP Curriculum Dashboard — deploy to GitHub Pages
# Double-click this file to push updates

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

git add index.html
git commit -m "Update dashboard $(date '+%Y-%m-%d %H:%M')"
git push origin main

echo ""
echo "✅ Deployed! Live at:"
echo "   https://piques-smudgy.github.io/esp-curriculum-dashboard/"
echo ""
read -p "Press Enter to close…"
