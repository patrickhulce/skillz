"""Unit tests for install.py conflict-safety and trailer-specificity logic."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from skillz.install import (
    LEGACY_CONTENT_ID,
    PlanEntry,
    Skill,
    SkillFile,
    apply_plan,
    build_trailer,
    classify,
    enumerate_skills,
    parse_existing_trailer,
)

OUR_REPO = "patrickhulce/skillz"
OTHER_REPO = "corp/other-skillz"
SHA = "a" * 40
OTHER_SHA = "b" * 40
CONTENT_ID = "c" * 40
OTHER_CONTENT_ID = "d" * 40


def _skill(name: str = "my-skill", content_id: str = CONTENT_ID) -> Skill:
    return Skill(
        name=name,
        files=[SkillFile(repo_path=f".agents/skills/{name}/SKILL.md", mode="100644", size=100, sha="e" * 40)],
        content_id=content_id,
    )


def _write_skill_md(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _legacy_trailer(git_sha: str, repo: str, skill_name: str) -> str:
    """A trailer as written before per-skill content IDs existed."""
    return (
        "\n\n<!-- skillz:install-metadata\n"
        "installed-by: skillz\n"
        "install-date: 2026-01-01T00:00:00Z\n"
        f"git-hash: {git_sha}\n"
        f"source: https://github.com/{repo}\n"
        f"skill: {skill_name}\n"
        "-->\n"
    )


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
    trailer = build_trailer(SHA, OTHER_REPO, _skill())
    skill_md.write_text("# Some skill\n" + trailer)
    assert parse_existing_trailer(skill_md, OUR_REPO) is None


def test_parse_trailer_round_trips_content_id(tmp_path: Path) -> None:
    skill_md = tmp_path / "SKILL.md"
    trailer = build_trailer(SHA, OUR_REPO, _skill())
    skill_md.write_text("# Some skill\n" + trailer)
    result = parse_existing_trailer(skill_md, OUR_REPO)
    assert result == CONTENT_ID


def test_parse_trailer_without_skill_hash_is_legacy(tmp_path: Path) -> None:
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("# Some skill\n" + _legacy_trailer(SHA, OUR_REPO, "my-skill"))
    assert parse_existing_trailer(skill_md, OUR_REPO) == LEGACY_CONTENT_ID


def test_parse_trailer_no_source_field(tmp_path: Path) -> None:
    # Trailer block exists but lacks a 'source:' line → treated as foreign
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text(f"# Skill\n\n<!-- skillz:install-metadata\ngit-hash: {SHA}\n-->\n")
    assert parse_existing_trailer(skill_md, OUR_REPO) is None


# ---------------------------------------------------------------------------
# classify
# ---------------------------------------------------------------------------


def test_classify_missing_dir(tmp_path: Path) -> None:
    skill = _skill("brand-new")
    entries = classify([skill], tmp_path, OUR_REPO)
    assert len(entries) == 1
    assert entries[0].classification == "new"


def test_classify_no_trailer_is_conflict(tmp_path: Path) -> None:
    skill = _skill("hand-edited")
    skill_md = tmp_path / "hand-edited" / "SKILL.md"
    _write_skill_md(skill_md, "# Hand-edited skill — no trailer\n")
    entries = classify([skill], tmp_path, OUR_REPO)
    assert entries[0].classification == "conflict"


def test_classify_wrong_repo_is_conflict(tmp_path: Path) -> None:
    skill = _skill("foreign")
    skill_md = tmp_path / "foreign" / "SKILL.md"
    trailer = build_trailer(SHA, OTHER_REPO, _skill("foreign"))
    _write_skill_md(skill_md, "# Foreign skill\n" + trailer)
    entries = classify([skill], tmp_path, OUR_REPO)
    assert entries[0].classification == "conflict"


def test_classify_our_trailer_current(tmp_path: Path) -> None:
    skill = _skill("up-to-date")
    skill_md = tmp_path / "up-to-date" / "SKILL.md"
    trailer = build_trailer(SHA, OUR_REPO, skill)
    _write_skill_md(skill_md, "# Skill\n" + trailer)
    entries = classify([skill], tmp_path, OUR_REPO)
    assert entries[0].classification == "ours-current"


def test_classify_unchanged_skill_current_despite_new_commit(tmp_path: Path) -> None:
    # A commit elsewhere in the repo moves HEAD but leaves this skill alone;
    # the skill must not be re-downloaded.
    skill = _skill("unchanged")
    skill_md = tmp_path / "unchanged" / "SKILL.md"
    _write_skill_md(skill_md, "# Skill\n" + build_trailer(SHA, OUR_REPO, skill))
    entries = classify([_skill("unchanged")], tmp_path, OUR_REPO)
    assert entries[0].classification == "ours-current"


def test_classify_changed_content_is_stale(tmp_path: Path) -> None:
    installed = _skill("stale", content_id=OTHER_CONTENT_ID)
    skill_md = tmp_path / "stale" / "SKILL.md"
    _write_skill_md(skill_md, "# Skill\n" + build_trailer(SHA, OUR_REPO, installed))
    entries = classify([_skill("stale")], tmp_path, OUR_REPO)
    assert entries[0].classification == "ours-stale"
    assert entries[0].existing_hash == OTHER_CONTENT_ID


def test_classify_legacy_trailer_is_stale(tmp_path: Path) -> None:
    skill = _skill("legacy-install")
    skill_md = tmp_path / "legacy-install" / "SKILL.md"
    _write_skill_md(skill_md, "# Skill\n" + _legacy_trailer(SHA, OUR_REPO, "legacy-install"))
    entries = classify([skill], tmp_path, OUR_REPO)
    assert entries[0].classification == "ours-stale"


# ---------------------------------------------------------------------------
# enumerate_skills content IDs
# ---------------------------------------------------------------------------


def _tree_response(entries: list[dict]) -> dict:
    return {"tree": entries, "truncated": False}


def test_enumerate_skills_uses_directory_tree_sha() -> None:
    response = _tree_response(
        [
            {"path": ".agents/skills/ship-it", "type": "tree", "sha": "72a5982" + "0" * 33},
            {"path": ".agents/skills/ship-it/SKILL.md", "type": "blob", "mode": "100644", "size": 10, "sha": "f" * 40},
        ]
    )
    with patch("skillz.install.fetch_tree", return_value=response):
        skills = enumerate_skills(OUR_REPO, "tree-sha")

    assert [s.name for s in skills] == ["ship-it"]
    assert skills[0].content_id == "72a5982" + "0" * 33
    assert skills[0].files[0].sha == "f" * 40


def test_enumerate_skills_falls_back_to_blob_digest() -> None:
    # No directory entry (e.g. a truncated tree) → derive an ID from the blobs.
    blob = {"path": ".agents/skills/ship-it/SKILL.md", "type": "blob", "mode": "100644", "size": 10, "sha": "f" * 40}
    with patch("skillz.install.fetch_tree", return_value=_tree_response([blob])):
        skills = enumerate_skills(OUR_REPO, "tree-sha")
    assert skills[0].content_id.startswith("sha256:")

    changed = dict(blob, sha="9" * 40)
    with patch("skillz.install.fetch_tree", return_value=_tree_response([changed])):
        changed_skills = enumerate_skills(OUR_REPO, "tree-sha")
    assert changed_skills[0].content_id != skills[0].content_id


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
    installed, updated, up_to_date, skipped, failed = apply_plan([entry], OUR_REPO, SHA, overwrite_conflicts=False, dry_run=False)

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

    with patch("skillz.install.stage_skill", side_effect=RuntimeError("mock")) as mock_stage:
        installed, updated, up_to_date, skipped, failed = apply_plan([entry], OUR_REPO, SHA, overwrite_conflicts=True, dry_run=False)

    mock_stage.assert_called_once()
    # stage_skill raised → counted as failed, not skipped
    assert failed == 1
    assert skipped == 0


def test_apply_plan_dry_run_does_not_write(tmp_path: Path) -> None:
    skill = _skill("dry-skill")
    dest = tmp_path / "dry-skill"
    # dest does not exist → "new"
    entry = PlanEntry(skill=skill, classification="new", dest=dest)

    with patch("skillz.install.stage_skill") as mock_stage:
        apply_plan([entry], OUR_REPO, SHA, overwrite_conflicts=False, dry_run=True)

    mock_stage.assert_not_called()
    assert not dest.exists()
