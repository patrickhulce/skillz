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
        "*",
        "scripts",
        "ci",
        "skills",
        "frontend",
        "src",
        "src/skillz",
        "hooks",
        "packages",
        "apps",
        "components",
        "lib",
        "feature",
        "unknown/prefix",
    ],
)
def test_rejects_banned_and_unknown(tmp_path: Path, scope: str) -> None:
    _assert_err(_run(tmp_path, scope))


def test_treewide_message_mentions_ban(tmp_path: Path) -> None:
    result = _run(tmp_path, "treewide")
    _assert_err(result, "'treewide' is banned")


@pytest.mark.parametrize(
    "scope",
    [
        "docs",
        "docs/migrations",
        "infra/ci",
        "infra/uv",
        "infra/eslint",
        "tests",
        "tests/node-mycool-library",
        "docs: update guidance for v1->v2 migrations",
    ],
)
def test_accepts_label_scopes(tmp_path: Path, scope: str) -> None:
    _assert_ok(_run(tmp_path, scope))


def test_skills_exist_and_missing(tmp_path: Path) -> None:
    skill = tmp_path / ".agents/skills/commit-it"
    skill.mkdir(parents=True)
    _assert_ok(_run(tmp_path, "skills/commit-it"))
    _assert_ok(_run(tmp_path, "skills/commit-it!: change format"))
    _assert_err(_run(tmp_path, "skills/missing"), "does not exist")


def test_packages_and_apps_require_dirs(tmp_path: Path) -> None:
    _assert_err(_run(tmp_path, "packages/python-foo"), "does not exist")
    (tmp_path / "packages/python-foo").mkdir(parents=True)
    (tmp_path / "packages/node-foo").mkdir(parents=True)
    _assert_ok(_run(tmp_path, "packages/python-foo"))
    _assert_ok(_run(tmp_path, "packages/python-foo/upload"))
    _assert_ok(_run(tmp_path, "packages/*-foo"))
    _assert_err(_run(tmp_path, "packages/*-missing"), "does not exist")

    (tmp_path / "apps/v8r.dev").mkdir(parents=True)
    _assert_ok(_run(tmp_path, "apps/v8r.dev/frontend"))
    _assert_err(_run(tmp_path, "apps/missing"), "does not exist")


def test_changed_file_matching(tmp_path: Path) -> None:
    login = "src/ui/components/LoginModal.tsx"
    _assert_ok(_run(tmp_path, "components/LoginModal", files=[login]))
    _assert_err(
        _run(tmp_path, "components/LoginModal", files=["src/other/unrelated.ts"]),
        "not a folder or filename",
    )
    _assert_ok(_run(tmp_path, "lib/auth", files=["lib/auth.ts"]))
    _assert_ok(_run(tmp_path, "lib/auth", files=["src/lib/auth/token.py"]))
    _assert_ok(_run(tmp_path, "api/preferences", files=["src/api/preferences.py"]))
    _assert_ok(_run(tmp_path, "routes/settings", files=["app/routes/settings.tsx"]))
    # Prefixes are not tied to a top-level components/ or lib/ directory.
    assert not (tmp_path / "components").exists()
    assert not (tmp_path / "lib").exists()


def test_feature_readme_matching(tmp_path: Path) -> None:
    _assert_err(_run(tmp_path, "feature/commit-it"), "not listed")
    (tmp_path / "README.md").write_text(
        "# Demo\n\n- **commit-it** - Organize mixed changes into commits\n",
        encoding="utf-8",
    )
    _assert_ok(_run(tmp_path, "feature/commit-it"))

    (tmp_path / "README.md").write_text(
        "# Demo\n\n- **`commit-it`** — Organize mixed changes into commits\n",
        encoding="utf-8",
    )
    _assert_ok(_run(tmp_path, "feature/commit-it"))

    (tmp_path / "README.md").write_text(
        "# Demo\n\n- **ship-it**: push a pull request\n",
        encoding="utf-8",
    )
    _assert_ok(_run(tmp_path, "feature/ship-it"))
    _assert_err(_run(tmp_path, "feature/commit-it"), "not listed")


def test_extra_scopes_from_readme_comment(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "# Demo\n\n<!-- skillz-commit-scopes: foo/<scope>,bar/<*>,baz -->\n",
        encoding="utf-8",
    )
    login = "src/ui/components/LoginModal.tsx"
    _assert_ok(_run(tmp_path, "foo/LoginModal", files=[login]))
    _assert_ok(_run(tmp_path, "bar/anything"))
    _assert_ok(_run(tmp_path, "baz"))
    _assert_err(_run(tmp_path, "foo"), "requires a suffix")
    _assert_err(_run(tmp_path, "foo/not-in-diff", files=[login]), "not a folder or filename")
    _assert_err(_run(tmp_path, "bar"), "requires a suffix")
    _assert_err(_run(tmp_path, "baz/nope"), "must be used bare")


def test_treewide_banned_even_when_listed_as_extra(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "<!-- skillz-commit-scopes: treewide,foo/<scope> -->\n",
        encoding="utf-8",
    )
    _assert_err(_run(tmp_path, "treewide"), "'treewide' is banned")
    _assert_ok(_run(tmp_path, "foo/LoginModal", files=["LoginModal.tsx"]))


def test_unions_multiple_extra_scope_comments(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "<!-- skillz-commit-scopes: foo/<scope> -->\n<!-- skillz-commit-scopes: baz -->\n",
        encoding="utf-8",
    )
    _assert_ok(_run(tmp_path, "foo/widget", files=["src/widget.py"]))
    _assert_ok(_run(tmp_path, "baz"))


def test_this_repo_skills_and_readme_features() -> None:
    _assert_ok(_run(REPO_ROOT, "skills/commit-it"))
    _assert_ok(_run(REPO_ROOT, "feature/commit-it"))
    _assert_ok(_run(REPO_ROOT, "lib/install", files=["src/skillz/install.py"]))
    _assert_err(_run(REPO_ROOT, "treewide"), "'treewide' is banned")
