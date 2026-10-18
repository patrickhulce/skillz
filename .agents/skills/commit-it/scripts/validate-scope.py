#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Validate a conventional commit scope against this repo's scope rules.

Usage:
    python3 validate-scope.py "type(scope)"
    python3 validate-scope.py "type(scope): subject line"
    python3 validate-scope.py "type(scope)" -- path/to/file1 path/to/file2

Scope is required. Exit codes: 0 = valid, 1 = invalid scope, 2 = usage error.
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

SKILL_ROOTS = (".agents/skills", ".claude/skills", ".cursor/skills", "skills")
CODE_PREFIXES = ("components", "routes", "api", "lib")
MEMBER_ROOTS = ("packages", "apps")

EXTRA_COMMENT_RE = re.compile(r"<!--\s*skillz-commit-scopes:\s*(.*?)\s*-->", re.DOTALL)
HEADER_RE = re.compile(r"^(?P<type>[a-z][a-z0-9]*)\((?P<scope>[^)]*)\)$")

# Placeholders in extra-scope comments: "foo/<scope>", "bar/<*>", "baz".
PLACEHOLDER_CHANGED_FILE = "<scope>"
PLACEHOLDER_ARBITRARY = "<*>"

FORMAT_ERROR = (
    "ERROR: commit must be '<type>(<scope>): <description>'. "
    "Scope is required and is the most important part of the header. "
    "'<type>: <description>' is invalid."
)


@dataclass(frozen=True)
class ExtraRule:
    prefix: str
    kind: str  # "changed_file" | "arbitrary" | "bare"


@dataclass(frozen=True)
class Header:
    type: str
    scope: str


class ScopeError(Exception):
    """Invalid scope; message is already formatted for stderr."""


def parse_header(raw: str) -> Header:
    """Parse `<type>(<scope>)`, optionally with `!` and a `: subject`."""
    text = raw.strip()
    if not text:
        raise ScopeError(FORMAT_ERROR)
    header = text.split(":", 1)[0].strip()
    if header.endswith("!"):
        header = header[:-1].rstrip()
    if header.lower() == "treewide":
        raise ScopeError("ERROR: 'treewide' is banned. Split the commit into surface scopes. The only '*' scope is docs(*).")
    match = HEADER_RE.fullmatch(header)
    if match is None:
        raise ScopeError(FORMAT_ERROR)
    scope = match.group("scope").strip()
    if not scope:
        raise ScopeError("ERROR: scope is required. Use <type>(<scope>): <description>. Scope is the most important part of the header.")
    return Header(type=match.group("type"), scope=scope)


def repo_root_from_cwd(cwd: Path | None = None) -> Path:
    cwd = (cwd or Path.cwd()).resolve()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return cwd
    if result.returncode == 0:
        top = result.stdout.strip()
        if top:
            return Path(top)
    return cwd


def read_readme(root: Path) -> str:
    path = root / "README.md"
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def parse_extra_rules(readme: str) -> list[ExtraRule]:
    rules: list[ExtraRule] = []
    seen: set[tuple[str, str]] = set()
    for match in EXTRA_COMMENT_RE.finditer(readme):
        body = match.group(1).replace("\n", " ")
        for item in body.split(","):
            token = item.strip()
            if not token:
                continue
            if "/" in token:
                prefix, _, rest = token.partition("/")
                prefix = prefix.strip()
                rest = rest.strip()
                if not prefix:
                    continue
                if rest == PLACEHOLDER_CHANGED_FILE:
                    kind = "changed_file"
                elif rest == PLACEHOLDER_ARBITRARY:
                    kind = "arbitrary"
                else:
                    continue
            else:
                prefix = token
                kind = "bare"
            key = (prefix, kind)
            if key in seen:
                continue
            seen.add(key)
            rules.append(ExtraRule(prefix=prefix, kind=kind))
    return rules


def skill_dirs(root: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for rel in SKILL_ROOTS:
        parent = root / rel
        if not parent.is_dir():
            continue
        for child in parent.iterdir():
            if child.is_dir() and not child.name.startswith("."):
                found.setdefault(child.name, child)
    return found


def child_dir_names(path: Path) -> list[str]:
    if not path.is_dir():
        return []
    return sorted(child.name for child in path.iterdir() if child.is_dir())


def name_matches_dir(name: str, parent: Path) -> bool:
    if "*" in name or "?" in name or "[" in name:
        return any(fnmatch.fnmatch(child, name) for child in child_dir_names(parent))
    return (parent / name).is_dir()


def git_changed_files(root: Path) -> list[str]:
    files: list[str] = []
    for args in (
        ["git", "diff", "--name-only"],
        ["git", "diff", "--cached", "--name-only"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ):
        try:
            result = subprocess.run(args, cwd=root, capture_output=True, text=True, check=False)
        except FileNotFoundError:
            return []
        if result.returncode != 0:
            continue
        files.extend(line.strip() for line in result.stdout.splitlines() if line.strip())
    seen: set[str] = set()
    unique: list[str] = []
    for path in files:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


def tokens_from_paths(paths: list[str]) -> set[str]:
    tokens: set[str] = set()
    for raw in paths:
        normalized = raw.replace("\\", "/").strip().removeprefix("./")
        parts = [part for part in normalized.split("/") if part]
        if not parts:
            continue
        for part in parts:
            tokens.add(part)
        filename = parts[-1]
        if "." in filename and not filename.startswith("."):
            stem, ext = filename.rsplit(".", 1)
            if stem and ext:
                tokens.add(stem)
    return tokens


def has_spaces(value: str) -> bool:
    return any(ch.isspace() for ch in value)


def first_segment(scope: str) -> str:
    return scope.split("/", 1)[0]


def remainder(scope: str) -> str:
    if "/" not in scope:
        return ""
    return scope.split("/", 1)[1]


def member_parents(root: Path) -> list[tuple[str, Path]]:
    found: list[tuple[str, Path]] = []
    for name in MEMBER_ROOTS:
        parent = root / name
        if parent.is_dir():
            found.append((name, parent))
    return found


def allowed_patterns(extras: list[ExtraRule]) -> list[str]:
    lines = [
        "<type>(<scope>): <description>   (scope is required)",
        "infra(<tool>)                     (one segment, e.g. uv, eslint, ci)",
        "infra(skills)                     (adding a skill)",
        "infra(skills/<name>)              (name is an existing skill)",
        "<member>[/<scope>]                (directory under packages/ or apps/)",
        "components/<name>                 (changed folder or filename)",
        "routes/<name>",
        "api/<name>",
        "lib/<name>",
        "docs(*)                           (docs that are not one surface)",
    ]
    if extras:
        lines.append("repo extras (from README skillz-commit-scopes):")
        for rule in extras:
            if rule.kind == "changed_file":
                lines.append(f"  {rule.prefix}/<scope>")
            elif rule.kind == "arbitrary":
                lines.append(f"  {rule.prefix}/<*>")
            else:
                lines.append(f"  {rule.prefix}")
    return lines


def fail(message: str, extras: list[ExtraRule], extra_lines: list[str] | None = None) -> None:
    parts = [f"ERROR: {message}", "", "Allowed scopes:"]
    parts.extend(f"  {line}" for line in allowed_patterns(extras))
    if extra_lines:
        parts.append("")
        parts.extend(extra_lines)
    raise ScopeError("\n".join(parts))


def require_clean_suffix(suffix: str, scope: str, extras: list[ExtraRule]) -> None:
    if not suffix or has_spaces(suffix) or suffix.endswith("/"):
        fail(f"scope '{scope}' has an empty, trailing, or spaced suffix", extras)


def validate_skills(scope: str, root: Path, extras: list[ExtraRule]) -> str:
    name = remainder(scope)
    require_clean_suffix(name, scope, extras)
    if "/" in name:
        fail(f"skills/<name> must be a single skill name, not '{scope}'", extras)
    found = skill_dirs(root)
    if name in found:
        return f"OK: '{scope}' is an existing skill."
    extra = ["Known skills:"]
    extra.extend(f"  - {item}" for item in sorted(found) or [])
    if not found:
        extra.append("  (none found under .agents/skills, .claude/skills, .cursor/skills, or skills/)")
    fail(f"skills/{name} does not exist", extras, extra)


def validate_infra(scope: str, root: Path, extras: list[ExtraRule]) -> str:
    if scope == "skills":
        return "OK: 'skills' is the infra scope for adding a skill."
    if "/" not in scope:
        return f"OK: '{scope}' is an infra scope."
    if first_segment(scope) == "skills":
        return validate_skills(scope, root, extras)
    fail(
        f"infra scope '{scope}' must be a single tool name, skills, or skills/<name>",
        extras,
    )


def validate_changed_file_name(
    scope: str,
    name: str,
    changed_files: list[str],
    extras: list[ExtraRule],
) -> str:
    require_clean_suffix(name, scope, extras)
    tokens = tokens_from_paths(changed_files)
    if name in tokens:
        return f"OK: '{scope}' matches a changed folder or filename."
    extra = ["Changed-file tokens:"]
    extra.extend(f"  - {token}" for token in sorted(tokens) or [])
    if not changed_files:
        extra.append("  (no changed files given; pass them after -- )")
    fail(
        f"'{name}' is not a folder or filename in the changed files for this commit",
        extras,
        extra,
    )


def member_matches(name: str, root: Path) -> bool:
    if name == "*":
        return False
    return any(name_matches_dir(name, parent) for _, parent in member_parents(root))


def validate_member(scope: str, root: Path, extras: list[ExtraRule]) -> str:
    name = first_segment(scope)
    nested = remainder(scope)
    if nested.endswith("/") or (nested and has_spaces(nested)):
        fail(f"scope '{scope}' has an empty, trailing, or spaced suffix", extras)
    if member_matches(name, root):
        return f"OK: '{scope}' is a package or app member."
    extra = ["Known packages and apps:"]
    parents = member_parents(root)
    listed = False
    for label, parent in parents:
        names = child_dir_names(parent)
        if not names:
            continue
        listed = True
        extra.append(f"  {label}:")
        extra.extend(f"    - {item}" for item in names)
    if not parents:
        extra.append("  (no packages/ or apps/ directory)")
    elif not listed:
        extra.append("  (none)")
    fail(f"'{name}' does not exist under packages/ or apps/", extras, extra)


def validate_extra(
    scope: str,
    rule: ExtraRule,
    changed_files: list[str],
    extras: list[ExtraRule],
) -> str:
    rest = remainder(scope) if first_segment(scope) == rule.prefix else ""
    if rule.kind == "bare":
        if scope == rule.prefix:
            return f"OK: '{scope}' is a repo extra scope."
        fail(f"extra scope '{rule.prefix}' must be used bare, not '{scope}'", extras)
    if not rest:
        fail(f"extra scope '{rule.prefix}' requires a suffix ({rule.prefix}/...)", extras)
    if rule.kind == "arbitrary":
        require_clean_suffix(rest, scope, extras)
        return f"OK: '{scope}' matches extra scope {rule.prefix}/<*>."
    return validate_changed_file_name(scope, rest, changed_files, extras)


def validate_surface(scope: str, root: Path, changed_files: list[str], extras: list[ExtraRule]) -> str:
    head = first_segment(scope)

    if head == "feature" or scope == "feature":
        fail("'feature/<name>' is not a scope. Split the commit by surface.", extras)
    if head == "skills" or scope == "skills":
        fail("skills is only valid as infra(skills) or infra(skills/<name>)", extras)
    if head in MEMBER_ROOTS:
        fail(
            f"'{head}/' is not part of the scope. Use the member name, as in feat(<name>).",
            extras,
        )
    if head in CODE_PREFIXES:
        if scope == head:
            fail(f"{head}/<name> requires a changed folder or filename", extras)
        return validate_changed_file_name(scope, remainder(scope), changed_files, extras)

    if member_matches(head, root):
        return validate_member(scope, root, extras)

    matching = [rule for rule in extras if rule.prefix == head]
    if matching:
        rest = remainder(scope) if scope != head else ""
        if not rest:
            bare = next((rule for rule in matching if rule.kind == "bare"), None)
            if bare:
                return validate_extra(scope, bare, changed_files, extras)
            fail(f"extra scope '{head}' requires a suffix ({head}/...)", extras)
        last_error: ScopeError | None = None
        for kind in ("changed_file", "arbitrary"):
            rule = next((item for item in matching if item.kind == kind), None)
            if rule is None:
                continue
            try:
                return validate_extra(scope, rule, changed_files, extras)
            except ScopeError as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        fail(f"extra scope '{head}' must be used bare, not '{scope}'", extras)

    return validate_member(scope, root, extras)


def validate(header: Header, root: Path, changed_files: list[str]) -> str:
    scope = header.scope
    if has_spaces(scope):
        raise ScopeError(f"ERROR: scope '{scope}' contains spaces")
    if scope.startswith("/") or scope.endswith("/"):
        raise ScopeError(f"ERROR: scope '{scope}' must not start or end with '/'")

    readme = read_readme(root)
    extras = parse_extra_rules(readme)
    if header.type == "treewide" or scope.lower() == "treewide" or first_segment(scope).lower() == "treewide":
        fail(
            "'treewide' is banned. Split the commit into surface scopes.",
            extras,
        )
    if header.type == "docs" and scope == "*":
        return "OK: 'docs(*)' is documentation that is not one surface."
    if scope == "*":
        fail("'*' is only valid as docs(*).", extras)

    if header.type == "infra":
        return validate_infra(scope, root, extras)
    return validate_surface(scope, root, changed_files, extras)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a conventional commit scope. Scope is required.",
    )
    parser.add_argument("header", help="Commit header: type(scope) or type(scope): subject")
    parser.add_argument(
        "files",
        nargs="*",
        help="Changed files for this commit (used by components/routes/api/lib and extra <scope> rules)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 2
        return code if code != 0 else 0

    if not args.header or not str(args.header).strip():
        parser.print_usage(sys.stderr)
        return 2

    root = repo_root_from_cwd()
    files = list(args.files) if args.files else git_changed_files(root)
    try:
        header = parse_header(args.header)
        message = validate(header, root, files)
    except ScopeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
