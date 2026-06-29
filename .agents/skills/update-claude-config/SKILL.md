---
name: update-claude-config
description: >
  Guide for adding or modifying Claude Code settings managed by this dotfiles
  repo. Use when asked to change a Claude setting, add a hook, update
  permissions, or modify anything in ~/.claude/settings.json. Changes must go
  through this repo — direct edits to settings.json are overwritten on the next
  install. Triggers on phrases like "add a hook", "change the model", "update
  Claude settings", "add a permission", "configure Claude Code", or "why was my
  setting overwritten".
---

# update-claude-config

Claude Code settings at `~/.claude/settings.json` are managed by this repo's installer. **Do not edit that file directly** for settings you want to persist — the installer will overwrite or remove anything it recognizes as its own on the next run.

## How it works

The installer maintains a manifest at `~/.claude/skillz_manifest.json` tracking what it last wrote. On each run it:

- Writes scalar settings it owns (or skips with a warning if the user has customized them)
- Compiles hooks from `hooks/<EventName>/<MatcherName>/<NN_slug>.md` files in this repo
- Removes hooks that were in the previous manifest but are no longer in the repo (deleted hooks are cleaned up)
- Preserves any hooks or settings the user added manually outside of this repo

## Adding or changing a scalar setting

Edit `DESIRED_CLAUDE_SETTINGS` in `src/skillz/install.py`:

```python
DESIRED_CLAUDE_SETTINGS = {
    "feedbackSurveyRate": 0,
    "model": "opus",
    # add your new key here
}
```

Then re-run the installer:

```bash
./install.sh
```

## Adding a new hook

Create a markdown file at the appropriate path:

```
hooks/<EventName>/<MatcherName>/<NN_slug>.md
```

- `EventName` — Claude hook event (e.g. `PreToolUse`, `PostToolUse`, `Stop`)
- `MatcherName` — tool matcher (e.g. `Bash`, `Edit`, `Write`)
- `NN_slug` — two-digit priority prefix + descriptive name (e.g. `00_force_push.md`); files are sorted alphabetically within a matcher group

Frontmatter fields:

| Field | Required | Description |
|-------|----------|-------------|
| `type` | yes | Hook type — always `command` |
| `command` | yes | Shell command to run; use a `\|` block scalar for long commands |
| `if` | no | Conditional pattern (e.g. `Bash(git push:*)`) |

Example `hooks/PreToolUse/Bash/01_my_hook.md`:

```markdown
---
type: command
if: "Bash(some pattern:*)"
command: |
  echo "do something"
---

Plain-English description of what this hook does.
```

Then re-run the installer:

```bash
./install.sh
```

## Removing a hook

Delete the `.md` file and re-run the installer. The installer will detect the hook was in the previous manifest but is no longer desired and remove it from `~/.claude/settings.json`.

## Force-overwriting all settings

Use this when you want to reset `~/.claude/settings.json` fully to what this repo specifies, discarding any local customizations:

```bash
SKILLZ_FORCE_CONFIG=1 ./install.sh
# or
./install.sh --force-config
```

## Dry-run preview

```bash
./install.sh --dry-run
```

Shows what the installer _would_ change in settings.json without writing anything.
