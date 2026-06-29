"""Unit tests for install.py conflict-safety and trailer-specificity logic."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.skillz.install import (
    PlanEntry,
    Skill,
    SkillFile,
    apply_plan,
    build_trailer,
    classify,
    parse_existing_trailer,
)

OUR_REPO = "patrickhulce/skillz"
OTHER_REPO = "corp/other-skillz"
SHA = "a" * 40
OTHER_SHA = "b" * 40


def _skill(name: str = "my-skill") -> Skill:
    return Skill(name=name, files=[SkillFile(repo_path=f".agents/skills/{name}/SKILL.md", mode="100644", size=100)])


def _write_skill_md(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# parse_existing_trailer
# ---------------------------------------------------------------------------


def test_parse_trailer_no_block(tmp_path: Path) -> None:
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("# Some skill\n\nNo trailer here.\n")
    assert parse_existing_trailer(skill_md, OUR_REPO) is None


def test_parse_trailer_missing_file(tmp_path: Path) -> None:
    assert parse_existing_trailer(tmp_path / "nonexistent.md", OUR_REPO) is None


def test_parse_trailer_wrong_repo(tmp_path: Path) -> None:
    skill_md = tmp_path / "SKILL.md"
    # Trailer present but source is a different repo
    trailer = build_trailer(SHA, OTHER_REPO, "my-skill")
    skill_md.write_text("# Some skill\n" + trailer)
    assert parse_existing_trailer(skill_md, OUR_REPO) is None


def test_parse_trailer_correct_repo(tmp_path: Path) -> None:
    skill_md = tmp_path / "SKILL.md"
    trailer = build_trailer(SHA, OUR_REPO, "my-skill")
    skill_md.write_text("# Some skill\n" + trailer)
    result = parse_existing_trailer(skill_md, OUR_REPO)
    assert result == SHA


def test_parse_trailer_no_source_field(tmp_path: Path) -> None:
    # Trailer block exists but lacks a 'source:' line → treated as foreign
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text(
        "# Skill\n\n"
        "<!-- skillz:install-metadata\n"
        f"git-hash: {SHA}\n"
        "-->\n"
    )
    assert parse_existing_trailer(skill_md, OUR_REPO) is None


# ---------------------------------------------------------------------------
# classify
# ---------------------------------------------------------------------------


def test_classify_missing_dir(tmp_path: Path) -> None:
    skill = _skill("brand-new")
    entries = classify([skill], tmp_path, SHA, OUR_REPO)
    assert len(entries) == 1
    assert entries[0].classification == "new"


def test_classify_no_trailer_is_conflict(tmp_path: Path) -> None:
    skill = _skill("hand-edited")
    skill_md = tmp_path / "hand-edited" / "SKILL.md"
    _write_skill_md(skill_md, "# Hand-edited skill — no trailer\n")
    entries = classify([skill], tmp_path, SHA, OUR_REPO)
    assert entries[0].classification == "conflict"


def test_classify_wrong_repo_is_conflict(tmp_path: Path) -> None:
    skill = _skill("foreign")
    skill_md = tmp_path / "foreign" / "SKILL.md"
    trailer = build_trailer(SHA, OTHER_REPO, "foreign")
    _write_skill_md(skill_md, "# Foreign skill\n" + trailer)
    entries = classify([skill], tmp_path, SHA, OUR_REPO)
    assert entries[0].classification == "conflict"


def test_classify_our_trailer_current(tmp_path: Path) -> None:
    skill = _skill("up-to-date")
    skill_md = tmp_path / "up-to-date" / "SKILL.md"
    trailer = build_trailer(SHA, OUR_REPO, "up-to-date")
    _write_skill_md(skill_md, "# Skill\n" + trailer)
    entries = classify([skill], tmp_path, SHA, OUR_REPO)
    assert entries[0].classification == "ours-current"


def test_classify_our_trailer_stale(tmp_path: Path) -> None:
    skill = _skill("stale")
    skill_md = tmp_path / "stale" / "SKILL.md"
    trailer = build_trailer(OTHER_SHA, OUR_REPO, "stale")
    _write_skill_md(skill_md, "# Skill\n" + trailer)
    entries = classify([skill], tmp_path, SHA, OUR_REPO)
    assert entries[0].classification == "ours-stale"


# ---------------------------------------------------------------------------
# apply_plan conflict behavior
# ---------------------------------------------------------------------------


def test_apply_plan_skips_conflict_by_default(tmp_path: Path) -> None:
    skill = _skill("protected")
    dest = tmp_path / "protected"
    skill_md = dest / "SKILL.md"
    _write_skill_md(skill_md, "# Protected — do not touch\n")
    original_content = skill_md.read_text()

    entry = PlanEntry(skill=skill, classification="conflict", dest=dest)
    installed, updated, up_to_date, skipped, failed = apply_plan(
        [entry], OUR_REPO, SHA, overwrite_conflicts=False, dry_run=False
    )

    assert skipped == 1
    assert installed == updated == failed == 0
    # File must be completely untouched
    assert skill_md.read_text() == original_content


def test_apply_plan_calls_stage_skill_when_overwrite_forced(tmp_path: Path) -> None:
    skill = _skill("to-overwrite")
    dest = tmp_path / "to-overwrite"
    skill_md = dest / "SKILL.md"
    _write_skill_md(skill_md, "# Old content\n")

    entry = PlanEntry(skill=skill, classification="conflict", dest=dest)

    with patch("src.skillz.install.stage_skill", side_effect=RuntimeError("mock")) as mock_stage:
        installed, updated, up_to_date, skipped, failed = apply_plan(
            [entry], OUR_REPO, SHA, overwrite_conflicts=True, dry_run=False
        )

    mock_stage.assert_called_once()
    # stage_skill raised → counted as failed, not skipped
    assert failed == 1
    assert skipped == 0


def test_apply_plan_dry_run_does_not_write(tmp_path: Path) -> None:
    skill = _skill("dry-skill")
    dest = tmp_path / "dry-skill"
    # dest does not exist → "new"
    entry = PlanEntry(skill=skill, classification="new", dest=dest)

    with patch("src.skillz.install.stage_skill") as mock_stage:
        apply_plan([entry], OUR_REPO, SHA, overwrite_conflicts=False, dry_run=True)

    mock_stage.assert_not_called()
    assert not dest.exists()
