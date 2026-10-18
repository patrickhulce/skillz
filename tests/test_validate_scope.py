"""CLI tests for commit-it/scripts/validate-scope.py."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / ".agents/skills/commit-it/scripts/validate-scope.py"


def _run(cwd: Path, scope: str, files: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(SCRIPT), scope]
    if files:
        cmd.append("--")
        cmd.extend(files)
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


def _assert_ok(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("OK:")


def _assert_err(result: subprocess.CompletedProcess[str], *needles: str) -> None:
    assert result.returncode == 1, result.stdout + result.stderr
    combined = result.stderr
    for needle in needles:
        assert needle in combined, combined


@pytest.mark.parametrize(
    "scope",
    [
        "treewide",
        "treewide!",
        "TREEWIDE",
        "treewide: add workspace metadata",
        "feat(treewide)",
        "infra(treewide)",
        "feat(*)",
        "tests(*)",
        "infra(*)",
        "feat: add login",
        "feat()",
        "feat(): add login",
        "lib/auth: validate token expiration",
        "feat(scripts)",
        "feat(ci)",
        "feat(skills)",
        "feat(skills/commit-it)",
        "feat(frontend)",
        "feat(src)",
        "feat(src/skillz)",
        "feat(hooks)",
        "feat(packages)",
        "feat(packages/foo)",
        "feat(apps)",
        "feat(apps/foo)",
        "feat(components)",
        "feat(lib)",
        "feat(feature)",
        "feat(feature/commit-it)",
        "feature(commit-it): add it",
        "feat(unknown/prefix)",
        "docs(skills/commit-it)",
        "infra(skills/missing)",
        "infra(eslint/semicolons)",
        "refactor(skills/commit-it)!",
    ],
)
def test_rejects_banned_and_unknown(tmp_path: Path, scope: str) -> None:
    _assert_err(_run(tmp_path, scope))


def test_treewide_message_mentions_ban(tmp_path: Path) -> None:
    result = _run(tmp_path, "feat(treewide)")
    _assert_err(result, "'treewide' is banned")


def test_missing_scope_says_required(tmp_path: Path) -> None:
    result = _run(tmp_path, "feat: add login")
    _assert_err(result, "Scope is required")


@pytest.mark.parametrize(
    "scope",
    [
        "docs(*)",
        "docs(*): update guidance for v1->v2 migrations",
        "infra(ci)",
        "infra(uv)",
        "infra(eslint)",
        "infra(skills)",
        "infra(skills)!",
        "infra(skills): add the foo skill",
    ],
)
def test_accepts_docs_and_infra(tmp_path: Path, scope: str) -> None:
    _assert_ok(_run(tmp_path, scope))


def test_skills_exist_and_missing(tmp_path: Path) -> None:
    _assert_ok(_run(tmp_path, "infra(skills)"))
    skill = tmp_path / ".agents/skills/commit-it"
    skill.mkdir(parents=True)
    _assert_ok(_run(tmp_path, "infra(skills/commit-it)"))
    _assert_ok(_run(tmp_path, "infra(skills/commit-it)!: change format"))
    _assert_err(_run(tmp_path, "infra(skills/missing)"), "does not exist")
    _assert_err(_run(tmp_path, "feat(skills)"), "infra(skills")
    _assert_err(_run(tmp_path, "feat(skills/commit-it)"), "infra(skills")
    _assert_err(_run(tmp_path, "refactor(skills/commit-it)!"), "infra(skills")


def test_packages_and_apps_require_dirs(tmp_path: Path) -> None:
    _assert_err(_run(tmp_path, "feat(python-foo)"), "does not exist")
    _assert_err(_run(tmp_path, "feat(packages/python-foo)"), "not part of the scope")
    _assert_err(_run(tmp_path, "feat(apps/v8r.dev)"), "not part of the scope")
    (tmp_path / "packages/python-foo").mkdir(parents=True)
    (tmp_path / "packages/node-foo").mkdir(parents=True)
    _assert_ok(_run(tmp_path, "feat(python-foo)"))
    _assert_ok(_run(tmp_path, "feat(python-foo/upload)"))
    _assert_ok(_run(tmp_path, "tests(node-foo)"))
    _assert_ok(_run(tmp_path, "docs(python-foo)"))
    _assert_ok(_run(tmp_path, "feat(*-foo)"))
    _assert_err(_run(tmp_path, "feat(*-missing)"), "does not exist")
    _assert_err(_run(tmp_path, "feat(packages/python-foo)"), "not part of the scope")

    (tmp_path / "apps/v8r.dev").mkdir(parents=True)
    _assert_ok(_run(tmp_path, "feat(v8r.dev/frontend)"))
    _assert_err(_run(tmp_path, "feat(missing)"), "does not exist")
    _assert_err(_run(tmp_path, "feat(apps/missing)"), "not part of the scope")


def test_changed_file_matching(tmp_path: Path) -> None:
    login = "src/ui/components/LoginModal.tsx"
    _assert_ok(_run(tmp_path, "feat(components/LoginModal)", files=[login]))
    _assert_err(
        _run(tmp_path, "fix(components/LoginModal)", files=["src/other/unrelated.ts"]),
        "not a folder or filename",
    )
    _assert_ok(_run(tmp_path, "fix(lib/auth)", files=["lib/auth.ts"]))
    _assert_ok(_run(tmp_path, "fix(lib/auth)", files=["src/lib/auth/token.py"]))
    _assert_ok(_run(tmp_path, "feat(api/preferences)", files=["src/api/preferences.py"]))
    _assert_ok(_run(tmp_path, "feat(routes/settings)", files=["app/routes/settings.tsx"]))
    assert not (tmp_path / "components").exists()
    assert not (tmp_path / "lib").exists()


def test_feature_scopes_are_rejected(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "# Demo\n\n- **commit-it** - Organize mixed changes into commits\n",
        encoding="utf-8",
    )
    _assert_err(_run(tmp_path, "feat(feature/commit-it)"), "not a scope")


def test_extra_scopes_from_readme_comment(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "# Demo\n\n<!-- skillz-commit-scopes: foo/<scope>,bar/<*>,baz -->\n",
        encoding="utf-8",
    )
    login = "src/ui/components/LoginModal.tsx"
    _assert_ok(_run(tmp_path, "feat(foo/LoginModal)", files=[login]))
    _assert_ok(_run(tmp_path, "chore(bar/anything)"))
    _assert_ok(_run(tmp_path, "chore(baz)"))
    _assert_err(_run(tmp_path, "feat(foo)"), "requires a suffix")
    _assert_err(_run(tmp_path, "feat(foo/not-in-diff)", files=[login]), "not a folder or filename")
    _assert_err(_run(tmp_path, "chore(bar)"), "requires a suffix")
    _assert_err(_run(tmp_path, "chore(baz/nope)"), "must be used bare")


def test_treewide_banned_even_when_listed_as_extra(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "<!-- skillz-commit-scopes: treewide,foo/<scope> -->\n",
        encoding="utf-8",
    )
    _assert_err(_run(tmp_path, "feat(treewide)"), "'treewide' is banned")
    _assert_ok(_run(tmp_path, "feat(foo/LoginModal)", files=["LoginModal.tsx"]))


def test_unions_multiple_extra_scope_comments(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "<!-- skillz-commit-scopes: foo/<scope> -->\n<!-- skillz-commit-scopes: baz -->\n",
        encoding="utf-8",
    )
    _assert_ok(_run(tmp_path, "feat(foo/widget)", files=["src/widget.py"]))
    _assert_ok(_run(tmp_path, "chore(baz)"))


def test_this_repo_skills_and_surfaces() -> None:
    _assert_ok(_run(REPO_ROOT, "infra(skills)"))
    _assert_ok(_run(REPO_ROOT, "infra(skills/commit-it)"))
    _assert_err(_run(REPO_ROOT, "feat(feature/commit-it)"), "not a scope")
    _assert_ok(_run(REPO_ROOT, "fix(lib/install)", files=["src/skillz/install.py"]))
    _assert_err(_run(REPO_ROOT, "feat(treewide)"), "'treewide' is banned")
