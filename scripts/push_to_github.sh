#!/usr/bin/env bash
# One-time helper to push this project to a new GitHub repo.
# Usage: edit REPO_URL below, then: bash scripts/push_to_github.sh
set -euo pipefail
REPO_URL="git@github.com:YOUR_USERNAME/autolog-triage.git"   # <-- edit this

git init
git add .
git commit -m "Initial commit: autonomous multi-agent automotive test-log triage"
git branch -M main
git remote add origin "$REPO_URL"
git push -u origin main
echo "Pushed to $REPO_URL"
