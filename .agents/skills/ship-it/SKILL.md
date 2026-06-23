---
name: ship-it
description: Orchestrate the full pull request creation workflow from uncommitted changes to an open GitHub PR ready-to-merge. Commits changes using scope-style commits, pushes the branch, generates a structured PR description, opens the PR on GitHub, and monitors until green. Use when the user says they're ready to create a PR, wants to open a pull request, or asks to ship/submit their changes.
---

# Create Pull Request

End-to-end workflow: scope-style commits → push → PR description → open PR on GitHub → monitor until green.

## Prerequisites

- All code changes are complete
- `gh` CLI is authenticated

## Workflow

### 1. Ensure Feature Branch

```bash
git branch --show-current
git status
```

If on `main`, create a feature branch with the following procedure:

1. Assess the high-level git diff to `main` with `git diff main...HEAD --word-diff | head -n 1000`
1. If the diff is empty, abort — nothing to do.
1. Determine a _short_ descriptive, snake_case branch name based on the diff. (e.g. "thread_pool_cleanup")
1. Create the branch with `git checkout -b "${USER}/${BRANCH_NAME}"`

### 2. Commit Changes (if any uncommitted changes exist)

Read and follow the **commit-it** skill at `.agents/skills/commit-it/SKILL.md`.

This will:

1. Analyze all changes
2. Create a safety checkpoint
3. Group changes into logical semantic commits
4. Print groupings and pause for review
5. Execute commits with scope-style commit messages

Skip this step if all changes are already committed.

### 3. Push Branch to Origin

```bash
git push -u origin HEAD
```

If the push fails due to diverged history, inform the user and stop — do NOT force push.

### 4. Generate PR Description

Read and follow the **describe-it** skill at `.agents/skills/describe-it/SKILL.md`.

When generating the description:

1. Analyze ALL commits on this branch vs `main`:
    ```bash
    git log --oneline main..HEAD
    git diff main...HEAD --stat
    ```
2. Review the actual diffs for each commit to understand the changes in detail
3. Write the description to `PR.md` following the template in the skill
4. The Evidence section should reference unit tests included in the PR, or commands the user can run to verify
5. DO NOT commit the PR.md file to the branch.

### 5. Open PR on GitHub

Read the generated `PR.md` and use it to create the PR.

**Title selection:**

- **Single commit:** Use the commit's one-liner as the title verbatim
- **Multiple commits:** Analyze the commits and synthesize a short thematic title (a few words, not a full sentence). Examples:
    - `Improve Error Handlers`
    - `Service DevX Improvements`
    - `Cache Layer Cleanup`
    - `Faster Startup Path`

Do NOT use generic titles like "various improvements" or "multiple fixes". The title should give a reader immediate context about the theme of the PR.

**Create the PR** with `gh`:

```bash
gh pr create --base main --title "$TITLE" --body-file PR.md
```

Parse the PR URL from the command output. After creation, display the PR URL to the user.

### 6. Cleanup

```bash
rm PR.md
```

Remove `PR.md` since it was a temporary artifact — the content now lives on the PR itself.

Do NOT commit the deletion of `PR.md`.

### 7. Monitor PR until Green

Read and follow the **sherpa-it** skill at `.agents/skills/sherpa-it/SKILL.md`.

This will:

1. Poll the PR's CI status until it has failed or succeeded
2. If the CI has succeeded, notify the user and exit
3. If the CI has failed, proceed in a loop of...
    1. ...analyzing the CI logs
    2. ...implementing a fix
    3. ...commit and push the fix
    4. ...poll the PR's CI status until it has failed or succeeded

## Error Handling

| Scenario                     | Action                                                                     |
| ---------------------------- | -------------------------------------------------------------------------- |
| `gh` not authenticated       | Run `gh auth status`, show error, ask user to run `gh auth login`          |
| Push rejected (diverged)     | Inform user, suggest `git pull --rebase origin <branch>`, NEVER force push |
| No changes to commit         | Skip to step 3 if there are unpushed commits, otherwise abort              |
| PR already exists for branch | Show the existing PR URL, ask user if they want to update it               |
