---
name: yeet-it
description: Reckless, no-safety-net correlary to ship-it. Commits whatever is uncommitted directly on main using scope-style commits, rebases onto the latest origin/main if it moved (resolving conflicts), and pushes straight to origin. Skips checkpoints, review passes, PRs, and confirmation pauses. Never force pushes or rewrites already-pushed remote history. Use when the user says "yeet it", "just push to main", "skip the PR", or wants uncommitted changes committed and pushed to main immediately without review.
---

# Yeet Code Straight to Main

The reckless correlary to **ship-it**: commit whatever is uncommitted directly on `main` with scope-style commits, rebase on top of `origin/main` if it has moved, and push. No feature branch, no PR, no checkpoint, no review pass, no pause for confirmation.

## When NOT to use

- The user hasn't explicitly asked to skip review/PR — default to **ship-it** (`.agents/skills/ship-it/SKILL.md`)
- Branch protection blocks direct pushes to `main` — this will fail at the push step; don't work around it by force pushing

## Prerequisites

- Currently on `main` (or the repo's default branch)
- Local git identity configured

## Workflow

### 1. Confirm on main

```bash
git branch --show-current
```

If not on `main`, stop and tell the user — yeet-it only operates directly on `main`, it does not create or switch branches.

### 2. Commit uncommitted changes (scope-style, no checkpoint)

If `git status --porcelain` shows any changes:

1. Review `git diff` and `git diff --cached` to understand what changed.
2. Group changes into logical, single-purpose commits using the scope rules and message format in **commit-it**'s "Scoped Commit Reference" section (`.agents/skills/commit-it/SKILL.md`) — but skip the rest of that skill's process.
3. Stage and commit each group directly (`git add` / `git add -p` for partial files, then `git commit -m "<scope>: <description>"`).
4. Do **not** run the checkpoint script, print a grouping table, or pause for review — commit immediately as you go.

Skip this step entirely if the working tree is already clean.

### 3. Sync with origin/main

```bash
git fetch origin main
git rev-list --left-right --count main...origin/main
```

The output is `<ahead> <behind>`.

- **`<behind>` is 0**: origin hasn't moved, proceed to push.
- **`<behind>` is nonzero**: origin moved ahead, rebase local commits on top of it:

  ```bash
  git rebase origin/main
  ```

  If conflicts occur, resolve them in place (edit the conflicting files preserving the intent of both sides, `git add <file>`, `git rebase --continue`). Never `git rebase --abort` silently — if a conflict can't be resolved confidently, stop mid-rebase and ask the user.

### 4. Push to origin

```bash
git push origin HEAD:main
```

If the push is rejected because origin moved again (race condition), repeat step 3 (fetch + rebase) and retry. **Never** use `--force` / `--force-with-lease` or otherwise rewrite history already pushed to `origin/main` — only ever rebase local, unpushed commits on top of the latest `origin/main`.

## Error Handling

| Scenario                                                        | Action                                                            |
| ----------------------------------------------------------------| ------------------------------------------------------------------|
| Not on `main`                                                    | Stop, tell the user yeet-it only runs on `main`                   |
| Working tree clean and `main` == `origin/main`                   | Nothing to do, report and stop                                    |
| Push rejected for a reason other than a stale ref (e.g. branch protection, CI required) | Stop, surface the error, do NOT force push        |
| Rebase conflict that can't be resolved confidently               | Stop mid-rebase, surface the conflicting files, ask the user      |

## Relationship to ship-it

| | ship-it | yeet-it |
| --- | --- | --- |
| Branch | feature branch | `main` directly |
| Commit safety | checkpoint + printed grouping + pause | none, commits immediately |
| Review pass | review-it + refine-it | skipped |
| Diverged remote | rebase not needed (fresh branch) | rebase local commits onto `origin/main` |
| PR | opens PR, monitors CI via sherpa-it | none |
| Push target | feature branch | `main` |
| Force push | never | never |
