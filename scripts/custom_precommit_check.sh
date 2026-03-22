#!/usr/bin/env bash
set -euo pipefail

# Get list of staged files
STAGED_FILES=$(git diff --staged --name-only --diff-filter=ACM 2>/dev/null || true)

if [[ -z "$STAGED_FILES" ]]; then
    exit 0
fi

# Get staged diff content
STAGED_DIFF=$(git diff --staged --diff-filter=ACM 2>/dev/null || true)

# Check for API keys from environment
FAILED=0
while IFS= read -r API_KEY; do
    if [[ -n "$API_KEY" ]] && echo "$STAGED_DIFF" | grep -qF "$API_KEY"; then
        echo "ERROR: Potential API key exposure detected!"
        echo "Found: $API_KEY"
        FAILED=1
    fi
done < <(env | grep API_KEY | cut -d'=' -f2)

# Check for username exposure
USERNAME="${USERNAME:-$(whoami)}"
if [[ -n "$USERNAME" ]] && echo "$STAGED_DIFF" | grep -qF "/$USERNAME/"; then
    echo "ERROR: Potential username path exposure detected!"
    echo "Found: /$USERNAME/"
    FAILED=1
fi

if [[ $FAILED -eq 1 ]]; then
    echo ""
    echo "Pre-commit check failed. Please review the staged changes."
    exit 1
fi

exit 0
