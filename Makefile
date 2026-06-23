.PHONY: default ci build lint lint-fix test

default: ci
ci: build lint test

build:
	uv build

lint:
	uv run ruff check .
	uv run ruff format --check .

lint-fix:
	uv run ruff check --fix .
	uv run ruff format .

test:
	uv run pytest
