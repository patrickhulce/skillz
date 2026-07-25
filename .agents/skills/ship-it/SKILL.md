---
name: ship-it
description: Orchestrate the full pull request creation workflow from uncommitted changes to an open GitHub PR ready-to-merge. Commits changes using scope-style commits, runs one pre-ship review and refine pass, pushes the branch, generates a structured PR description, opens the PR on GitHub, and monitors until CI is green and reviewer feedback is resolved. Use when the user says they're ready to create a PR, wants to open a pull request, or asks to ship/submit their changes.
---

# Create Pull Request

End-to-end workflow: scope-style commits → review and refine → push → PR description → open PR on GitHub → monitor to mergeable.

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

### 3. Pre-Ship Review Pass

Catch what a reviewer would catch before anyone else sees the PR. Run this **exactly once** — it is not a loop.

1. Read and follow the **review-it** skill at `.agents/skills/review-it/SKILL.md` to audit the committed diff against `main`. It produces a read-only report with every finding tiered P0, P1, or P2.
2. If there are findings, read and follow the **refine-it** skill at `.agents/skills/refine-it/SKILL.md` in local mode. It verifies each finding against the code and applies its fix-size policy: P0 always, P1 when the fix is roughly 100 lines or less, P2 only when the fix is under about 10 lines and concerns this change.
3. If **refine-it** changed anything, commit the fixes via **commit-it** — usually a single `<scope>: address pre-ship review findings` commit.

Stop and surface it to the user before pushing if a P0 finding is left unaddressed because it needs a human decision. Everything else — deferred P1s and P2s with their rationale — is fine to ship; the rationale belongs in the PR description's tradeoffs.

### 4. Push Branch to Origin

```bash
git push -u origin HEAD
```

If the push fails due to diverged history, inform the user and stop — do NOT force push.

### 5. Generate PR Description

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

### 6. Open PR on GitHub

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

### 7. Cleanup

```bash
rm PR.md
```

Remove `PR.md` since it was a temporary artifact — the content now lives on the PR itself.

Do NOT commit the deletion of `PR.md`.

### 8. Monitor PR until Mergeable

Read and follow the **sherpa-it** skill at `.agents/skills/sherpa-it/SKILL.md`.

This will loop until the PR is mergeable — every check green AND no unresolved actionable review threads:

1. Poll the PR's checks
2. If a check has failed, analyze the CI logs and fix the cause
3. Address any unresolved reviewer feedback via **refine-it**, replying and resolving threads
4. Commit and push the CI fixes and review fixes together
5. Re-poll and repeat

AI reviewers post asynchronously, so the first pass usually has no comments yet. Suggest running **sherpa-it** on an interval if the user wants it monitored unattended.

## Error Handling

| Scenario                     | Action                                                                     |
| ---------------------------- | -------------------------------------------------------------------------- |
| `gh` not authenticated       | Run `gh auth status`, show error, ask user to run `gh auth login`          |
| Push rejected (diverged)     | Inform user, suggest `git pull --rebase origin <branch>`, NEVER force push |
| No changes to commit         | Skip to the review pass (step 3) if there are unpushed commits, else abort |
| Unaddressed P0 after refine  | Stop before pushing, surface the finding, let the user decide              |
| PR already exists for branch | Show the existing PR URL, ask user if they want to update it               |
