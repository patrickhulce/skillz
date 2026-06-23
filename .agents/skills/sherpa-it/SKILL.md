---
name: sherpa-it
description: Diagnose and fix CI failures by inspecting GitHub Actions logs from a pull request's status checks. Use when CI is failing, builds are broken, status checks are red, or the user asks to fix CI, debug a build failure, or check why the pipeline failed.
---

# Sherpa It (Monitor CI)

Diagnose and fix CI failures for the current branch's pull request, guiding it to green.

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

If no checks are failing, inform the user that all checks are passing.

If checks are still pending (`state == "PENDING"` / `IN_PROGRESS`), inform the user and ask whether to wait or stop.

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

### 7. Push the Fix

Commit and push the fix using a scope-style message (see the **commit-it** skill):

```bash
git add -A
git commit -m "<scope>: <description of what was fixed>"
git push
```

Choose `<scope>` per the project's scope rules — a workspace package name (monorepo) or a subsystem/global (`scripts`, `ci`, `docs`). Validate with `.agents/skills/commit-it/scripts/validate-scope.sh <scope>` if unsure.

### 8. Wait for CI

After pushing, poll the status checks until they complete:

```bash
# Wait for the new run to register, then poll
gh pr checks --watch
```

If `--watch` isn't desired, poll manually:

```bash
sleep 60
gh pr checks
```

Poll until checks complete. If still pending, keep waiting. If a check fails again, go back to step 3.

Report the final result to the user.

## Error Handling

| Scenario               | Action                                                |
| ---------------------- | ----------------------------------------------------- |
| No open PR for branch  | Inform user, suggest pushing and opening a PR first   |
| `gh` not authenticated | Run `gh auth status`, ask user to run `gh auth login` |
| Logs unavailable       | Show the run URL, ask user to check it in the browser |
| Fix doesn't resolve CI | Report the new failure, repeat diagnosis              |
