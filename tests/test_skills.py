"""End-to-end tests for skill scripts."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = REPO_ROOT / ".agents/skills/polyglot-scaffold/template"
SCAFFOLD_SCRIPT = REPO_ROOT / ".agents/skills/polyglot-scaffold/scripts/scaffold.py"


def _run(cmd: list[str], *, cwd: Path, timeout: int = 900) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _require_tool(name: str) -> None:
    if shutil.which(name) is None:
        pytest.skip(f"{name} not on PATH")


@pytest.fixture(scope="module")
def template_pnpm_installed() -> None:
    _require_tool("pnpm")
    if not (TEMPLATE_DIR / "node_modules").exists():
        _run(["pnpm", "install"], cwd=TEMPLATE_DIR)


def test_template_make_all(template_pnpm_installed: None) -> None:
    _require_tool("cargo")
    _require_tool("uv")
    _require_tool("make")
    result = _run(["make", "all"], cwd=TEMPLATE_DIR, timeout=900)
    assert result.returncode == 0


# Each checkpoint is one `make` target from the template's `make all` graph,
# run separately so pytest reports incremental progress instead of one long
# hang. `skip_prereqs` lists prerequisite targets already built by an earlier
# checkpoint; passing them via `make -o` reuses that work instead of rebuilding.
MAKE_CHECKPOINTS: list[tuple[str, list[str]]] = [
    ("build-rust", []),
    ("build-python", []),
    ("build-node", []),
    ("lint-rust", []),
    ("lint-python", []),
    ("lint-node", []),
    ("typecheck-python", []),
    ("typecheck-node", []),
    ("test-rust", []),
    ("test-python", ["build-python"]),
    ("test-node", ["build-node"]),
]


@pytest.fixture(scope="module")
def scaffolded_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    _require_tool("cargo")
    _require_tool("uv")
    _require_tool("make")
    _require_tool("pnpm")

    dest = tmp_path_factory.mktemp("scaffold") / "muxon-test"
    _run(
        [sys.executable, str(SCAFFOLD_SCRIPT), "--name", "muxon", "--dest", str(dest)],
        cwd=REPO_ROOT,
    )
    _run(["pnpm", "install"], cwd=dest)
    assert (dest / "src/rust-muxon/src/lib.rs").is_file()
    assert (dest / "src/python-muxon/myplaceholder_project").exists() is False
    assert (dest / "src/python-muxon/muxon/__init__.py").is_file()
    return dest


@pytest.mark.parametrize(
    ("target", "skip_prereqs"),
    MAKE_CHECKPOINTS,
    ids=[target for target, _ in MAKE_CHECKPOINTS],
)
def test_scaffold_make_target(scaffolded_project: Path, target: str, skip_prereqs: list[str]) -> None:
    cmd = ["make"]
    for prereq in skip_prereqs:
        cmd += ["-o", prereq]
    cmd.append(target)
    result = _run(cmd, cwd=scaffolded_project, timeout=900)
    assert result.returncode == 0
