---
type: command
if: "Bash(git push:*)"
command: |
  jq -r '.tool_input.command' | grep -qE '(^|[[:space:]])(--force(-with-lease)?|-f)([[:space:]]|=|$)' && echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"Force-push detected — confirm before rewriting remote history."}}' || true
---

Force-push guard: intercepts `git push --force` / `git push -f` / `git push --force-with-lease` and surfaces a confirmation prompt before the command runs, preventing accidental rewrites of remote history.
