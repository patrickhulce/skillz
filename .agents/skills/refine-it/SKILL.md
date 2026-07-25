---
name: refine-it
description: Act on code review feedback — either a local review-it report or the unresolved review threads on a pull request. Verifies every claim against the actual code, fixes what's valid according to a severity and fix-size policy, replies in-thread, and resolves settled threads. Use when the user says "address the review findings", "handle the PR feedback", "respond to the reviewer", "fix what review-it found", or as a step inside the ship-it and sherpa-it workflows.
---

# Refine It (Address Review Feedback)

Work through code review feedback and apply the fixes that are worth applying. Feedback comes from one of two places: a **review-it** report produced locally before shipping, or the unresolved review threads on an open PR (AI reviewers and humans alike).

**Guiding principle:** do NOT take the reviewer at their word. A finding — especially one from an AI reviewer, including **review-it** itself — can be wrong, stale, or already handled. Verify every claim against the current code before editing or replying.

This skill edits code and replies to threads. It does **not** commit or push — the caller (the user, **ship-it**, or the **sherpa-it** monitor loop) owns commit/push so changes batch cleanly into one push.

## Workflow

### 1. Pick the feedback source

**Local mode** — the feedback is a **review-it** report. Use the report already produced in this session. If there isn't one, run **review-it** first (`.agents/skills/review-it/SKILL.md`) and use its output. Each finding already carries a tier and category, e.g. `[P1][BUG] src/auth/session.py:88: ...`.

**PR mode** — the feedback lives on the current branch's open PR. Resolve the repo and PR number:

```bash
REPO=$(gh repo view --json nameWithOwner --jq .nameWithOwner)
OWNER=$(echo "$REPO" | cut -d/ -f1)
NAME=$(echo "$REPO" | cut -d/ -f2)
PR_NUMBER=$(gh pr view --json number --jq .number)
```

If there is no open PR, tell the user and stop.

Review threads live behind GraphQL — `isResolved` and thread resolution are not exposed over REST:

```bash
gh api graphql -F owner="$OWNER" -F repo="$NAME" -F pr="$PR_NUMBER" -f query='
query($owner:String!,$repo:String!,$pr:Int!,$cursor:String){
  repository(owner:$owner,name:$repo){
    pullRequest(number:$pr){
      reviewThreads(first:100, after:$cursor){
        pageInfo{ hasNextPage endCursor }
        nodes{
          id isResolved isOutdated
          comments(first:50){ nodes{ databaseId author{login} body path line } }
        }
      }
    }
  }
}'
```

**Paginate.** A PR under active review (AI reviewers re-review on every push) can exceed 100 threads. If `pageInfo.hasNextPage` is `true`, re-run with `-F cursor="$END_CURSOR"` and merge the `nodes` until it's `false` — never operate on a truncated set. Comments per thread are capped at 50; if a thread has more, say so rather than silently dropping the tail.

Each thread's GraphQL node `id` is what you resolve with later. The first comment's `databaseId` is the REST comment id you reply to with `in_reply_to`.

Also fetch the top-level (non-inline) review bodies, since summary-level feedback never appears as a thread:

```bash
gh pr view --json reviews --jq '.reviews[] | {author: .author.login, state, body}'
```

### 2. Filter to actionable items

In PR mode, set aside:

- **Resolved** threads (`isResolved == true`) — never reopen them.
- Threads where the **last comment is yours** (the PR author) — the ball is in the reviewer's court; don't reply again.
- **Out-of-scope** threads: comments on vendored code (`vendor/`, `_vendor/`), generated files, or lines your diff didn't touch. Note them but don't act.
- **Non-actionable** praise, or pure nits with nothing concrete to change.

AI reviewers (Bugbot, Copilot, CodeRabbit) post as bot accounts and often prefix a severity on each comment. Treat their threads exactly like human ones — verify, then act.

In local mode there's nothing to filter: **review-it** already reports only findings.

### 3. Verify each item against the code

For every actionable item, open the referenced file at the referenced line and judge the claim against the CURRENT code — it may have changed since the review ran. Assign two things.

**a) A validity class:**

| Class               | Meaning                              | Action                                            |
| ------------------- | ------------------------------------ | ------------------------------------------------- |
| `valid`             | Real issue, still present            | Address per the policy in step 5                  |
| `already-addressed` | Fixed by a later edit or commit      | PR mode: reply "Verified fixed" and resolve       |
| `partial`           | Partly right; needs a judgment call  | Surface to the user before acting                 |
| `invalid`           | Reviewer is factually wrong          | Surface to the user; reply with a counter-argument |
| `needs-user-input`  | Design or product decision           | Ask the user via `AskQuestion`                    |
| `ignore`            | Out-of-scope or non-actionable       | No action                                         |

**b) A severity tier** — use the tier the reviewer already assigned (**review-it**'s `[P1]`, or an AI reviewer's `P0`/`P1`/`P2` prefix). If the feedback carries no tier, assign one:

- **P0** — a critical bug that breaks essential functionality for a frequent or obvious use case.
- **P1** — a bug or usage problem that might create errors in edge cases or rarer use cases.
- **P2** — style, pattern, optimization, or a nit.

### 4. Estimate the fix size

For each `valid` item, sketch what the fix would actually touch and estimate its line count. Count only the **production-code** delta — accompanying test changes don't count toward the estimate, and never let test volume push a fix over a threshold.

This estimate, not the size of the PR, is what gates the decision in step 5. A one-line guard clause and a refactor that reshapes three modules are very different responses to the same finding.

### 5. Decide what to address

Apply this policy to every `valid` item:

- **P0 — always address.** Non-negotiable, no matter how large the fix or how tangential to the change.
- **P1 — address if the fix is roughly 100 lines or less** (tests not counted). If the fix would be larger than that, defer it with a rationale.
- **P2 — address only if the fix is under about 10 lines** (tests not counted) AND the finding is about this change — meaning code this PR added or modified, not a pre-existing issue that merely sits near the diff. If either condition fails, skip it.

These are judgment thresholds, not hard limits. A 110-line P1 fix that's clearly the right call still gets made; a "10-line" P2 that quietly requires touching a public signature does not.

For any `valid` **P1 or P2 you decide NOT to address**, you still owe a written rationale — in-thread in PR mode (step 7), in the report in local mode (step 8). Never silently drop a valid finding.

Print a compact decision table before editing:

| Item                            | Class     | Tier | Est. fix   | Decision                 |
| ------------------------------- | --------- | ---- | ---------- | ------------------------ |
| `src/auth/session.py:88` expiry | `valid`   | P0   | ~6 lines   | address                  |
| `src/io/reader.py:210` retries  | `valid`   | P1   | ~250 lines | skip — fix too large     |
| `src/io/reader.py:31` naming    | `valid`   | P2   | ~2 lines   | address                  |
| `src/cli/main.py:12` unused arg | `invalid` | P1   | —          | ask user before pushback |

For any `invalid`, `partial`, or `needs-user-input` item, use `AskQuestion` **before** pushing back on a reviewer or making a judgment-call change.

### 6. Edit, then verify

Make the edits for the items you're addressing, batching related fixes. Follow the repo's own conventions (`AGENTS.md` / `CLAUDE.md`, existing patterns in the surrounding code), preserve why-comments, and keep any new comments terse.

Then verify the edits with the narrowest check that covers them, using the **test-it** skill (`.agents/skills/test-it/SKILL.md`) to discover the repo's real commands and scope the run to what changed:

```bash
make lint        # or make typecheck / make test — whichever the fixes touch
```

Repos following the **build-scripts** convention (`.agents/skills/build-scripts/SKILL.md`) expose `make lint`, `make typecheck`, `make test`, and `make ci`. Don't guess command names — let **test-it** discover them.

### 7. Reply and resolve (PR mode only)

Reply to the thread via REST `in_reply_to`, using the first comment's `databaseId` from step 1:

```bash
gh api "repos/$REPO/pulls/$PR_NUMBER/comments" \
  -f body="Verified fixed: <what changed, file:line>." \
  -F in_reply_to="$COMMENT_DATABASE_ID"
```

Reply conventions:

- `Verified fixed: …` — you made the change; cite the `file:line`.
- `Skip verified: …` — you accept the reviewer's own dismissal as correct.
- `Not addressing (P1|P2): …` — a valid finding you're deferring per step 5; give the reason (fix too large / pre-existing / unrelated to this change).
- A specific counter-argument citing file and lines when a claim is factually wrong — only after the user approves pushing back, per step 5.

Reply to every actionable thread you settle, bot-authored or human, so the reviewer sees their comment was acted on. The only threads you don't reply to are the ones step 2 filtered out because your comment is already the most recent. Never inject into an ongoing human-to-human back-and-forth.

Resolve a thread once it's genuinely settled — you fixed it, it was already addressed, or you replied with a deferral rationale — using the GraphQL thread `id`:

```bash
gh api graphql -F threadId="$THREAD_ID" -f query='
mutation($threadId:ID!){ resolveReviewThread(input:{threadId:$threadId}){ thread{ isResolved } } }'
```

Leave threads awaiting a human decision (`needs-user-input`, unresolved `invalid`) OPEN.

### 8. Report

Summarize for the user:

- How many items were addressed, with `file:line` for each fix
- Which were skipped and why (tier + fix size + rationale)
- Which you pushed back on, and which still need a human decision
- The result of the verification run from step 6

Then state plainly that the changes are **uncommitted**, so the caller knows they're ready to commit and push.

## Error handling

| Scenario                                   | Action                                                       |
| ------------------------------------------ | ------------------------------------------------------------ |
| No open PR for the branch (PR mode)        | Inform the user; suggest pushing and opening a PR first      |
| No review report available (local mode)    | Run **review-it** first, then continue                       |
| `gh api graphql` 401/403                   | Run `gh auth status`; the token needs `repo` scope for threads |
| Thread references a file not in the diff   | Classify `ignore`; note it, don't act                        |
| Reviewer claim you can't verify either way | Classify `needs-user-input`; ask the user                     |
| Verification fails after your fix          | Fix forward; do not hand back a red tree to the caller       |

## What NOT to do

- Do not commit or push — the caller batches and pushes
- Do not trust a finding without opening the code and checking it
- Do not silently drop a valid P1 or P2; defer with a written rationale instead
- Do not resolve a thread that's waiting on a human decision
- Do not expand a P2 nit into a refactor to satisfy the fix-size rule — skip it instead
