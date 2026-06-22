---
name: polyglot-scaffold
description: >-
  Scaffold a polyglot monorepo with a Rust core library, Python bindings (PyO3/maturin),
  and TypeScript/Node bindings (napi-rs). Use when creating a new Rust library with Python
  and TypeScript bindings, setting up a polyglot monorepo, or bootstrapping a project like
  muxon. Triggers on polyglot, monorepo, PyO3, maturin, napi-rs, Rust Python TypeScript.
---

# Polyglot Scaffold

Scaffold a **Rust + Python + TypeScript** monorepo from the bundled runnable template.

## When to use

- New library needing Rust core with Python and Node/TS bindings
- Monorepo layout matching `src/rust-*`, `src/python-*`, `src/node-*`
- Replacing hand-rolled binding boilerplate

## Prerequisites

- Rust (stable), uv, pnpm 9+, Node 22+
- Destination directory must not already exist

## Workflow

### 1. Gather inputs

| Input            | Required | Default                 |
| ---------------- | -------- | ----------------------- |
| Project name     | yes      | —                       |
| Destination path | yes      | —                       |
| npm package name | no       | flat kebab project name |
| `--git-init`     | no       | off                     |

### 2. Run the scaffold script

From this skill directory:

```bash
python scripts/scaffold.py --name <project> --dest <path>
```

Examples:

```bash
python scripts/scaffold.py --name muxon --dest ~/Code/OpenSource/muxon
python scripts/scaffold.py --name cool-widget --dest ./cool-widget --npm-pkg @acme/cool-widget
python scripts/scaffold.py --name muxon --dest ./muxon --git-init
```

The script copies `template/` and replaces literal placeholder tokens (longest first):

| Token                                          | Replacement for `--name muxon` |
| ---------------------------------------------- | ------------------------------ |
| `myplaceholder_project._myplaceholder_project` | `muxon._muxon`                 |
| `myplaceholder_python_bindings`                | `muxon_python_bindings`        |
| `myplaceholder_node_bindings`                  | `muxon_node_bindings`          |
| `myplaceholder_rust_crate`                     | `muxon`                        |
| `myplaceholder_python_pkg`                     | `muxon`                        |
| `myplaceholder_project`                        | `muxon`                        |
| `myplaceholder-project`                        | `muxon`                        |
| `MyPlaceholderProject`                         | `Muxon`                        |
| `myPlaceholderProject`                         | `muxon`                        |
| `myplaceholder-napi-name`                      | `muxon-napi-name`              |
| `myplaceholder-npm-pkg`                        | `muxon` (or `--npm-pkg`)       |

Multi-word names derive snake/kebab/Pascal/camel forms automatically (`cool-widget` → `cool_widget`, `CoolWidget`, `coolWidget`, …).

### 3. Verify

```bash
cd <dest>
pnpm install   # if not already done
make
```

### 4. Customize

Replace the `echo` stub in `src/rust-<project>/src/lib.rs` with your real API. Keep Python (`_core.py`) and TypeScript (`src/index.ts`) wrappers thin — map types and delegate to Rust.

See [references/architecture.md](references/architecture.md) for layout and conventions.

## Anti-patterns

- Do not duplicate business logic in Python or TypeScript bindings
- Do not edit placeholder tokens in `template/` by hand when scaffolding — use the script
- Do not skip `make` verification after scaffolding
