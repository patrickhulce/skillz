#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Validate a commit scope against this repo's scope rules.

Usage:
    python3 validate-scope.py <scope>
    python3 validate-scope.py "scope: subject line"
    python3 validate-scope.py <scope> -- path/to/file1 path/to/file2

Exit codes: 0 = valid, 1 = invalid scope, 2 = usage error.
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
LABEL_PREFIXES = ("tests", "docs", "infra")
MONOREPO_PREFIXES = ("packages", "apps")

EXTRA_COMMENT_RE = re.compile(r"<!--\s*skillz-commit-scopes:\s*(.*?)\s*-->", re.DOTALL)
FEATURE_ITEM_RE = re.compile(
    r"(?:^|\n)\s*[-*]\s+\*\*`?(?P<name>[^`*]+)`?\*\*(?: -|:| —)\s+\w+",
)

# Placeholders in extra-scope comments: "foo/<scope>", "bar/<*>", "baz".
PLACEHOLDER_CHANGED_FILE = "<scope>"
PLACEHOLDER_ARBITRARY = "<*>"


@dataclass(frozen=True)
class ExtraRule:
    prefix: str
    kind: str  # "changed_file" | "arbitrary" | "bare"


class ScopeError(Exception):
    """Invalid scope; message is already formatted for stderr."""


def parse_scope(raw: str) -> str:
    """Take the token before ':' and strip a trailing breaking-change '!'."""
    scope = raw.split(":", 1)[0].strip()
    if scope.endswith("!"):
        scope = scope[:-1].rstrip()
    return scope


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


def feature_names_in_readme(readme: str) -> set[str]:
    return {match.group("name").strip() for match in FEATURE_ITEM_RE.finditer(readme)}


def feature_listed(name: str, readme: str) -> bool:
    escaped = re.escape(name)
    pattern = re.compile(
        rf"(?:^|\n)\s*[-*]\s+\*\*`?{escaped}`?\*\*(?: -|:| —)\s+\w+",
    )
    return pattern.search(readme) is not None


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
    # Preserve order, drop dupes.
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


def allowed_patterns(root: Path, extras: list[ExtraRule]) -> list[str]:
    lines = [
        "skills/<name>",
        "tests[/<scope>]",
        "docs[/<scope>]",
        "infra[/<scope>]",
        "packages/<name>[/<scope>]  (packages/<name> must exist)",
        "apps/<name>[/<scope>]      (apps/<name> must exist)",
        "components/<name>          (name is a changed folder or filename)",
        "routes/<name>",
        "api/<name>",
        "lib/<name>",
        "feature/<name>             (name listed as **name** in README.md)",
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


def fail(message: str, root: Path, extras: list[ExtraRule], extra_lines: list[str] | None = None) -> None:
    parts = [f"ERROR: {message}", "", "Allowed scopes:"]
    parts.extend(f"  {line}" for line in allowed_patterns(root, extras))
    if extra_lines:
        parts.append("")
        parts.extend(extra_lines)
    raise ScopeError("\n".join(parts))


def require_clean_suffix(suffix: str, scope: str, root: Path, extras: list[ExtraRule]) -> None:
    if not suffix or has_spaces(suffix) or suffix.endswith("/"):
        fail(f"scope '{scope}' has an empty, trailing, or spaced suffix", root, extras)


def validate_label_prefix(scope: str, prefix: str, root: Path, extras: list[ExtraRule]) -> str:
    rest = remainder(scope) if first_segment(scope) == prefix else ""
    if scope == prefix:
        return f"OK: '{scope}' is an allowed label scope."
    require_clean_suffix(rest, scope, root, extras)
    return f"OK: '{scope}' is an allowed label scope."


def validate_skills(scope: str, root: Path, extras: list[ExtraRule]) -> str:
    name = remainder(scope)
    require_clean_suffix(name, scope, root, extras)
    if "/" in name:
        fail(f"skills/<name> must be a single skill name, not '{scope}'", root, extras)
    found = skill_dirs(root)
    if name in found:
        return f"OK: '{scope}' is a skill."
    extra = ["Known skills:"]
    extra.extend(f"  - {item}" for item in sorted(found) or [])
    if not found:
        extra.append("  (none found under .agents/skills, .claude/skills, .cursor/skills, or skills/)")
    fail(f"skills/{name} does not exist", root, extras, extra)


def validate_monorepo(scope: str, prefix: str, root: Path, extras: list[ExtraRule]) -> str:
    parent = root / prefix
    rest = remainder(scope)
    require_clean_suffix(rest, scope, root, extras)
    name, _, nested = rest.partition("/")
    if not parent.is_dir():
        fail(f"'{prefix}/' does not exist in this repo", root, extras)
    if nested.endswith("/") or (nested and has_spaces(nested)):
        fail(f"scope '{scope}' has an empty, trailing, or spaced suffix", root, extras)
    if name_matches_dir(name, parent):
        return f"OK: '{scope}' is a {prefix} surface."
    extra = [f"Known {prefix}:"]
    extra.extend(f"  - {item}" for item in child_dir_names(parent) or [])
    fail(f"{prefix}/{name} does not exist", root, extras, extra)


def validate_changed_file_name(
    scope: str,
    name: str,
    changed_files: list[str],
    root: Path,
    extras: list[ExtraRule],
) -> str:
    require_clean_suffix(name, scope, root, extras)
    tokens = tokens_from_paths(changed_files)
    if name in tokens:
        return f"OK: '{scope}' matches a changed folder or filename."
    extra = ["Changed-file tokens:"]
    extra.extend(f"  - {token}" for token in sorted(tokens) or [])
    if not changed_files:
        extra.append("  (no changed files given; pass them after -- )")
    fail(
        f"'{name}' is not a folder or filename in the changed files for this commit",
        root,
        extras,
        extra,
    )


def validate_feature(scope: str, root: Path, extras: list[ExtraRule], readme: str) -> str:
    name = remainder(scope)
    require_clean_suffix(name, scope, root, extras)
    if feature_listed(name, readme):
        return f"OK: '{scope}' is a named feature in README.md."
    extra = [
        "feature/<name> requires a README.md list item like:",
        "  - **name** - description",
        "  - **name**: description",
        "  * **name** — description",
        "Add the feature to README.md, or split into surface-scoped commits.",
    ]
    listed = sorted(feature_names_in_readme(readme))
    if listed:
        extra.append("Features listed in README.md:")
        extra.extend(f"  - {item}" for item in listed)
    fail(f"'{name}' is not listed as a **name** feature in README.md", root, extras, extra)


def validate_extra(
    scope: str,
    rule: ExtraRule,
    changed_files: list[str],
    root: Path,
    extras: list[ExtraRule],
) -> str:
    rest = remainder(scope) if first_segment(scope) == rule.prefix else ""
    if rule.kind == "bare":
        if scope == rule.prefix:
            return f"OK: '{scope}' is a repo extra scope."
        fail(f"extra scope '{rule.prefix}' must be used bare, not '{scope}'", root, extras)
    if not rest:
        fail(f"extra scope '{rule.prefix}' requires a suffix ({rule.prefix}/...)", root, extras)
    if rule.kind == "arbitrary":
        require_clean_suffix(rest, scope, root, extras)
        return f"OK: '{scope}' matches extra scope {rule.prefix}/<*>."
    return validate_changed_file_name(scope, rest, changed_files, root, extras)


def validate(scope: str, root: Path, changed_files: list[str]) -> str:
    if not scope:
        raise ScopeError("ERROR: empty scope")
    if has_spaces(scope):
        raise ScopeError(f"ERROR: scope '{scope}' contains spaces")
    if scope.startswith("/") or scope.endswith("/"):
        raise ScopeError(f"ERROR: scope '{scope}' must not start or end with '/'")

    readme = read_readme(root)
    extras = parse_extra_rules(readme)
    head = first_segment(scope)

    if head.lower() == "treewide" or scope.lower() == "treewide":
        fail(
            "'treewide' is banned. Use a surface prefix, or feature/<name> if README.md documents that feature.",
            root,
            extras,
        )
    if scope == "*":
        fail("'*' is banned as a whole-tree scope. Use a surface prefix or feature/<name>.", root, extras)

    if head == "skills":
        if scope == "skills":
            fail("skills/<name> requires a skill name", root, extras)
        return validate_skills(scope, root, extras)

    if head in LABEL_PREFIXES:
        return validate_label_prefix(scope, head, root, extras)

    if head in MONOREPO_PREFIXES:
        if scope == head:
            fail(f"{head}/<name> requires a member name", root, extras)
        return validate_monorepo(scope, head, root, extras)

    if head in CODE_PREFIXES:
        if scope == head:
            fail(f"{head}/<name> requires a changed folder or filename", root, extras)
        return validate_changed_file_name(scope, remainder(scope), changed_files, root, extras)

    if head == "feature":
        if scope == "feature":
            fail("feature/<name> requires a feature name listed in README.md", root, extras)
        return validate_feature(scope, root, extras, readme)

    matching = [rule for rule in extras if rule.prefix == head]
    if matching:
        rest = remainder(scope) if scope != head else ""
        if not rest:
            bare = next((rule for rule in matching if rule.kind == "bare"), None)
            if bare:
                return validate_extra(scope, bare, changed_files, root, extras)
            fail(f"extra scope '{head}' requires a suffix ({head}/...)", root, extras)
        last_error: ScopeError | None = None
        for kind in ("changed_file", "arbitrary"):
            rule = next((item for item in matching if item.kind == kind), None)
            if rule is None:
                continue
            try:
                return validate_extra(scope, rule, changed_files, root, extras)
            except ScopeError as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        fail(f"extra scope '{head}' must be used bare, not '{scope}'", root, extras)

    fail(f"'{scope}' does not match an allowed prefix", root, extras)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a commit scope against this repo's scope rules.",
    )
    parser.add_argument("scope", help="Bare scope or a full 'scope: subject' line")
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

    if not args.scope or not str(args.scope).strip():
        parser.print_usage(sys.stderr)
        return 2

    root = repo_root_from_cwd()
    scope = parse_scope(args.scope)
    files = list(args.files) if args.files else git_changed_files(root)
    try:
        message = validate(scope, root, files)
    except ScopeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
