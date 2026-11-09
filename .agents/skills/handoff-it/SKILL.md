---
name: handoff-it
description: Write HANDOFF.md in the current repository root so a future agent can resume the work. Use when asked to hand off a task or preserve session context for another agent.
---

# Handoff

Write or update `HANDOFF.md` in the current repository root with **everything a future agent needs to pick up exactly where you left off**, without this conversation. Review the conversation and repo state; preserve still-relevant context from any existing handoff.

Include:

- Objective, user requirements, constraints, decisions and rationale.
- Current state: relevant files, branch/commits, uncommitted work, setup, commands, artifacts and external references needed to resume.
- Completed work and verification commands/results; distinguish unverified work and known failures.
- Unfinished work, blockers, open questions, failed approaches and concrete next actions.
- Interesting next steps mentioned or deferred, clearly separated from required remaining work.

Be concrete and self-contained; omit no necessary context for brevity. Mark uncertainty and reference secret locations without copying credentials.
