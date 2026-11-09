---
name: sitrep
description: Quickly assess a repository's current work, git and PR status, progress against root TODO/design/handoff files, and recommended next steps. Use when asked for a sitrep, repo status briefing, where things stand, or what to work on next.
---

# Repository Situation Report

Produce a brief, evidence-backed answer to: **What is this repo doing, where does the current work stand, and what should happen next?** Explore enough to orient the user without turning the briefing into a full code review or exhaustive branch audit.

This is an inspection workflow. Do not edit files, update checkboxes, stash, switch branches, pull, rebase, commit, delete branches, or post to a PR as part of the report. Recommend follow-up actions; execute them only if the user's request also authorizes that work.

## Establish the local state

- Locate the repository root and read applicable repository instructions. If this is not a git repository, report that and inspect the available project/planning files instead.
- Read the root README and enough manifests or directory structure to explain the project's purpose and normal development workflow.
- Inspect `git status --short --branch`, the current branch or detached HEAD, configured remotes and upstream, and recent commits. Note staged, unstaged, and untracked work separately, plus conflicts or an in-progress merge/rebase.
- Use diff summaries first, then inspect the relevant hunks and untracked files to identify what the current work is trying to accomplish. Do not dump every changed file or read generated artifacts and secrets.
- Identify the actual default branch and, when applicable, the PR's base branch; do not assume `main` or `origin`. Compare branch commits and changes against the appropriate available base. Label ahead/behind counts as relative to locally cached refs unless their freshness has been verified.

## Establish the PR state

Use the available hosting connector or CLI to query current remote state. On GitHub, `gh pr view` is a useful starting point; also search the identified repository with `gh pr list --state all --head <branch>` so closed and merged PRs are not missed. Confirm the head repository and branch, especially for forks or reused branch names. For detached HEADs, use commit-associated PRs when supported. Do not arbitrarily select one PR when several match.

For a relevant PR, capture its URL, title, base/head, open/closed/merged state, draft status, and merge time when present. For an open PR, summarize available check results, review decisions, and unresolved feedback that affects the next step. Avoid downloading every CI log or comment unless needed to explain a blocker.

Keep these distinctions explicit:

- A closed PR is not necessarily merged. Use the host's merge metadata.
- A merged PR does not prove that all current local work landed. Compare the PR's recorded head with local commits and inspect uncommitted work for additions after that PR.
- Squash and rebase merges can leave different commit IDs. A failed ancestry check or nonempty three-dot diff alone does not prove the work is absent from the base; inspect relevant patches or current base content when that distinction matters.
- An old merged PR for a reused branch does not describe a newer PR or later commits.

If no PR is found, state the scope of the successful search. If the CLI, authentication, network, or host support is unavailable, say PR status is **unknown**, not that no PR exists. Continue with local evidence. Avoid fetching by default; if fresh base content is necessary, a targeted fetch without pruning is acceptable, and should be disclosed. Never present cached remote refs as verified live state.

## Reconcile plans with reality

Inspect root planning/context files, including untracked files: `TODO.md`, `HANDOFF.md`, `PLAN.md`, `DESIGN.md`, `ROADMAP.md`, and similarly named proposals or notes. Follow links into design directories only where relevant to the active work. If none exist, say so and use the README, current diff, commits, and PR context to infer the immediate objective.

For each relevant plan or milestone, distinguish **done**, **in progress**, **remaining**, **blocked**, and **uncertain/stale**, citing the supporting file, commit, or PR. Check claims against targeted code and tests:

- An unchecked item may already be implemented; a checked item may be incomplete or superseded.
- Implementation, test presence, and verified test results are different evidence. Do not claim tests passed merely because tests exist or a handoff says they once passed.
- A design proposal is not automatically an accepted requirement. Note conflicting plans or missing decisions rather than inventing a resolution.

Keep this pass bounded to the current objective and near-term work. Summarize large backlogs by milestone instead of investigating every item. Do not launch builds or test suites just to produce a quick status briefing; report existing verification evidence and recommend a focused check where needed.

## Deliver the briefing

Lead with the most consequential finding, then give a concise account of:

- **Current work:** project purpose, branch, local changes, and their apparent intent.
- **PR and integration:** relevant PR link/state, blockers, and whether additional local work remains after any merge.
- **Plan progress:** relevant root files and the status of their near-term items, with evidence and uncertainties. Use a small table if several plans need comparison.
- **Next steps:** a short ordered list of concrete actions, prioritizing conflicts/blockers, finishing active work, verification, and integration before speculative new features. Explain why the first action should come first.

Separate observations from inferences. Link to useful files and PRs rather than reproducing command output. State material limits on the report's freshness or coverage. End with a clear recommended next action; do not require the user to answer a question just to receive the briefing.
