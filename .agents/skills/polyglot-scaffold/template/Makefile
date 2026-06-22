.PHONY: all build lint typecheck test \
        build-rust build-python build-node \
        lint-rust lint-python lint-node \
        typecheck-python typecheck-node \
        test-rust test-python test-node

all: build lint typecheck test

build: build-rust build-python build-node

build-rust:
	cargo build --workspace --exclude myplaceholder_python_bindings

build-python:
	cd src/python-myplaceholder-project && uv sync && uv run maturin develop --uv

build-node:
	pnpm --dir src/node-myplaceholder-project build

lint: lint-rust lint-python lint-node

lint-rust:
	cargo fmt --all -- --check
	cargo clippy -p myplaceholder_rust_crate -p myplaceholder_node_bindings -- -D warnings

lint-python:
	cd src/python-myplaceholder-project && uv run ruff check .
	cd src/python-myplaceholder-project && uv run ruff format --check .

lint-node:
	pnpm --dir src/node-myplaceholder-project lint

typecheck: typecheck-python typecheck-node

typecheck-python:
	cd src/python-myplaceholder-project && uv run mypy myplaceholder_project tests

typecheck-node:
	pnpm --dir src/node-myplaceholder-project typecheck

test: test-rust test-python test-node

test-rust:
	cargo test -p myplaceholder_rust_crate

test-python: build-python
	cd src/python-myplaceholder-project && uv run pytest

test-node: build-node
	pnpm --dir src/node-myplaceholder-project test
