---
name: commit-it
description: Organize mixed-purpose changes into logical, separate commits using conventional commits with a mandatory scope. Scope is the most important part of the message. Use when the user has multiple unrelated changes (bug fixes, features, refactoring) mixed together and wants to split them into clean, semantic commits. This skill provides a safe workflow with checkpoint backups before reorganizing changes.
---

# Conventional Commits

Safely organize mixed-purpose changes into logical, focused commits. Every message is `<type>(<scope>): <description>`. The scope is mandatory and is the most important part of the header: it names the surface the commit touches. The type only says what kind of change it is.

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
- Have a conventional commit message whose scope names the surface
- Include all related changes, even across multiple files

**See references/workflow-example.md for a detailed example.**

**Important considerations:**

- Group by PURPOSE, not by file - related changes across files should be together
- Each group should be independently deployable if possible
- Consider the git log reader - each commit should tell a clear story
- Separate breaking changes and call them out with `!` after the closing parenthesis: `type(scope)!`

### 4. Print Grouping Details

Before executing, print the full details of each group so the user can see what will be committed. Use this format:

```markdown
## Commit Groups

### Group 1: `fix(scope): brief description`

**Files:**

- `path/to/file1.py` (lines X-Y, entire file, or specific change description)
- `path/to/file2.py` (lines A-B)
  **Purpose:** [Brief explanation of what this group accomplishes]

---

### Group 2: `feat(scope): brief description`

...
```

### 5. Execute Commits

Execute each commit in order:

For each group:

**5a. Validate the scope**

Before staging, confirm the header is valid for this repo. The script requires a scope and checks that scope against the rules below. Pass the files in this group so `components/` / `routes/` / `api/` / `lib/` (and extra `<scope>` rules) can match against them:

```bash
python3 ./scripts/validate-scope.py "fix(lib/auth)" -- path/to/file1 path/to/file2
```

This enforces the project's scope rules (see "Conventional Commit Reference" below). Fix the scope if it is rejected. A missing scope is a failure. Never use `treewide` or `feature/`.

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

Use the approved conventional commit message. The scope in parentheses is mandatory:

```bash
git commit -m "fix(lib/auth): validate token expiration correctly

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

## Conventional Commit Reference

The scope is mandatory and is the most important part of the message. Readers scan the scope to see what the commit touches. The type only says what kind of change it is. A header without parentheses is invalid.

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

`feat: add login` is invalid. `treewide` is banned. `feature/<name>` is not a scope. If a change spans surfaces, split the commit.

**Type** is a lowercase word (`feat`, `fix`, `refactor`, `perf`, `docs`, `tests`, `infra`, `chore`, and other `[a-z][a-z0-9]*` tokens). It is not a closed list. These types change which scopes are valid:

- `docs` — `*` when the docs are not one surface, otherwise a member or code-surface scope
- `tests` — the surface under test (a member or code surface)
- `infra` — a tool, `skills`, or `skills/<name>`

**Infra scopes:**

- `infra(<tool>)` — one path segment, such as `uv`, `eslint`, or `ci`
- `infra(skills)` — adding a skill. This stays valid when the skill directory does not exist yet
- `infra(skills/<name>)` — a change to one existing skill. `<name>` must be a single skill directory under `.agents/skills/`, `.claude/skills/`, `.cursor/skills/`, or `skills/`

`feat(skills)` and `feat(skills/<name>)` are invalid. Skills are infra-only.

**Package and app members** (drop the `packages/` or `apps/` prefix):

- `<name>` or `<name>/<scope>`, where `<name>` is a child directory of `packages/` or `apps/`
- A glob is allowed in the name and must match at least one directory (`*-mycool-library`, not `packages/*-mycool-library`)
- A nested suffix such as `v8r.dev/frontend` is kept. It is not required to be its own directory
- A name that exists in either `packages/` or `apps/` is enough

**Code surfaces** (not tied to a top-level directory). `<name>` must equal a folder or filename among the files in this commit:

- `components/<name>`
- `routes/<name>`
- `api/<name>`
- `lib/<name>`

`frontend/` is not a valid prefix — use `components/` or `routes/`. These prefixes may appear anywhere in the tree (`src/ui/components/LoginModal.tsx` validates `components/LoginModal`).

**Repo extras:** a consuming repo may add prefixes via an HTML comment in `README.md`:

```html
<!-- skillz-commit-scopes: foo/<scope>,bar/<*>,baz -->
```

- `foo/<scope>` — suffix required; must match a changed folder or filename
- `bar/<*>` — suffix required; any non-empty path token
- `baz` — exact bare token only

Extra scopes are additive. `treewide` and `feature/` stay banned even if listed.

**Examples:**

- `infra(skills): add the polyglot-scaffold skill`
- `infra(skills/polyglot-scaffold): add initial implementation`
- `tests(node-mycool-library): fix flaky failure in s3 tests`
- `docs(*): update guidance for v1->v2 migrations`
- `infra(uv): bump lockfile`
- `infra(eslint): ignore semicolons rule`
- `infra(ci): add github actions workflows`
- `feat(python-mycool-library): add __iter__ sugar to upload`
- `feat(*-mycool-library): add the decode function`
- `feat(v8r.dev/frontend): add login modal`
- `fix(components/form): fix regex DDoS vulnerability`
- `feat(components/LoginModal): add login modal`
- `feat(routes/settings): add billing section`
- `feat(api/preferences): add user preferences endpoint`
- `fix(lib/auth): validate token expiration correctly`
- `infra(skills/commit-it): add scope validator and README examples`

Validate the header before committing, passing this group's files:

```bash
python3 ./scripts/validate-scope.py "fix(lib/auth)" -- path/to/file1 path/to/file2
```

**Breaking changes:** Add `!` after the closing parenthesis: `refactor(api/preferences)!: change response format`

**Description rules:**

- Imperative mood (e.g., "add", "fix", "update", not "added", "fixes")
- Lowercase
- No period at end
- The description after the colon is brief (50 characters or less). The type and scope do not count toward that limit

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

**"The scope was rejected by validate-scope.py"**

- The header must be `<type>(<scope>): <description>`. A missing scope is invalid
- Skill work is `infra(skills)` when adding a skill, or `infra(skills/<name>)` when that skill already exists
- Package and app scopes are the member name only: `feat(python-mycool-library)`, `feat(v8r.dev/frontend)`. Do not write `packages/` or `apps/` in the scope
- Code surfaces are `components/`, `routes/`, `api/`, and `lib/`. `<name>` must be a folder or filename in this group's files — pass those files to the validator
- `docs(*)` is the only valid `*` scope. `tests` uses the surface under test
- Do not use `treewide`, `feature/`, `scripts`, `frontend`, or a bare `ci` scope. `ci` belongs in `infra(ci)`
- If the change spans surfaces, split the commit
- Consuming repos can add prefixes with `<!-- skillz-commit-scopes: foo/<scope>,bar/<*>,baz -->` in README.md
