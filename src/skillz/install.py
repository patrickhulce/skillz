#!/usr/bin/env python3
"""
skillz install.py - fetch agent skills from skillz and lay them down under
either ``~/.agents/skills/`` (default) or the current git repo's
``.agents/skills/`` (only when explicitly requested).

Designed to be invoked by ``install.sh`` (which validates Python 3.11 / uv
first), but is also runnable directly:

    python3.11 src/skillz/install.py [--target user|repo] [--ref REF] [--branch NAME] [--yes]
                                  [--overwrite-conflicts] [--dry-run]

Constraints (deliberate):
  - stdlib only, so it can run under ``uv run --python 3.11 --no-project``
  - network via ``urllib.request`` against GitHub API + raw.githubusercontent.com
  - never invokes ``git clone``; uses GitHub REST + raw blob endpoints
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

DEFAULT_REPO = os.environ.get("SKILLZ_REPO", "patrickhulce/skillz")
SKILLS_PREFIX = ".agents/skills/"
TRAILER_MARKER = "skillz:install-metadata"
GITHUB_API = "https://api.github.com"
RAW_HOST = "raw.githubusercontent.com"

TRAILER_BLOCK_RE = re.compile(
    r"<!--\s*" + re.escape(TRAILER_MARKER) + r"\s*\n(?P<body>.*?)-->",
    re.DOTALL,
)
TRAILER_HASH_RE = re.compile(r"^git-hash:\s*(?P<sha>[0-9a-f]{40})\s*$", re.MULTILINE)


def effective_install_ref_from_env() -> str:
    b = os.environ.get("SKILLZ_BRANCH", "").strip()
    if b:
        return f"refs/heads/{b}"
    r = os.environ.get("SKILLZ_REF", "").strip()
    if r:
        return r
    return "refs/heads/main"


def resolve_install_ref(cli_ref: str | None, cli_branch: str | None) -> str:
    if cli_branch and cli_branch.strip():
        return f"refs/heads/{cli_branch.strip()}"
    if cli_ref is not None and cli_ref.strip():
        return cli_ref.strip()
    return effective_install_ref_from_env()


def info(msg: str) -> None:
    print(f"\033[36m[..]\033[0m   {msg}")


def ok(msg: str) -> None:
    print(f"\033[32m[OK]\033[0m   {msg}")


def warn(msg: str) -> None:
    print(f"\033[33m[!!]\033[0m   {msg}", file=sys.stderr)


def fail(msg: str) -> None:
    print(f"\033[31m[FAIL]\033[0m {msg}", file=sys.stderr)


def http_get(url: str, *, accept: str | None = None) -> bytes:
    headers = {"User-Agent": "skillz-installer"}
    if accept:
        headers["Accept"] = accept
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"HTTP {exc.code} for {url}\n{body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"request failed for {url}: {exc}") from exc


def gh_json(url: str) -> dict | list:
    body = http_get(url, accept="application/vnd.github+json")
    return json.loads(body.decode("utf-8"))


@dataclass
class SkillFile:
    repo_path: str
    mode: str
    size: int

    @property
    def is_executable(self) -> bool:
        return self.mode in {"100755", "100775"}


@dataclass
class Skill:
    name: str
    files: list[SkillFile] = field(default_factory=list)


@dataclass
class PlanEntry:
    skill: Skill
    classification: str
    dest: Path
    existing_hash: str | None = None


def resolve_install_sha(repo: str, ref: str) -> tuple[str, str]:
    info(f"resolving commit SHA for {repo}@{ref}")
    data = gh_json(f"{GITHUB_API}/repos/{repo}/commits/{ref}")
    if not isinstance(data, dict) or "sha" not in data:
        raise RuntimeError(f"unexpected response resolving {ref}: {data!r}")
    sha = data["sha"]
    tree_sha = data.get("commit", {}).get("tree", {}).get("sha")
    if not tree_sha:
        raise RuntimeError(f"commit response missing tree.sha: {data!r}")
    ok(f"install commit: {sha} (tree {tree_sha})")
    return sha, tree_sha


def enumerate_skills(repo: str, tree_sha: str) -> list[Skill]:
    info(f"enumerating {SKILLS_PREFIX} via git tree API")
    data = gh_json(f"{GITHUB_API}/repos/{repo}/git/trees/{tree_sha}?recursive=1")
    if not isinstance(data, dict) or "tree" not in data:
        raise RuntimeError(f"unexpected tree response: {data!r}")
    if data.get("truncated"):
        warn("git tree response was truncated; very large repos are not supported")

    skills: dict[str, Skill] = {}
    for entry in data["tree"]:
        path = entry.get("path", "")
        if entry.get("type") != "blob":
            continue
        if not path.startswith(SKILLS_PREFIX):
            continue
        rest = path[len(SKILLS_PREFIX) :]
        if "/" not in rest:
            continue
        skill_name, _ = rest.split("/", 1)
        sf = SkillFile(repo_path=path, mode=entry.get("mode", "100644"), size=entry.get("size", 0))
        skills.setdefault(skill_name, Skill(name=skill_name)).files.append(sf)

    if not skills:
        raise RuntimeError(f"no skills found under {SKILLS_PREFIX} in tree {tree_sha}")
    ok(f"found {len(skills)} skill(s): {', '.join(sorted(skills))}")
    return [skills[name] for name in sorted(skills)]


def detect_repo_root() -> Path | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    root = result.stdout.strip()
    return Path(root) if root else None


def choose_target(args: argparse.Namespace) -> Path:
    repo_root = detect_repo_root()
    repo_dir = repo_root / ".agents" / "skills" if repo_root else None
    user_dir = Path.home() / ".agents" / "skills"

    if args.target == "repo":
        if not repo_dir:
            fail("--target=repo specified but cwd is not inside a git repository")
            sys.exit(2)
        return repo_dir
    if args.target == "user":
        return user_dir

    if not repo_dir:
        ok(f"not in a git repo; installing to user dir: {user_dir}")
        return user_dir

    if args.yes:
        ok(f"--yes; defaulting to user dir: {user_dir} (pass --target repo to install repo-locally)")
        return user_dir
    if not sys.stdin.isatty():
        ok(f"stdin is not a tty; defaulting to user dir: {user_dir} (pass --target repo to install repo-locally)")
        return user_dir

    prompt = f"Install into [u]ser ({user_dir}) or [r]epo ({repo_dir})? [U/r]: "
    answer = input(prompt).strip().lower() or "u"
    if answer.startswith("u"):
        return user_dir
    if answer.startswith("r"):
        return repo_dir
    fail(f"unrecognized answer: {answer!r}")
    sys.exit(2)


def parse_existing_trailer(skill_md: Path) -> str | None:
    if not skill_md.is_file():
        return None
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError:
        return None
    match = TRAILER_BLOCK_RE.search(text)
    if not match:
        return None
    body = match.group("body")
    hash_match = TRAILER_HASH_RE.search(body)
    return hash_match.group("sha") if hash_match else "unknown"


def classify(skills: Iterable[Skill], target_dir: Path, install_sha: str) -> list[PlanEntry]:
    plan: list[PlanEntry] = []
    for skill in skills:
        dest = target_dir / skill.name
        skill_md = dest / "SKILL.md"
        if not dest.exists():
            plan.append(PlanEntry(skill=skill, classification="new", dest=dest))
            continue
        existing = parse_existing_trailer(skill_md)
        if existing is None:
            plan.append(PlanEntry(skill=skill, classification="conflict", dest=dest))
        elif existing == install_sha:
            plan.append(PlanEntry(skill=skill, classification="ours-current", dest=dest, existing_hash=existing))
        else:
            plan.append(PlanEntry(skill=skill, classification="ours-stale", dest=dest, existing_hash=existing))
    return plan


def maybe_resolve_conflicts(plan: list[PlanEntry], args: argparse.Namespace) -> bool:
    conflicts = [p for p in plan if p.classification == "conflict"]
    if not conflicts:
        return True
    if args.overwrite_conflicts:
        warn(f"--overwrite-conflicts; will overwrite {len(conflicts)} conflicting skill(s)")
        return True

    print()
    print(f"Found {len(conflicts)} existing skill(s) not installed by skillz:")
    for p in conflicts:
        print(f"  - {p.skill.name:<32} ({p.dest})")
    print()
    print("These may have been hand-edited. Overwriting will replace them entirely.")

    if args.yes:
        warn("--yes does not auto-overwrite conflicts; pass --overwrite-conflicts for that. Skipping conflicts.")
        return False
    if not sys.stdin.isatty():
        warn("stdin is not a tty; skipping conflicts. Pass --overwrite-conflicts to force.")
        return False

    answer = input("Overwrite ALL of these with skillz versions? [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def build_trailer(install_sha: str, repo: str, skill_name: str) -> str:
    when = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return (
        "\n\n"
        f"<!-- {TRAILER_MARKER}\n"
        f"installed-by: skillz\n"
        f"install-date: {when}\n"
        f"git-hash: {install_sha}\n"
        f"source: https://github.com/{repo}\n"
        f"skill: {skill_name}\n"
        "-->\n"
    )


def strip_existing_trailer(text: str) -> str:
    return TRAILER_BLOCK_RE.sub("", text).rstrip() + "\n"


def stage_skill(skill: Skill, repo: str, install_sha: str, work_root: Path) -> Path:
    staging = work_root / skill.name
    staging.mkdir(parents=True, exist_ok=False)

    for f in skill.files:
        rel = f.repo_path[len(SKILLS_PREFIX) + len(skill.name) + 1 :]
        url = f"https://{RAW_HOST}/{repo}/{install_sha}/{f.repo_path}"
        body = http_get(url)
        out_path = staging / rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(body)
        if f.is_executable:
            cur = out_path.stat().st_mode
            out_path.chmod(cur | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    skill_md = staging / "SKILL.md"
    if skill_md.is_file():
        text = skill_md.read_text(encoding="utf-8")
        text = strip_existing_trailer(text)
        text += build_trailer(install_sha, repo, skill.name)
        skill_md.write_text(text, encoding="utf-8")
    else:
        warn(f"skill {skill.name!r} has no SKILL.md; install trailer will not be added")

    return staging


def atomic_swap(staging: Path, dest: Path) -> None:
    parent = dest.parent
    parent.mkdir(parents=True, exist_ok=True)
    same_fs_staging = parent / f".{dest.name}.skillz-new.{os.getpid()}"
    if same_fs_staging.exists():
        shutil.rmtree(same_fs_staging)
    shutil.move(str(staging), str(same_fs_staging))

    backup: Path | None = None
    if dest.exists():
        backup = parent / f".{dest.name}.skillz-old.{os.getpid()}"
        if backup.exists():
            shutil.rmtree(backup)
        os.rename(dest, backup)
    try:
        os.rename(same_fs_staging, dest)
    except OSError:
        if backup is not None:
            os.rename(backup, dest)
        raise
    if backup is not None:
        shutil.rmtree(backup, ignore_errors=True)


def apply_plan(
    plan: list[PlanEntry],
    repo: str,
    install_sha: str,
    overwrite_conflicts: bool,
    dry_run: bool,
) -> tuple[int, int, int, int, int]:
    installed = updated = up_to_date = skipped_conflict = failed = 0

    work_root = Path(tempfile.mkdtemp(prefix="skillz-stage."))
    try:
        for entry in plan:
            cls = entry.classification
            label = f"{entry.skill.name:<32}"
            if cls == "ours-current":
                ok(f"{label} up-to-date")
                up_to_date += 1
                continue
            if cls == "conflict" and not overwrite_conflicts:
                warn(f"{label} skipped (conflict)")
                skipped_conflict += 1
                continue

            verb = {
                "new": "install",
                "ours-stale": "update",
                "conflict": "overwrite",
            }[cls]

            if dry_run:
                ok(f"{label} would {verb} ({len(entry.skill.files)} file(s)) -> {entry.dest}")
                if cls == "new":
                    installed += 1
                elif cls == "ours-stale":
                    updated += 1
                else:
                    installed += 1
                continue

            try:
                staging = stage_skill(entry.skill, repo, install_sha, work_root)
                atomic_swap(staging, entry.dest)
            except Exception as exc:
                fail(f"{label} {verb} FAILED: {exc}")
                failed += 1
                continue

            ok(f"{label} {verb}d -> {entry.dest}")
            if cls == "new":
                installed += 1
            elif cls == "ours-stale":
                updated += 1
            else:
                installed += 1
    finally:
        shutil.rmtree(work_root, ignore_errors=True)

    return installed, updated, up_to_date, skipped_conflict, failed


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="skillz-install",
        description="Install skillz agent skills from GitHub.",
    )
    p.add_argument("--ref", default=None, metavar="REF", help="full git ref; defaults from env / refs/heads/main")
    p.add_argument(
        "--branch",
        default=None,
        metavar="BRANCH",
        help="branch shorthand → refs/heads/<branch> (overrides --ref when both are set)",
    )
    p.add_argument("--repo", default=DEFAULT_REPO, help=f"owner/repo on GitHub (default: {DEFAULT_REPO})")
    p.add_argument(
        "--target",
        choices=("repo", "user"),
        default=None,
        help="install location; defaults to user (prompts when run interactively in a git repo)",
    )
    p.add_argument("--yes", action="store_true", help="accept default prompts; does NOT auto-overwrite conflicts")
    p.add_argument("--overwrite-conflicts", action="store_true", help="overwrite skills that lack the skillz trailer")
    p.add_argument("--dry-run", action="store_true", help="show the plan but do not download or write")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    install_ref = resolve_install_ref(args.ref, args.branch)

    info(f"skillz installer (repo={args.repo}, ref={install_ref})")

    try:
        install_sha, tree_sha = resolve_install_sha(args.repo, install_ref)
        skills = enumerate_skills(args.repo, tree_sha)
    except RuntimeError as exc:
        fail(str(exc))
        return 2

    target_dir = choose_target(args)
    ok(f"target: {target_dir}")

    plan = classify(skills, target_dir, install_sha)
    print()
    info("plan:")
    for p in plan:
        print(f"  - {p.skill.name:<32} {p.classification}")
    print()

    overwrite = maybe_resolve_conflicts(plan, args)

    installed, updated, up_to_date, skipped_conflict, failed = apply_plan(
        plan,
        args.repo,
        install_sha,
        overwrite_conflicts=overwrite,
        dry_run=args.dry_run,
    )

    print()
    summary = f"Installed: {installed}   Updated: {updated}   Skipped (up-to-date): {up_to_date}   Skipped (conflict): {skipped_conflict}"
    if failed:
        summary += f"   Failed: {failed}"
    if args.dry_run:
        summary = "[DRY-RUN] " + summary
    ok(summary)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
