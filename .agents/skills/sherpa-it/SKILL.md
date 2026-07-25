---
name: sherpa-it
description: Guide a pull request to a mergeable state — diagnose and fix CI failures from GitHub Actions logs AND address unresolved review comments from AI and human reviewers, looping until checks pass and threads are resolved. Use when CI is failing, builds are broken, status checks are red, or the user asks to fix CI, debug a build failure, address reviewer feedback, monitor a PR, or babysit a PR until it's ready to merge.
---

# Sherpa It (Monitor PR to Mergeable)

Drive the current branch's pull request to a **mergeable** state. The PR is mergeable when both are true: every status check is green, and no unresolved actionable review threads remain.

Each pass does two things, then batches both into one push:

1. **Fix CI failures** — diagnose the failing GitHub Actions job and fix the cause (steps 2–6).
2. **Address review feedback** — work through unresolved threads from AI and human reviewers (step 7).

Green CI is not the finish line on its own. Reviewers post asynchronously and re-review each push, so keep looping (step 9) until both conditions hold. For unattended monitoring, run this skill on an interval so it keeps re-checking as reviewers catch up.

## Workflow

### 1. Identify the PR

Find the open PR for the current branch:

```bash
BRANCH=$(git branch --show-current)
gh pr view --json number,url,state --jq '{number, url, state}'
```

If no open PR exists, inform the user and stop.

### 2. Get Failed Status Checks

List the checks for the PR:

```bash
gh pr checks
```

Or, for machine-readable detail:

```bash
gh pr checks --json name,state,link --jq '.[] | select(.state == "FAILURE") | {name, link}'
```

If no checks are failing, skip ahead to step 7 — green CI is not a terminal state, there may still be reviewer feedback to address.

If checks are still pending (`state == "PENDING"` / `IN_PROGRESS`), note it and continue to step 7 anyway; you can address review comments while CI runs, then re-poll in step 9.

### 3. Fetch GitHub Actions Logs

For each failed check, fetch the failing job's logs. Find the run for the PR's head commit and dump the failed steps:

```bash
# List recent runs for this branch
gh run list --branch "$BRANCH" --limit 5

# View the failing run and print only the failed steps' logs
gh run view <run-id> --log-failed
```

For the full log of a specific job (when `--log-failed` isn't enough context):

```bash
gh run view <run-id> --log
```

The output can be large. Pipe through `tail` or `grep` to find the error:

```bash
gh run view <run-id> --log-failed 2>/dev/null | tail -200
gh run view <run-id> --log-failed 2>/dev/null | grep -n -E "FAILED|ERROR|Error|error:|failed|AssertionError|FAILURE" | tail -20
```

Then read the surrounding context of the relevant line numbers.

### 4. Diagnose and Fix

Analyze the error output to determine the root cause. Map the failure to a category and the corresponding verification root (see step 5 / the **build-scripts** skill):

| Category      | Signs                                          | Verification root | Typical fix                                  |
| ------------- | ---------------------------------------------- | ----------------- | -------------------------------------------- |
| Test failure  | `FAILED`, assertion errors, failing test cases | `make test`       | Fix the failing test or the code it tests    |
| Lint/format   | linter or formatter errors                     | `make lint`       | Apply the formatter / fix the lint violation |
| Type errors   | type-checker mismatches                        | `make typecheck`  | Fix type annotations                         |
| Import/deps   | missing module / unresolved dependency         | `make build`      | Fix imports or update/install dependencies   |
| Build errors  | compile / package failures                     | `make build`      | Fix package config or syntax errors          |

The exact tool behind each root varies by language and repo — let the repo's own scripts decide it rather than hardcoding `pytest`/`ruff`/etc.

### 5. Discover the Repo's Verification Commands

Don't guess command names. Discover what this repo actually runs:

1. Read `.github/workflows/*.yml` — the source of truth for what CI runs. Reproduce the failing job's `run:` steps locally so your local run matches CI exactly.

    ```bash
    ls .github/workflows/
    ```

2. For finding and scoping the right test/lint/typecheck commands, read and follow the **test-it** skill at `.agents/skills/test-it/SKILL.md`. It discovers the repo's commands in priority order (`.github/workflows`, `Makefile`, `tasks.py`, `tox.ini`, `package.json`, `build.gradle`, ...) and scopes the run to the diff.

3. Most repos following the **build-scripts** convention (`.agents/skills/build-scripts/SKILL.md`) expose a top-level `Makefile` with `make ci`, `make test`, `make lint`, `make typecheck`, and `make build` as the universal entry points — prefer these when present.

### 6. Verify Locally Before Pushing

ALWAYS VERIFY LOCALLY BEFORE PUSHING. Run what CI runs.

- Full gate (mirrors CI):

    ```bash
    make ci          # or the exact commands from .github/workflows/*.yml
    ```

- For tighter feedback during iteration, run the narrower root matching the failure (see step 4), and use **test-it** to scope a targeted run to just the changed files:

    ```bash
    make test        # or make lint / make typecheck
    ```

If the repo has no `Makefile`, fall back to the literal commands surfaced by the **test-it** skill.

### 7. Address Review Feedback

Before pushing, work through the PR's unresolved review threads — AI reviewers and humans alike — so CI fixes and review fixes batch into a single push.

Read and follow the **refine-it** skill at `.agents/skills/refine-it/SKILL.md` in PR mode. It fetches unresolved threads, verifies each claim against the current code (do NOT take the reviewer at their word), applies its fix-size policy (P0 always, P1 when the fix is roughly 100 lines or less, P2 only when under about 10 lines and about this change), replies in-thread, and resolves settled threads. It stops short of committing so its edits join the CI fix in step 8.

Honor the items it surfaces for approval — `invalid`, `partial`, and `needs-user-input` need your decision before pushing back on a reviewer. Never silently dismiss a reviewer.

AI reviewers (Bugbot, Copilot, CodeRabbit) review asynchronously and take several minutes after each push. On the first pass their review often hasn't posted yet — that's expected, a later loop iteration picks it up.

### 8. Push the Fix

Commit the CI fixes and review fixes together using a scope-style message (see the **commit-it** skill), or as a few logical commits if they're unrelated:

```bash
git add -A
git commit -m "<scope>: <description of what was fixed>"
git push
```

Choose `<scope>` per the project's scope rules — a workspace package name (monorepo) or a subsystem/global (`scripts`, `ci`, `docs`). Validate with `.agents/skills/commit-it/scripts/validate-scope.sh <scope>` if unsure.

Skip the commit only if this pass changed nothing (no CI fix needed, no valid review findings) — in that case go straight to step 9 to keep monitoring.

### 9. Loop Until Green and Resolved

After pushing, re-assess both conditions. Wait for the new run to register, then watch it:

```bash
gh pr checks --watch
```

If `--watch` isn't desired, poll manually:

```bash
sleep 60
gh pr checks
```

Then branch on what you find:

- **Checks pending** — keep waiting and re-poll. When running on an interval, let the interval do the waiting instead of blocking.
- **A check failed again** — go back to step 3.
- **Checks green but reviewer feedback is new or unreviewed** — go back to step 7.
- **Checks green and no unresolved actionable threads** — done. Report the final state.

Stop and hand back to the user if you hit any of these:

- A review thread needing a human decision
- A merge conflict with the base branch
- The same check failing three passes in a row

Report the final state either way: CI status, review threads addressed, and anything still blocked on a human.

## Error Handling

| Scenario                         | Action                                                         |
| -------------------------------- | -------------------------------------------------------------- |
| No open PR for branch            | Inform user, suggest pushing and opening a PR first            |
| `gh` not authenticated           | Run `gh auth status`, ask user to run `gh auth login`          |
| Logs unavailable                 | Show the run URL, ask user to check it in the browser          |
| Fix doesn't resolve CI           | Report the new failure, repeat diagnosis                       |
| GraphQL 401/403 fetching threads | Run `gh auth status`; the token needs `repo` scope for threads |
| Merge conflict with base         | Report it and hand back — do not resolve conflicts blindly     |
