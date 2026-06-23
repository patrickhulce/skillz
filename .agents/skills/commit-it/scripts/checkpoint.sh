#!/bin/bash
# checkpoint.sh - Safely create a checkpoint commit with all changes
#
# Usage: ./checkpoint.sh
#
# This script:
# 1. Stages all changes (tracked and untracked)
# 2. Creates a checkpoint commit
# 3. Saves the commit hash to ~/.claude/semantic-commits/<timestamp>.checkpoint
# 4. Returns the checkpoint hash

set -e

# Ensure we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "Error: Not in a git repository" >&2
    exit 1
fi

# Create checkpoints directory if it doesn't exist
CHECKPOINT_DIR="$HOME/.claude/semantic-commits"
mkdir -p "$CHECKPOINT_DIR"

# Generate timestamp
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
CHECKPOINT_FILE="$CHECKPOINT_DIR/$TIMESTAMP.checkpoint"

# Check if there are any changes to commit
if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
    echo "Error: No changes to checkpoint" >&2
    exit 1
fi

# Remember the commit we were on (if any) so we can return to it precisely.
PREV_HEAD=$(git rev-parse --verify HEAD 2>/dev/null || echo "")

# Stage all changes (tracked modifications and new files)
echo "Staging all changes..."
git add -A

# Create checkpoint commit
echo "Creating checkpoint commit..."
git commit -m "checkpoint: safe backup before semantic commit reorganization

This checkpoint was automatically created before reorganizing mixed changes
into semantic commits. Hash saved to: $TIMESTAMP.checkpoint" --no-verify > /dev/null

# Record the checkpoint commit hash directly from git
CHECKPOINT_HASH=$(git rev-parse HEAD)

# Save checkpoint hash to file
echo "$CHECKPOINT_HASH" > "$CHECKPOINT_FILE"

echo "✓ Checkpoint created: $CHECKPOINT_HASH"
echo "✓ Saved to: $CHECKPOINT_FILE"

# Undo the commit AND unstage everything, keeping the edits in the working tree,
# so changes come back UNSTAGED and ready to be regrouped with `git add -p`.
# A mixed reset (the default) resets the index but leaves the working tree.
# NOTE: do NOT use `--soft` here — that leaves everything staged, which is the
# whole bug this avoids.
echo "Resetting to unstage all changes..."
if [ -n "$PREV_HEAD" ]; then
    git reset --mixed "$PREV_HEAD" > /dev/null
else
    # The checkpoint was the repository's first commit (no prior HEAD). Remove
    # the commit and clear the index so every file returns as an unstaged change.
    git update-ref -d HEAD
    git rm -r --cached . > /dev/null 2>&1 || true
fi

echo "✓ All changes are now unstaged and ready to be organized."
echo ""
echo "You can restore this checkpoint with:"
echo "  git reset --soft $CHECKPOINT_HASH"
echo "  or"
echo "  git reset --hard $CHECKPOINT_HASH  # WARNING: Discards all changes"

# Output just the hash for scripting
echo "$CHECKPOINT_HASH"
