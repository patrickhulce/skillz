---
name: test-it
description: Identify the correct test commands for the current repository, scope the run to what actually changed, and hand off to dogfood-it when docs or examples were touched. Use when the user asks to run tests, verify the diff, smoke-check changes before pushing, or says things like "test it", "run the tests", or "make sure this still works".
---

# Test It

Run the _right_ tests for this repo and this diff — not a guessed `pytest` or `npm test`. Mirror what CI runs, narrow the scope to what changed, and escalate to documentation testing when examples were edited.

## Workflow

### 1. Discover the repo's test commands

Look at these sources **in order** and stop at the first that gives you a concrete invocation. The earlier sources are more authoritative because they reflect what CI actually runs.

| Priority | Source                                  | What to do                                                            |
| -------- | --------------------------------------- | --------------------------------------------------------------------- |
| 1        | `.github/workflows/*.yml`               | Read them. These are the literal CI jobs — mirror their steps locally.|
| 2        | `Makefile`                              | Look for `test`, `check`, `ci`, `verify` targets.                     |
| 3        | `tasks.py` (invoke / pyinvoke)          | Look for `@task`-decorated functions named `test`, `check`, `ci`.     |
| 4        | `tox.ini` / `pyproject.toml [tool.tox]` | Run `tox -l` to list envs.                                            |
| 5        | `pyproject.toml [tool.pytest]`          | Plain `pytest` is the fallback for Python repos with no orchestrator. |
| 6        | `package.json` `scripts.test`           | Use `npm test` / `yarn test` / `pnpm test` per the lockfile.          |
| 7        | `build.gradle` / `build.gradle.kts`     | `./gradlew test` (or `./gradlew check` for full verification).        |

```bash
ls .github/workflows/ Makefile tasks.py tox.ini pyproject.toml package.json build.gradle build.gradle.kts 2>/dev/null
```

For each existing file, read it and extract the literal commands. Do **not** invent `make test` if no `test` target exists. Do **not** run `pytest` directly when `tox.ini` defines envs that set up dependencies.

#### Mirroring GitHub Actions

- `.github/workflows/*.yml` is the source of truth for what runs in CI. Read each job's `steps:` and reproduce the `run:` commands locally in the same order.
- The test step is usually the `run:` line that invokes `pytest`, `tox`, `npm test`, `./gradlew test`, etc. Match its flags and environment.
- If a workflow uses a matrix (e.g. multiple Python versions), pick the version closest to your local interpreter for the inner loop, and note that CI covers the rest.

### 2. Read the diff to scope the run

A full CI run is the safety net, not the inner loop. Start by understanding **what changed** so you can run a targeted subset first.

```bash
git fetch origin main --quiet 2>/dev/null || true
BASE=$(git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD main 2>/dev/null || echo HEAD~1)
git diff --name-status "$BASE"...HEAD
git diff --stat "$BASE"...HEAD
```

Bucket every changed path:

| Bucket                   | Examples                                                              | Test implication                                                 |
| ------------------------ | --------------------------------------------------------------------- | ---------------------------------------------------------------- |
| **Source code**          | `src/**/*.py`, `lib/**/*.ts`, `app/**/*.kt`                           | Find tests that import or exercise the changed module.           |
| **Tests**                | `tests/**`, `*_test.py`, `*.spec.ts`                                  | Run the changed test files directly.                             |
| **Build / dep config**   | `pyproject.toml`, `requirements*.txt`, `package.json`, `build.gradle` | Run the full suite — deps may have shifted under the whole repo. |
| **Lint / format config** | `ruff.toml`, `.eslintrc`, `.prettierrc`                               | Run the lint/style env (e.g. `tox -e style`).                    |
| **CI config**            | `.github/workflows/**`                                                | Run whatever the new CI workflow runs.                           |
| **Docs & examples**      | `*.md`, `docs/**`, `examples/**`, README snippets                     | Escalate to the **dogfood-it** skill (see step 4).              |

For source changes, find the matching tests:

```bash
# Python: tests that import the changed module
git diff --name-only "$BASE"...HEAD -- 'src/**/*.py' | while read f; do
  mod=$(echo "$f" | sed 's#^src/##; s#\.py$##; s#/#.#g; s#\.__init__##')
  rg -l "$mod" tests/ 2>/dev/null
done | sort -u
```

Adapt the pattern for the language at hand (`*.ts`/`*.spec.ts`, `*.kt`/`*Test.kt`, etc.).

### 3. Run tests, narrowest first

Iterate from cheap → expensive:

1. **Targeted tests first.** Run only the test files that exercise changed code:

    ```bash
    # Python via tox
    tox -e py311 -- tests/path/to/test_changed.py -vv

    # Python directly
    pytest tests/path/to/test_changed.py -vv

    # Make / invoke
    make test ARGS="tests/path/to/test_changed.py"
    invoke test --pytest-args="tests/path/to/test_changed.py"
    ```

2. **Lint / format / typecheck** if config or source changed:

    ```bash
    tox -e style       # or whatever env tox.ini defines
    ```

3. **Full suite as the final gate**, mirroring CI:

    ```bash
    tox                # runs the env list from tox.ini
    # or run the exact commands from .github/workflows/*.yml
    ```

If a step fails, surface the failure to the user and stop — do not paper over it by skipping tests or weakening assertions.

### 4. Hand off to dogfood-it when docs or examples changed

If step 2 found changes under `docs/`, `examples/`, `README.md`, or any `*.md` that contains executable instructions or code blocks the reader is expected to run, **read and follow** the **dogfood-it** skill at `.agents/skills/dogfood-it/SKILL.md` against the changed files.

This applies when:

- A README's "Quickstart" / "Installation" section was edited.
- Example scripts under `examples/` were added or modified.
- A tutorial under `docs/` had its commands, code blocks, or links changed.
- A new `.md` walkthrough was introduced.

This does **not** apply for:

- API reference docs auto-generated from docstrings.
- Pure prose changes (typo fixes, rewording) with no executable instructions.
- Changelog / release-notes edits.

Pass the changed doc paths to the dogfood-it skill so it scopes its run to those files rather than the whole `docs/` tree.

### 5. Report results

Summarize for the user:

- Which command(s) you ran and where they came from (`.github/workflows/ci.yml`, `Makefile:test`, `tox.ini [testenv]`, etc.).
- What scope you tested (targeted files vs. full suite).
- Pass / fail counts and any failure details.
- Whether the documentation handoff ran, and a pointer to `FEEDBACK.md` if it produced one.

## Guidelines

- **Mirror CI, don't reinvent it.** If `.github/workflows/ci.yml` runs `tox`, your local run should too. Diverging from CI is how "works on my machine" happens.
- **Don't guess command names.** If no `test` target exists in the `Makefile`, say so — don't fabricate one.
- **Targeted before full.** A 2-second targeted run beats a 10-minute full run for the inner loop. Use the full suite as the final gate, not the only gate.
- **Read tool output, don't just exit-code-check.** A passing exit code with `0 tests collected` is a failure mode worth flagging.
- **Respect skip markers.** If tests are skipped due to missing env vars or services, surface that to the user — don't pretend they passed.
- **Never weaken a test to make it pass.** If a test fails, the fix goes in the source, not in the assertion.
