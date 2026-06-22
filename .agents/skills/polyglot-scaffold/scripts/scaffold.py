#!/usr/bin/env python3
"""Copy the polyglot-scaffold template and replace myplaceholder tokens."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = SKILL_ROOT / "template"

TOKEN_ORDER = [
    "myplaceholder_project._myplaceholder_project",
    "myplaceholder_python_bindings",
    "myplaceholder_node_bindings",
    "myplaceholder_rust_crate",
    "myplaceholder_python_pkg",
    "myplaceholder_project",
    "myplaceholder-project",
    "MyPlaceholderProject",
    "myPlaceholderProject",
    "myplaceholder-napi-name",
    "myplaceholder-npm-pkg",
]


@dataclass(frozen=True)
class NameForms:
    snake: str
    kebab: str
    pascal: str
    camel: str


def _split_parts(raw: str) -> list[str]:
    normalized = raw.strip().replace("-", "_")
    parts = [p for p in re.split(r"[_\s]+", normalized) if p]
    if not parts:
        raise ValueError("project name must not be empty")
    return parts


def parse_name(raw: str) -> NameForms:
    parts = _split_parts(raw)
    snake = "_".join(parts).lower()
    kebab = "-".join(parts).lower()
    pascal = "".join(part.capitalize() for part in parts)
    camel = pascal[0].lower() + pascal[1:] if pascal else ""
    return NameForms(snake=snake, kebab=kebab, pascal=pascal, camel=camel)


def validate_name(forms: NameForms) -> None:
    for label, value in (
        ("snake", forms.snake),
        ("kebab", forms.kebab),
        ("pascal", forms.pascal),
        ("camel", forms.camel),
    ):
        if not value:
            raise ValueError(f"invalid {label} form derived from project name")
    if not re.fullmatch(r"[a-z][a-z0-9_-]*", forms.kebab):
        raise ValueError(f"project name {forms.kebab!r} is not a valid kebab-case identifier")


IGNORE_NAMES = {
    "target",
    "node_modules",
    ".venv",
    "dist",
    "__pycache__",
    ".git",
    "binding.js",
    "binding.d.ts",
}
IGNORE_SUFFIXES = {".node", ".so", ".dylib", ".dll", ".whl", ".pyc"}


def _ignore_copy(_dir: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    for name in names:
        if name in IGNORE_NAMES or any(name.endswith(suffix) for suffix in IGNORE_SUFFIXES):
            ignored.add(name)
    return ignored


def replace_in_file(path: Path, mapping: dict[str, str]) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    for token in TOKEN_ORDER:
        if token in mapping:
            text = text.replace(token, mapping[token])
    path.write_text(text, encoding="utf-8")


def build_replacement_map(
    forms: NameForms,
    *,
    npm_pkg: str | None,
) -> dict[str, str]:
    snake = forms.snake
    kebab = forms.kebab
    npm = npm_pkg or kebab
    return {
        "myplaceholder_project._myplaceholder_project": f"{snake}._{snake}",
        "myplaceholder_python_bindings": f"{snake}_python_bindings",
        "myplaceholder_node_bindings": f"{snake}_node_bindings",
        "myplaceholder_rust_crate": snake,
        "myplaceholder_python_pkg": snake,
        "myplaceholder_project": snake,
        "myplaceholder-project": kebab,
        "MyPlaceholderProject": forms.pascal,
        "myPlaceholderProject": forms.camel,
        "myplaceholder-napi-name": f"{kebab}-napi-name",
        "myplaceholder-npm-pkg": npm,
    }


def replace_in_tree(dest: Path, mapping: dict[str, str]) -> None:
    for path in dest.rglob("*"):
        if path.is_file():
            replace_in_file(path, mapping)

    for path in sorted(dest.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        new_name = path.name
        for token in TOKEN_ORDER:
            if token in mapping:
                new_name = new_name.replace(token, mapping[token])
        if new_name != path.name:
            path.rename(path.with_name(new_name))


def copy_template(dest: Path, mapping: dict[str, str]) -> None:
    if dest.exists():
        raise FileExistsError(f"destination already exists: {dest}")
    shutil.copytree(TEMPLATE_DIR, dest, ignore=_ignore_copy)
    replace_in_tree(dest, mapping)


def maybe_git_init(dest: Path) -> None:
    subprocess.run(["git", "init"], cwd=dest, check=True, capture_output=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scaffold a polyglot Rust/Python/Node monorepo.")
    p.add_argument("--name", required=True, help="project name (kebab, snake, or plain)")
    p.add_argument("--dest", required=True, type=Path, help="output directory")
    p.add_argument("--npm-pkg", default=None, help="npm package name (flat or scoped); defaults to project kebab name")
    p.add_argument("--license", default="MIT", help="license identifier (default: MIT)")
    p.add_argument("--author", default=None, help="author name for generated files")
    p.add_argument("--git-init", action="store_true", help="run git init in the output directory")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        forms = parse_name(args.name)
        validate_name(forms)
        mapping = build_replacement_map(
            forms,
            npm_pkg=args.npm_pkg,
        )
        copy_template(args.dest.resolve(), mapping)
        if args.git_init:
            maybe_git_init(args.dest.resolve())
    except (ValueError, FileExistsError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Scaffolded project at {args.dest}")
    print("Next steps:")
    print(f"  cd {args.dest}")
    print("  make")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
