"""Tests for lazy skill loading (metadata-only scan + on-demand full body)."""

from __future__ import annotations

import textwrap
from pathlib import Path

from syntaxai.tools.skills_loader import (
    extract_skills_from_project,
    load_skill_full,
    SkillDefinition,
)


def _make_skill(tmp_path: Path, name: str, body: str) -> Path:
    d = tmp_path / ".skills" / name
    d.mkdir(parents=True)
    skill = d / "SKILL.md"
    front = textwrap.dedent(
        f"""\
        ---
        name: {name}
        description: Test skill {name}
        triggers:
          - {name}
        ---

        """
    )
    skill.write_text(front + body)
    return skill


def test_metadata_loaded_without_body(tmp_path: Path):
    big_body = "BODY-" * 5000  # large body
    _make_skill(tmp_path, "demo", big_body)
    skills = extract_skills_from_project(str(tmp_path))
    assert len(skills) == 1
    s = skills[0]
    assert s.name == "demo"
    assert not s.is_loaded()  # content must be empty until requested
    assert s.content == ""


def test_full_body_loaded_on_demand(tmp_path: Path):
    big_body = "UNIQUE_MARKER_" + "x" * 5000
    _make_skill(tmp_path, "demo", big_body)
    skills = extract_skills_from_project(str(tmp_path))
    s = skills[0]
    loaded = load_skill_full(s)
    assert "UNIQUE_MARKER_" in loaded
    assert s.is_loaded()
    # idempotent
    assert load_skill_full(s) == loaded


def test_find_matching_skills(tmp_path: Path):
    _make_skill(tmp_path, "dockerhelper", "desc")
    skills = extract_skills_from_project(str(tmp_path))
    matches = [s for s in skills if s.name == "dockerhelper"]
    from syntaxai.tools.skills_loader import find_matching_skills

    found = find_matching_skills("please use dockerhelper", skills)
    assert any(s.name == "dockerhelper" for s in found)
