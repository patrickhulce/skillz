---
name: prune-it
description: Examine all local git branches, assess whether changes landed or were solved on main, delete fully landed branches without asking, prompt before deleting partially addressed branches with novel work, and rebase active novel branches against origin/main resolving all conflicts. Use when the user says "prune-it", "prune branches", "clean up branches", "audit branches", "tidy branches", "reconcile branches", or asks to assess the state of local branches.
---

# Prune and Rebase Local Branches (`prune-it`)

Audit every local git branch against the latest `origin/main`. Prune fully landed branches, prompt before deleting partially addressed branches that contain novel work, and rebase active novel branches onto main with all conflicts resolved.

**End state:** every local branch left in the repository is active, relevant, and cleanly rebased on top of the latest `origin/main`.

## Principles

1. **Delete landed branches silently**: If a branch's changes are already on main (merged, squash-merged, or cherry-picked), delete it immediately without asking.
2. **Never lose novel work without confirmation**: If the main problem was addressed on main but the branch contains novel fixes, extra test cases, or unmerged features, present a summary of the missing work and ask the user before deleting.
3. **Rebase and resolve conflicts**: Actively novel branches are kept and rebased onto `origin/main`, with conflicts resolved intelligently.
4. **Clean restoration**: Always return the user to their original branch (or default branch if deleted) and restore any stashed state.

## Workflow

### 1. Preflight and Remote Sync

Check working tree status, identify the default branch, and fetch latest state from origin:

```bash
# 1. Require or preserve a clean working tree
git status --porcelain

# If there are uncommitted changes, stash them safely:
# git stash push -u -m "prune-it: pre-audit stash $(date +%s)"

# 2. Record the current branch
START_BRANCH=$(git branch --show-current)

# 3. Detect default branch (main or master)
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "main")
[ -z "$DEFAULT_BRANCH" ] && DEFAULT_BRANCH="main"

# 4. Fetch latest refs and prune stale remote tracking
git fetch origin --prune

# 5. List all local candidate branches (excluding default branch)
CANDIDATE_BRANCHES=$(git for-each-ref --format='%(refname:short)' refs/heads/ | grep -v -E "^(${DEFAULT_BRANCH}|main|master)$" || true)
```

If `CANDIDATE_BRANCHES` is empty, inform the user that no local feature branches exist and stop.

---

### 2. Assess Each Branch

Iterate through each candidate branch and classify it into one of three tiers:

```bash
BASE=$(git merge-base "origin/$DEFAULT_BRANCH" "$BRANCH")
```

#### Tier 1: Landed As-Is (Delete without asking)

A branch is classified as **landed as-is** if any of the following are true:

1. **Direct ancestor**: `git merge-base --is-ancestor "$BRANCH" "origin/$DEFAULT_BRANCH"` succeeds (commit SHAs are directly in main's history).
2. **Patch equivalence (cherry-picks / rebase-merges)**:
   ```bash
   # If git cherry shows only '-' (all commits equivalent to main)
   UNLANDED=$(git cherry "origin/$DEFAULT_BRANCH" "$BRANCH" | grep -v '^-' || true)
   ```
   If `$UNLANDED` is empty, all commits on the branch were applied to main.
3. **Squash-merged with identical changes**:
   - `git diff "origin/$DEFAULT_BRANCH...$BRANCH"` shows no changes that aren't already represented in `origin/$DEFAULT_BRANCH`.
   - Or `gh pr list --state merged --head "$BRANCH"` confirms the branch PR was merged, and `git log origin/$DEFAULT_BRANCH..$BRANCH` contains no subsequent unpushed commits.
4. **Empty branch**: `git rev-list --count "origin/$DEFAULT_BRANCH..$BRANCH"` is 0.

**Action:**
Delete the branch immediately without prompting:
```bash
git branch -D "$BRANCH"
```
Record in summary: `Deleted (landed as-is)`.

---

#### Tier 2: Concern Mostly Addressed, but Novel Work Remains (Prompt User)

A branch fits this category when:

- The core feature, issue, or bug was addressed on `main` (for instance, a related PR merged, or files were rewritten on main solving the same problem), **BUT**:
- The branch still contains novel changes that are NOT on main:
  - Additional edge case fixes or defensive checks
  - Extra unit/integration test cases
  - Distinct refactorings or utility functions
  - Documentation, comments, or alternative implementations

**Inspection commands:**

```bash
# View unique commits on this branch
git log --oneline "origin/$DEFAULT_BRANCH..$BRANCH"

# Inspect the novel diff against merge-base and against latest main
git diff --stat "$BASE..$BRANCH"
git diff "origin/$DEFAULT_BRANCH...$BRANCH"
```

**Action:**

Do NOT delete silently. Present a concise assessment to the user:
1. Explain how the primary concern was addressed on `main` (cite commits or PRs if known).
2. List the specific novel commits, files, or functions that only exist on this branch.
3. Ask the user via `AskQuestion` (or structured prompt):
   - **Delete branch**: Confirm the novel changes are unneeded, obsolete, or abandoned (`git branch -D "$BRANCH"`).
   - **Keep & rebase**: Rebase onto `origin/$DEFAULT_BRANCH` and keep the branch active.
   - **Cherry-pick novel work**: Extract the specific novel commits into a new branch before deleting.

---

#### Tier 3: Obviously Novel / Unaddressed (Rebase onto main)

A branch fits this category when:

- The branch represents active, unmerged work (novel feature, pending bugfix, ongoing experiment).
- None or few of its commits exist in `origin/$DEFAULT_BRANCH`.

**Action:**

Rebase the branch against the updated default branch and resolve all conflicts:

```bash
git checkout "$BRANCH"
git rebase "origin/$DEFAULT_BRANCH"
```

##### Handling Rebase Conflicts

If rebase encounters conflicts:

1. **Inspect conflicting files**:
   ```bash
   git status --porcelain
   ```
2. **Review conflicting hunks**:
   - Read the conflict markers (`<<<<<<< HEAD`, `=======`, `>>>>>>>`).
   - `HEAD` is the updated state from `origin/$DEFAULT_BRANCH`.
   - The incoming commit is the branch's change being replayed.
3. **Resolve conflicts preserving intent**:
   - Keep the upstream improvements from main while integrating the branch's novel feature or fix.
   - Never blindly accept `--ours` or `--theirs` without inspecting code semantics.
   - If an incoming commit's changes are completely superseded or already incorporated by main, skip it:
     ```bash
     git rebase --skip
     ```
   - Otherwise, stage the resolved files and continue:
     ```bash
     git add <resolved-files>
     git rebase --continue
     ```
4. **Genuinely ambiguous conflicts**:
   - If a conflict represents an architectural impasse or breaking semantic conflict that cannot be resolved with certainty, pause and consult the user with the exact conflicting hunks before making destructive choices.

Record in summary: `Rebased (clean)` or `Rebased (conflicts resolved)`.

---

### 3. Restoration and Summary

After evaluating all candidate branches:

1. **Return to appropriate branch**:
   - If `START_BRANCH` still exists, switch back: `git checkout "$START_BRANCH"`.
   - If `START_BRANCH` was deleted (it landed), switch to the default branch: `git checkout "$DEFAULT_BRANCH"`.
2. **Restore stashed changes** if any were stashed during preflight:
   ```bash
   git stash pop
   ```
3. **Output Audit Report**:
   Print a markdown summary table of all branches evaluated:

```markdown
## Branch Audit Summary

| Branch | Assessment | Action Taken | Details |
|---|---|---|---|
| `fix/auth-leak` | Landed as-is (squash-merged) | Deleted | Changes present in origin/main |
| `feature/user-profile` | Mostly addressed, had 2 extra tests | Kept & Rebased | User confirmed; preserved novel tests |
| `feature/v2-parser` | Obviously novel | Rebased | Conflicts resolved in `parser.py` |
| `spike/old-cache` | Mostly addressed | Deleted | User confirmed obsolete |
```

---

## Decision Matrix

| State vs `origin/main` | Condition | Default Action | User Prompt Required? |
|---|---|---|---|
| **Landed as-is** | Merged, cherry-picked, or empty diff | `git branch -D <branch>` | No |
| **Mostly addressed** | Core solved, but novel hunks/commits remain | Present novel diff & options | Yes |
| **Novel / Active** | Independent unmerged feature or fix | Rebase onto `origin/main` | No (unless conflict is ambiguous) |

---

## Conflict Resolution Guidelines

- **Preserve branch features**: When main modified adjacent code or imports, update the branch's calls to use the new imports/signatures while preserving the branch's logic.
- **Verify syntax and tests**: After resolving conflicts on a branch, run quick lint or tests if available (e.g. `uv run pytest` or `npm test`) before concluding.
- **Never force push**: This skill operates on local branches only. Remote pushes belong to `ship-it` or explicit user commands.

## What NOT to do

- Do not delete `main`, `master`, or the repository's default branch.
- Do not delete branches with uncommitted or unmerged novel work without explicit user confirmation.
- Do not push or force-push branches to remote origins.
- Do not leave the repository in a detached HEAD or mid-rebase state. If an error occurs, clean up or abort the in-progress rebase (`git rebase --abort`).
