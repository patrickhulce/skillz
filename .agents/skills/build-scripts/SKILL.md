---
name: build-scripts
description: >-
  Guidance for structuring build, lint, typecheck, and test scripts across
  npm/pnpm, Makefiles, and Python invoke using a hierarchical task convention.
  Use when adding or organizing package.json scripts, Makefile targets, or
  invoke tasks, or setting up build commands in a repo.
---

# Build Scripts

Structure project automation as a small set of task primitives with consistent
scoping, so the same handful of commands work in every repo regardless of
language.

## Always have a top-level Makefile

Every repo gets a top-level `Makefile`, no matter the language. It is the
universal entry point: `make` always does the reasonable default combination, `make lint`
always lints + formats, `make typecheck` always typechecks, etc. In a
single-language repo the Makefile simply delegates to that language's tool; in a
mixed repo it delegates to each language's tool and wires them together. It must
never reimplement the per-language logic.

## Core primitives

Every project exposes five roots:

- `build` - builds the project for production
- `lint` - lints and formats the project
- `typecheck` - typechecks the project
- `test` - runs the full test suite
- `ci` - runs the full CI pipeline

Narrower scopes are suffixes on a primitive, following the language's own
conventions: `test-unit`, `test-e2e`, `lint-fix`. **Do not duplicate the full
scope tree into the Makefile.** Top-level `make` targets only need the roots
(plus per-language children in a mixed repo); finer scopes like `test-unit` live
in the language tool and are not worth a `make` target in a single-language repo.

## Optional top-level targets

Add these only when they apply; they are not part of the core primitives:

- `serve` — start the dev server. Use `serve-production`
  for a production-style local run. `npm start` is reserved for the actual
  production deployment entry point, never the dev server.
- `dev` — spin up multiple processes in parallel for an active build loop, e.g.
  run `serve` and `build-watch` concurrently.
- `eval` - runs soft test-like evaluation suites for ML projects.
- `train` - runs the training loop for ML projects.
- `deploy` - deploys the project to a production environment.
- `promote` - sets the tagged production version to latest.

## Separator convention

The scope separator depends on the tool, not the project:

| Tool                | Separator | Example                 |
| ------------------- | --------- | ----------------------- |
| Makefile targets    | hyphen    | `test-unit`, `lint-fix` |
| npm/pnpm scripts    | colon     | `test:unit`, `lint:fix` |
| Python invoke tasks | colon     | `test:unit`, `lint:fix` |

Never mix separators within one tool.

## Tool choice per language

The top-level Makefile delegates to whichever tool is idiomatic per language:

- **JS/TS**: pnpm with `package.json` scripts.
- **Python**: invoke (`tasks.py`).
- **Rust**: `cargo` directly.

The per-language tool owns the finer scopes (`test:unit`, `lint:fix`, …); the
Makefile only exposes the roots and optional top-level targets.

## Examples

### Single-language Makefile (delegates to the language tool)

Even a one-language repo gets a Makefile so `make`, `make lint`, etc. are
uniform. It just forwards to pnpm / invoke / cargo.

```makefile
.PHONY: default ci build lint typecheck test serve dev

default: ci
ci: build lint typecheck test

build:
	pnpm build
lint:
	pnpm lint
typecheck:
	pnpm typecheck
test:
	pnpm test

serve:
	pnpm serve
dev:
	pnpm dev
```

### Mixed-repo Makefile

Scoped targets use hyphens; each root aggregates its per-language children and
delegates to that language's tool. Finer scopes stay in the language tool.

```makefile
.PHONY: all build lint typecheck test ci serve dev \
        build-rust build-node \
        lint-rust lint-node \
        typecheck-node \
        test-rust test-node

default: ci
ci: build lint typecheck test

build: build-rust build-node
build-rust:
	cargo build --workspace
build-node:
	pnpm --dir src/node build

lint: lint-rust lint-node
lint-rust:
	cargo clippy -- -D warnings
lint-node:
	pnpm --dir src/node lint

typecheck: typecheck-node
typecheck-node:
	pnpm --dir src/node typecheck

test: test-rust test-node
test-rust:
	cargo test
test-node:
	pnpm --dir src/node test

serve:
	pnpm --dir src/node serve
dev:
	pnpm --dir src/node dev
```

### npm/pnpm package.json scripts

Scopes use colons; the bare primitive chains its scoped children.

```json
{
  "scripts": {
    "build:native": "napi build --release",
    "build:ts": "tsc",
    "build": "pnpm run build:native && pnpm run build:ts",
    "lint": "eslint . && prettier --check .",
    "lint:fix": "eslint --fix . && prettier --write .",
    "typecheck": "tsc --noEmit",
    "test": "node --test",
    "test:unit": "node --test test/unit",
    "test:e2e": "node --test test/e2e",
    "serve": "vite",
    "dev": "concurrently \"pnpm serve\" \"pnpm build:ts --watch\"",
    "start": "node dist/index.js"
  }
}
```

`start` is the production entry point, not the dev server — keep the dev server
under `serve`/`dev`.

### Python invoke tasks.py

Invoke supports colon-namespaced task names; declare them explicitly.

```python
from invoke import task


@task
def build(c):
    c.run("python -m build")


@task(name="lint")
def lint(c):
    c.run("ruff check .")
    c.run("ruff format --check .")


@task(name="lint:fix")
def lint_fix(c):
    c.run("ruff check --fix .")
    c.run("ruff format .")


@task(name="typecheck")
def typecheck(c):
    c.run("mypy .")


@task(name="test")
def test(c):
    c.run("pytest")


@task(name="test:unit")
def test_unit(c):
    c.run("pytest tests/unit")


@task(name="test:e2e")
def test_e2e(c):
    c.run("pytest tests/e2e")
```

Invoke them with `invoke test:unit`, `invoke lint:fix`, etc.

## Anti-patterns

- Don't mix separators within one tool (no `test:unit` in a Makefile, no
  `test-unit` in `package.json`).
- Don't duplicate logic across the Makefile and the per-language scripts —
  delegate from the Makefile, don't reimplement.
- Don't duplicate every finer scope into the Makefile — keep `make` to the roots
  plus optional top-level targets; let the language tool own `test-unit`, etc.
- Don't skip the top-level Makefile, even for a single-language repo.
- Don't use `start` for the dev server — it's reserved for production.
- Don't invent new primitives when a scope of an existing one fits.
