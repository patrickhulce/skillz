---
name: commit-it
description: Organize mixed-purpose changes into logical, separate commits with scope-style commit messages. Use when the user has multiple unrelated changes (bug fixes, features, refactoring) mixed together and wants to split them into clean, semantic commits. This skill provides a safe workflow with checkpoint backups before reorganizing changes.
---

# Scoped Commits

Safely organize mixed-purpose changes into logical, focused commits with scope-style commit messages.

## Overview

When working on multiple tasks simultaneously, changes often get mixed together. This skill helps untangle these changes and create clean, semantic commits that each represent a single logical change.

**Key benefits:**

- **Safe**: Creates checkpoint backup before any changes
- **Transparent**: Prints grouping details with a brief pause before executing
- **Semantic**: Groups changes by purpose, not by file
- **Clean history**: Each commit tells a clear story

## Workflow

### 1. Analyze Current Changes

First, review all changes to understand what's in the working directory:

```bash
git status          # See which files are modified
git diff            # Review unstaged changes
git diff --cached   # Review staged changes
```

Read through the changes and understand what each modification accomplishes. Look for:

- Bug fixes
- New features
- Refactoring
- Performance improvements
- Documentation changes
- Style/formatting changes

### 2. Create Safety Checkpoint

**ALWAYS create a checkpoint before reorganizing commits.** This provides a safe rollback point.

Use the `./scripts/checkpoint.sh` script to create a safety checkpoint which does the following:

1. Stages all changes (git add -A)
2. Creates a checkpoint commit with descriptive message
3. Save the checkpoint commit hash to `~/.claude/semantic-commits/<timestamp>.checkpoint`
4. Mixed reset (`git reset --mixed HEAD~1`) to undo the commit and leave all changes UNSTAGED
5. Print the checkpoint hash for future reference

After running, all changes are unstaged and ready to be organized. (A `--soft` reset would leave everything staged, which defeats the purpose — the script deliberately uses a mixed reset.)

**Example output:**

```
Staging all changes...
Creating checkpoint commit...
✓ Checkpoint created: a1b2c3d4
✓ Saved to: .claude/20240315-143022.checkpoint
Resetting to unstage all changes...
✓ All changes are now unstaged and ready to be organized.

You can restore this checkpoint with:
  git reset --soft a1b2c3d4
```

### 3. Determine Semantic Groupings

Analyze the changes semantically and determine logical groupings. Each group should:

- Represent a single logical change (one purpose)
- Have a clear scope-style commit message
- Include all related changes, even across multiple files

**See references/workflow-example.md for a detailed example.**

**Important considerations:**

- Group by PURPOSE, not by file - related changes across files should be together
- Each group should be independently deployable if possible
- Consider the git log reader - each commit should tell a clear story
- Separate breaking changes and call them out with `!` after the scope

### 4. Print Grouping Details

Before executing, print the full details of each group so the user can see what will be committed. Use this format:

```markdown
## Commit Groups

### Group 1: `scope: brief description`

**Files:**

- `path/to/file1.py` (lines X-Y, entire file, or specific change description)
- `path/to/file2.py` (lines A-B)
  **Purpose:** [Brief explanation of what this group accomplishes]

---

### Group 2: `scope: brief description`

...
```

### 5. Execute Commits

Execute each commit in order:

For each group:

**5a. Validate the scope**

Before staging, confirm the chosen scope is valid for this repo:

```bash
./scripts/validate-scope.sh <scope>
```

This enforces the project's scope rules (see "Scoped Commit Reference" below). Fix the scope if it is rejected.

**5b. Stage the specific changes**

Depending on whether entire files or partial files are involved:

- **Entire files:** Git add directly:

    ```bash
    git add file1.py file2.py
    ```

- **Partial files (multiple changes in same file):** Use interactive staging:

    ```bash
    git add -p path/to/file.py
    ```

    Review each hunk and type `y` to stage hunks belonging to this group, `n` to skip others.

- **Complex partial staging:** Use git add with edit mode:
    ```bash
    git add -e path/to/file.py
    ```

**5c. Verify staged changes**

Before committing, verify that only the intended changes are staged:

```bash
git diff --cached
```

**5d. Create the commit**

Use the approved scope-style commit message:

```bash
git commit -m "scope: description

Optional body explaining the change in more detail."
```

**5e. Repeat for remaining groups**

Continue with the next group until all changes are committed.

### 6. Verify Completion

After all commits:

```bash
git status  # Should show clean working directory
git log --oneline -n <number-of-commits>  # Verify all commits
git diff $(cat ~/.claude/semantic-commits/<timestamp>.checkpoint) --stat  # Verify nothing lost
```

If any changes remain uncommitted, either:

- Create an additional commit for them
- Investigate why they weren't included in any group

## Safety Features

- **Checkpoint backup**: Can always return to the checkpoint state
- **Mixed reset**: No changes are lost — the commit is undone and all edits return unstaged
- **Printed details with pause**: Grouping details are printed and a 5s pause gives the user a chance to interrupt
- **Staged change verification**: Review each group before committing
- **Rollback instructions**: Checkpoint file contains restore command

**To restore checkpoint:**

```bash
# Soft reset (preserves changes in working directory)
git reset --soft $(cat ~/.claude/semantic-commits/<timestamp>.checkpoint)

# Hard reset (WARNING: discards all changes)
git reset --hard $(cat ~/.claude/semantic-commits/<timestamp>.checkpoint)
```

## Scoped Commit Reference

This project follows the [Scoped Commits](https://scopedcommits.com/) convention. Commit messages put the affected scope up front so the log is easy to scan:

```
<scope>: <description>

[optional body]

[optional footer]
```

**Choosing the scope:**

- **Monorepo:** the scope MUST be a package name (a workspace member) OR a narrow global: `scripts`, `ci`, or `docs`.
- **Single-package repo:** the scope MUST be a directory or an extensionless file path that locates the change in the tree, OR a narrow global: `scripts`, `ci`, or `docs`.
    - It is always a subdirectory (`utils`, `auth`, `components`) or a path down to a specific extensionless file (`utils/jwt`, `components/file-picker`, `pages/foo`).
    - It NEVER includes a file extension — use `utils/jwt`, not `utils/jwt.ts`.
    - It NEVER names a nested file without its folder — use `components/file-picker`, not just `file-picker`.
    - No spaces.
    - Good: `components/file-picker`, `utils/jwt`, `utils`, `auth`, `pages/foo`. Bad: `jwt.ts`, `file-picker`, `the auth module`.
- **Whole-tree changes:** use `treewide`.
- **A commit spanning multiple scopes:** pick a broader scope that encompasses them (e.g. the common parent directory), list scopes comma-separated, or split the commit so each one fits a single scope.

Validate any scope before committing:

```bash
./scripts/validate-scope.sh <scope>
```

**Breaking changes:** Add `!` after the scope: `api!: change response format`

**Description rules:**

- Imperative mood (e.g., "add", "fix", "update", not "added", "fixes")
- Lowercase
- No period at end
- Brief (50 chars or less for first line)

## Best Practices

1. **Analyze before grouping** - Read all changes first to understand the full picture
2. **One logical change per commit** - Each commit should have a single clear purpose
3. **Include all related changes** - Don't split logically-related code across commits
4. **Write clear commit messages** - Future developers (including you) will thank you
5. **Verify each commit** - Review `git diff --cached` before each commit
6. **Keep commits focused** - Better to have many small commits than few large ones
7. **Consider reviewers** - Each commit should be independently reviewable

## Troubleshooting

**"I made a mistake in the groupings"**

- Reset to the checkpoint and start over
- Or use `git reset --soft HEAD~N` to undo N commits and regroup

**"Some changes are hard to separate"**

- Consider if they're truly separate logical changes
- Use `git add -p` and review each hunk carefully
- For complex cases, use `git add -e` to manually edit the patch

**"Changes span too many files"**

- That's okay! A logical change can span multiple files
- What matters is that they serve a single purpose

**"The scope was rejected by validate-scope.sh"**

- In a monorepo, the scope must match a workspace package name or be one of `scripts`, `ci`, `docs`
- Outside a monorepo, drop spaces from the scope or use a narrower subsystem name
- If the change truly spans the whole tree, use `treewide`
