---
name: review-it
description: Inspect the diff against main to surface bugs, inconsistencies, incorrect explanations, lost explanatory comments, and light API hygiene issues before shipping, classifying every finding as P0, P1, or P2. Use when the user says "review my diff before I ship", "look over my changes", "check this PR", or asks for a pre-flight code review. Hands off to refine-it to actually apply fixes.
---

# Code Review

Audit the changes on the current branch before shipping. Catch the kind of bugs and API mistakes a careful human reviewer would catch on a PR.

This skill is **read-only**. Do not commit, push, run formatters, or auto-fix anything. Fixing findings is **refine-it**'s job (`.agents/skills/refine-it/SKILL.md`), which consumes the report this skill produces.

## Workflow

### 1. Establish the diff scope

```bash
git fetch origin main --quiet
BASE=$(git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD main)
git log --oneline "$BASE"..HEAD
git diff --stat "$BASE"...HEAD
```

### 2. Bucket every changed file

```bash
git diff --name-status "$BASE"...HEAD
```

Categorize each path:

- **Public surface** — non-underscore-prefixed modules under the top-level package (e.g. `src/<pkg>/`) and anything re-exported from `__init__.py`
- **Internal** — `_*.py`, `tests/`, `scripts/`, `vendor/`, `_vendor/`
- **Docs/config** — `*.md`, `pyproject.toml`, `Makefile`, `tox.ini`, `ruff.toml`, `pyrightconfig.json`

### 3. Read the actual diffs

For each changed file, read the full diff (not just the summary):

```bash
git diff "$BASE"...HEAD -- <path>
```

For large or context-dependent changes, also read the new file contents around the hunks — the diff alone often hides necessary context (callers, surrounding logic, related symbols).

### 4. Run the review checklist

Walk every changed file against this checklist. Note each finding with its `path:line` and category as you go; you'll assign severity tiers in the next step.

#### Correctness

- Off-by-one, wrong operators, swapped arguments, inverted conditions
- Mutable default arguments, accidental aliasing, missing `await`
- Exception handling that silently swallows errors or catches too broadly
- Resource leaks (open files, sessions, GPU memory) without `with`/`close`
- Incorrect or missing `None` / empty-collection handling

#### Consistency

- Naming drift: the same concept named differently across files in the diff
- Mismatch between a docstring/comment and the actual implementation
- Mismatch between a function signature and its callers in the diff
- Type hints that don't match runtime behavior or values returned
- Inconsistent units, casing, or coordinate/colorspace conventions

#### Documentation accuracy

- Docstrings, `docs/*.md`, FAQs, and `README` snippets that contradict the code change
- Code examples in docs/markdown that won't run as written
- `CLAUDE.md` / `AGENTS.md` guidance that's now stale

#### Lost explanatory comments

Scan every removed line in the diff for comments and docstrings (`#`, `"""..."""`, `//`, `/* */`) that explained **why** something was done. A comment is **critical** if it conveys context that isn't recoverable from the code alone:

- Rationale for a non-obvious choice ("we use X here because Y rejects Z")
- Warnings about footguns, edge cases, or upstream bugs ("do not reorder — see #1234")
- Performance tradeoffs ("avoiding `.copy()` saves ~40ms on 4K frames")
- Compatibility notes ("required for PyAV < 12.0", "matches FFmpeg's quirky behavior")
- Cross-references to issues, RFCs, vendor docs, or design decisions
- Invariants and preconditions ("caller must hold `_lock`", "input must be normalized")
- `TODO`/`FIXME`/`XXX`/`HACK` markers that still describe live debt

For each such removed comment, check whether the new code:

1. **Preserves it** verbatim or in spirit elsewhere in the diff → fine, no flag
2. **Makes the comment obsolete** because the underlying issue is gone → fine, no flag (but verify the claim)
3. **Drops it silently** while the rationale still applies → flag as `[LOST-COMMENT]`

Ignore narration-style comments that just restate the code (`# increment counter`, `# return result`). Only flag comments that carry irreplaceable intent.

#### API quality

- Missing or wrong type annotations on new/changed public functions
- Public functions accepting `dict[str, Any]` instead of a typed schema
- Required params added after optional ones
- New public symbols with vague names (`helper`, `process`, `do_thing`)
- New `# type: ignore` without a specific error code

### 5. Assign a severity tier to every finding

Every finding gets exactly one tier. The tier is what drives whether **refine-it** fixes it, so it matters more than the category:

- **P0** — a critical bug that breaks essential functionality for a frequent or obvious use case.
- **P1** — a bug or usage problem that might create errors in edge cases or rarer use cases.
- **P2** — style, pattern, optimization, or a nit.

Default mappings, so the tiering is repeatable across runs:

| Finding                                                            | Tier |
| ------------------------------------------------------------------ | ---- |
| `[BUG]` on the mainline path a caller hits every time              | P0   |
| `[BUG]` reachable only through an edge case or rare input          | P1   |
| `[API]` break: removed/renamed export, incompatible signature      | P1   |
| `[LOST-COMMENT]` that warned about a footgun or upstream bug       | P1   |
| `[INCONSISTENT]` where code and its docstring/types actually clash | P1   |
| `[DOC]` example that won't run as written                          | P1   |
| `[DOC]` wording that is merely stale or imprecise                  | P2   |
| `[LOST-COMMENT]` whose rationale is now obvious from the code      | P2   |
| `[NIT]`, naming preference, or a new vague public name             | P2   |

When a finding sits between tiers, ask how a caller experiences it: a wrong result on a common call is P0, a wrong result behind an unusual flag is P1, and something a reader would only notice while reading is P2.

### 6. Produce the review report

Write findings directly into the chat (do not create a file). Group by tier — P0 first — and tag each finding with both its tier and its category:

```markdown
## Pre-Ship Review

**Scope:** <N> commits, <M> files changed against `main`
**Findings:** <a> P0, <b> P1, <c> P2

### P0 — must fix before shipping

- [P0][BUG] <path>:<line>: <issue>

### P1 — should fix

- [P1][API] <path>:<line>: <issue>
- [P1][LOST-COMMENT] <path>:<line>: <quoted snippet of the removed comment> — <why the rationale still applies>

### P2 — nits and polish

- [P2][DOC] <path>:<line>: <issue>
```

Drop any tier section that has zero findings. If there are no findings at all, say so plainly.

### 7. Confirm next step with the user

After delivering the report, do not auto-fix. Offer to hand off to **refine-it** (`.agents/skills/refine-it/SKILL.md`), which verifies each finding against the code and applies its own fix-size policy — P0 always, P1 when the fix is small enough, P2 only when it's tiny and about this change.

Alternatives worth naming for the user:

- Ship as-is and accept the flagged tradeoffs
- Fix a specific subset of findings before shipping
- Split concerns out into separate PRs

## Category labels

Categories describe *what kind* of problem a finding is; the P-tier describes *how much it matters*.

| Label            | Meaning                                                                                                               |
| ---------------- | --------------------------------------------------------------------------------------------------------------------- |
| `[BUG]`          | Incorrect behavior the diff introduces                                                                                |
| `[INCONSISTENT]` | Code/docs/types disagree with each other or with the rest of the codebase                                             |
| `[DOC]`          | Docs/comments don't match the change                                                                                  |
| `[LOST-COMMENT]` | Diff removed a comment carrying irreplaceable rationale or warning                                                    |
| `[API]`          | Public-surface change worth calling out: removed/renamed export, changed signature, new vague public name, new export  |
| `[NIT]`          | Style or readability suggestion; reviewer-optional                                                                    |

## What NOT to do

- Do not run formatters, linters, or auto-fixers as part of the review
- Do not commit, push, or open PRs — this skill is read-only
- Do not fix findings yourself; that's **refine-it**'s job
- Do not repeat the entire diff back to the user; report only findings
- Do not flag changes inside `tests/` or `_*.py` modules as `[API]`
- Do not report a style nit as P0, and do not leave any finding untiered
