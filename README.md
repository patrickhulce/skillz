# skillz

Personal agent skills for the AI era.

## Quick Start

```bash
curl -fsSL https://raw.githubusercontent.com/patrickhulce/skillz/main/install.sh | bash
```

Installs skills into either:

- **`~/.agents/skills/`** — available in every project (default)
- **`<repo>/.agents/skills/`** — scoped to one project (`--target repo`)

Re-run the same command any time to update. Skills installed by skillz carry a hidden trailer so updates are non-destructive and hand-edited skills are never silently overwritten.

### Requirements

- `python3.11` _or_ `uv` on `PATH`
- `curl`

### Useful flags

```bash
./install.sh --target user             # install into ~/.agents/skills/
./install.sh --target repo --yes       # non-interactive, install into repo
./install.sh --dry-run                 # show the plan, write nothing
./install.sh --overwrite-conflicts     # replace hand-edited skills
./install.sh --branch my-feature       # shorthand → refs/heads/my-feature
./install.sh --ref refs/tags/v1.0.0    # full ref (sha, heads, tags, ...) verbatim
SKILLZ_BRANCH=my-feature ./install.sh   # same as --branch
SKILLZ_REF=refs/heads/foo ./install.sh  # explicit ref without rewriting
```

## Skills Provided

- **`polyglot-scaffold`** — Scaffold a Rust + Python + TypeScript monorepo (PyO3/maturin + napi-rs) from a runnable template. See [.agents/skills/polyglot-scaffold/SKILL.md](.agents/skills/polyglot-scaffold/SKILL.md).
- **`build-scripts`** — Structure build, lint, typecheck, and test scripts across npm/pnpm, Makefiles, and Python invoke using a hierarchical task convention. See [.agents/skills/build-scripts/SKILL.md](.agents/skills/build-scripts/SKILL.md).

## Development

Skill scripts are tested end-to-end:

```bash
uv sync --dev
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Requires Rust, uv, pnpm, and Node 22 on `PATH` for polyglot-scaffold integration tests.

## License

MIT
