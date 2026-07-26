---
type: command
if: "Bash(git push:*)"
command: |
  cmd=$(jq -r '.tool_input.command // empty')
  echo "$cmd" | grep -qE '(^|[[:space:]]|;)git([[:space:]]+[^[:space:]]+)*[[:space:]]+push([[:space:]]|$)' || exit 0
  echo "$cmd" | grep -qE '(^|[[:space:]])(--force(-with-lease)?|-f)([[:space:]]|=|$)|[[:space:]]\+[^[:space:]]' && echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"Force-push detected — confirm before rewriting remote history."}}' || true
---

Force-push guard: intercepts `git push --force` / `git push -f` / `git push --force-with-lease` / `git push origin +ref` and surfaces a confirmation prompt before the command runs, preventing accidental rewrites of remote history.
