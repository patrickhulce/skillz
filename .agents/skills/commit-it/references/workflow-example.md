# Scoped Commits Workflow Example

This document shows a concrete example of analyzing mixed changes and grouping them into semantic commits.

## Example Scenario

### Initial State

Working directory has these mixed changes:

- `auth.py`: Bug fix for token expiration (lines 45-52)
- `auth.py`: Added logging for auth failures (lines 103-107)
- `database.py`: Fixed connection pooling bug (lines 28-35)
- `database.py`: Added retry logic (lines 89-102)
- `api.py`: New endpoint for user preferences (lines 201-245)
- `utils.py`: Refactored error handling (lines 12-67)
- `utils.py`: Added helper function for auth (lines 102-115)

### Analysis Process

**Step 1: Review all changes**

```bash
git diff
git diff --cached  # If any changes are already staged
git status
```

**Step 2: Identify logical groupings by purpose**

Analyze each change semantically:

- What is the change trying to accomplish?
- What is the business/technical reason for the change?
- Are there related changes in other files?

**Step 3: Proposed groupings**

**Group 1: Authentication token expiration fix**

- `auth.py` lines 45-52 (token expiration fix)
- `utils.py` lines 102-115 (auth helper function)
- Purpose: Fix bug where tokens weren't being validated correctly
- Commit message: `auth: validate token expiration correctly`

**Group 2: Database connection improvements**

- `database.py` lines 28-35 (connection pooling fix)
- `database.py` lines 89-102 (retry logic)
- Purpose: Improve database reliability and connection handling
- Commit message: `database: improve connection pooling and add retry logic`

**Group 3: Enhanced observability**

- `auth.py` lines 103-107 (logging for auth failures)
- Purpose: Better debugging for authentication issues
- Commit message: `auth: add logging for failures`

**Group 4: User preferences endpoint**

- `api.py` lines 201-245 (new endpoint)
- Purpose: New feature for user preferences
- Commit message: `api: add user preferences endpoint`

**Group 5: Error handling refactor**

- `utils.py` lines 12-67 (error handling refactor)
- Purpose: Improve error handling consistency
- Commit message: `utils: standardize error handling patterns`

### Staging Strategy

For each group, the staging approach depends on whether entire files or partial files need to be staged:

**Entire file changes:**

```bash
git add api.py  # Group 4 - entire file is new feature
```

**Partial file changes:**
When multiple changes in the same file belong to different groups, use one of these approaches:

1. **Interactive staging** (recommended):

```bash
git add -p auth.py  # Review each hunk interactively
```

2. **Manual patch editing**:

```bash
git add -e auth.py  # Edit the patch directly
```

3. **Reset and re-stage**:

```bash
git reset HEAD auth.py
git add -p auth.py  # Stage only the hunks for current group
```

### Commit Execution

After staging changes for each group:

```bash
git commit -m "auth: validate token expiration correctly

This commit addresses the bug where expired tokens were not being
properly validated, leading to security issues."
```

## Scoped Commit Format

This project follows the [Scoped Commits](https://scopedcommits.com/) convention.
Use the format: `<scope>: <description>`

**Choosing the scope:**

- **Monorepo:** the scope MUST be a workspace package name OR a narrow global
  (`scripts`, `ci`, `docs`).
- **Single-package repo:** the scope MUST be a directory or an extensionless file
  path that locates the change in the tree, OR a narrow global (`scripts`, `ci`,
  `docs`). Always a subdir or a path down to a specific extensionless file; never
  a bare filename, a nested file without its folder, or a path with an extension.
  Good: `components/file-picker`, `utils/jwt`, `utils`, `auth`, `pages/foo`.
  Bad: `jwt.ts`, `file-picker`, `auth module`. No spaces.
- **Whole-tree changes:** use `*: <description>`.
- **Multiple scopes:** split the commit so each one fits a single scope.

Validate the chosen scope before committing:

```bash
./scripts/validate-scope.sh <scope>
```

**Description:**

- Brief, imperative mood description (e.g., "add", "fix", "update", not "added", "fixed")
- Lowercase, no period at the end
- Focus on what changed, not why (save "why" for commit body)

## Tips for Semantic Grouping

1. **Group by purpose, not by file** - Changes across multiple files can belong to one logical commit
2. **Keep commits focused** - Each commit should represent one logical change
3. **Consider the git log reader** - Each commit should tell a clear story
4. **Breaking changes** - Use `!` after the scope for breaking changes: `api!: change auth format`
5. **When in doubt, separate** - It's better to have too many small commits than too few large ones
