# Scoped Commits Workflow Example

This document shows a concrete example of analyzing mixed changes and grouping them into semantic commits.

## Example Scenario

### Initial State

Working directory has these mixed changes:

- `src/lib/auth.py`: Bug fix for token expiration (lines 45-52)
- `src/lib/auth.py`: Added logging for auth failures (lines 103-107)
- `src/lib/database.py`: Fixed connection pooling bug (lines 28-35)
- `src/lib/database.py`: Added retry logic (lines 89-102)
- `src/api/preferences.py`: New endpoint for user preferences (lines 201-245)
- `src/lib/errors.py`: Refactored error handling (lines 12-67)
- `src/lib/auth.py`: Added helper function for auth (lines 102-115)
- `src/components/LoginModal.tsx`: New login modal

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

- `src/lib/auth.py` lines 45-52 (token expiration fix) and 102-115 (auth helper)
- Purpose: Fix bug where tokens weren't being validated correctly
- Commit message: `lib/auth: validate token expiration correctly`

**Group 2: Database connection improvements**

- `src/lib/database.py` lines 28-35 (connection pooling fix)
- `src/lib/database.py` lines 89-102 (retry logic)
- Purpose: Improve database reliability and connection handling
- Commit message: `lib/database: improve connection pooling and add retry logic`

**Group 3: Enhanced observability**

- `src/lib/auth.py` lines 103-107 (logging for auth failures)
- Purpose: Better debugging for authentication issues
- Commit message: `lib/auth: add logging for failures`

**Group 4: User preferences endpoint**

- `src/api/preferences.py` lines 201-245 (new endpoint)
- Purpose: New feature for user preferences
- Commit message: `api/preferences: add user preferences endpoint`

**Group 5: Error handling refactor**

- `src/lib/errors.py` lines 12-67 (error handling refactor)
- Purpose: Improve error handling consistency
- Commit message: `lib/errors: standardize error handling patterns`

**Group 6: Login modal**

- `src/components/LoginModal.tsx` (entire file)
- Purpose: Add a login modal
- Commit message: `components/LoginModal: add login modal`

### Staging Strategy

For each group, the staging approach depends on whether entire files or partial files need to be staged:

**Entire file changes:**

```bash
git add src/api/preferences.py src/components/LoginModal.tsx
```

**Partial file changes:**
When multiple changes in the same file belong to different groups, use one of these approaches:

1. **Interactive staging** (recommended):

```bash
git add -p src/lib/auth.py  # Review each hunk interactively
```

2. **Manual patch editing**:

```bash
git add -e src/lib/auth.py  # Edit the patch directly
```

3. **Reset and re-stage**:

```bash
git reset HEAD src/lib/auth.py
git add -p src/lib/auth.py  # Stage only the hunks for current group
```

### Commit Execution

Validate the scope against this group's files, then commit:

```bash
python3 ./scripts/validate-scope.py "lib/auth: validate token expiration correctly" -- src/lib/auth.py
git commit -m "lib/auth: validate token expiration correctly

This commit addresses the bug where expired tokens were not being
properly validated, leading to security issues."
```

## Scoped Commit Format

Use the format: `<scope>: <description>`

**Choosing the scope:**

- **Always valid:** `skills/<name>`, `tests[/<scope>]`, `docs[/<scope>]`, `infra[/<scope>]`
- **Monorepo:** `packages/<name>[/<scope>]` or `apps/<name>[/<scope>]` when that directory exists
- **Code surfaces:** `components/<name>`, `routes/<name>`, `api/<name>`, `lib/<name>` where `<name>` is a folder or filename in this commit's files
- **Multi-surface:** `feature/<name>` when README.md lists that feature as `- **name** - …` (or `: ` / `—`). Never `treewide`.
- **Repo extras:** `<!-- skillz-commit-scopes: foo/<scope>,bar/<*>,baz -->` in README.md

Validate the chosen scope before committing:

```bash
python3 ./scripts/validate-scope.py <scope> -- path/to/file1 path/to/file2
```

**Description:**

- Brief, imperative mood description (e.g., "add", "fix", "update", not "added", "fixed")
- Lowercase, no period at the end
- Focus on what changed, not why (save "why" for commit body)

## Tips for Semantic Grouping

1. **Group by purpose, not by file** - Changes across multiple files can belong to one logical commit
2. **Keep commits focused** - Each commit should represent one logical change
3. **Consider the git log reader** - Each commit should tell a clear story
4. **Breaking changes** - Use `!` after the scope for breaking changes: `api/preferences!: change auth format`
5. **When in doubt, separate** - It's better to have too many small commits than too few large ones
6. **Never use `treewide`** - Split, or use `feature/<name>` when README already documents the feature
