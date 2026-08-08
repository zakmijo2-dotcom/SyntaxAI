"""Skill loading and parsing for SyntaxAI.

Skills are extended capabilities that can be enabled per-project via .skills/ directory.
They follow a YAML frontmatter + markdown body format.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

_METADATA_CACHE: dict[tuple[str, float], SkillDefinition] = {}


@dataclass
class SkillDefinition:
    name: str
    description: str
    triggers: list[str]
    content: str = ""
    file_path: str = ""
    enabled: bool = True

    def is_loaded(self) -> bool:
        return bool(self.content)


def load_skill_file(skill_path: str) -> SkillDefinition | None:
    try:
        path = Path(skill_path)
        if not path.exists():
            return None

        mtime = path.stat().st_mtime
        cache_key = (str(path), mtime)
        if cache_key in _METADATA_CACHE:
            return _METADATA_CACHE[cache_key]

        with open(path, encoding="utf-8") as f:
            content = f.read()

        frontmatter, _body = parse_markdown_frontmatter(content)
        if not frontmatter:
            return None

        name = frontmatter.get("name", path.parent.name)
        description = frontmatter.get("description", "")
        triggers = frontmatter.get("triggers", [])
        if isinstance(triggers, str):
            triggers = [t.strip() for t in triggers.split(",") if t.strip()]

        skill = SkillDefinition(
            name=name,
            description=description,
            triggers=triggers,
            content="",
            file_path=str(path),
            enabled=frontmatter.get("enabled", True),
        )
        _METADATA_CACHE[cache_key] = skill
        return skill

    except Exception as e:
        print(f"Warning: Failed to load skill from {skill_path}: {e}")
        return None


def load_skill_full(skill: SkillDefinition) -> str:
    if skill.is_loaded():
        return skill.content

    path = Path(skill.file_path)
    try:
        if not path.exists():
            return ""
        with open(path, encoding="utf-8") as f:
            content = f.read()
        _front, body = parse_markdown_frontmatter(content)
        skill.content = body.strip()
        return skill.content
    except Exception as e:
        print(f"Warning: Failed to read skill body {skill.file_path}: {e}")
        return ""


def parse_markdown_frontmatter(content: str) -> tuple[dict | None, str]:
    if not content.startswith("---"):
        return None, content

    middle_idx = content.find("\n---\n", 1)
    if middle_idx == -1:
        return None, content

    frontmatter_str = content[3:middle_idx]
    body = content[middle_idx + 5:]

    try:
        frontmatter = yaml.safe_load(frontmatter_str)
        return frontmatter, body
    except yaml.YAMLError:
        return None, content


def extract_skills_from_project(project_path: str = None) -> list[SkillDefinition]:
    return _extract_skills(project_path)


def _extract_skills(project_path: str = None) -> list[SkillDefinition]:
    skills: list[SkillDefinition] = []

    if project_path is None:
        project_path = os.getcwd()

    project_root = Path(project_path)
    if not project_root.exists():
        return skills

    skills_dir = project_root / ".skills"
    if not skills_dir.exists():
        return skills

    for skill_subdir in sorted(skills_dir.iterdir()):
        if not skill_subdir.is_dir():
            continue
        skill_md = skill_subdir / "SKILL.md"
        if skill_md.exists():
            skill = load_skill_file(str(skill_md))
            if skill:
                skills.append(skill)

    return skills


def find_matching_skills(query: str, skills: list[SkillDefinition]) -> list[SkillDefinition]:
    query_lower = query.lower()
    matching: list[SkillDefinition] = []

    for skill in skills:
        trigger_match = any(t.lower() in query_lower for t in skill.triggers)
        name_match = skill.name.lower() in query_lower
        desc_match = any(
            w in query_lower for w in skill.description.lower().split()
        )
        if trigger_match or name_match:
            matching.insert(0, skill)
        elif desc_match:
            matching.append(skill)

    return matching


def get_skill_by_name(name: str, skills: list[SkillDefinition]) -> SkillDefinition | None:
    for skill in skills:
        if skill.name.lower() == name.lower():
            return skill
    return None


def format_skill_context(skill: SkillDefinition) -> str:
    body = skill.content or load_skill_full(skill)
    return f"""=== SKILL CONTEXT ===
Name: {skill.name}
Description: {skill.description}

{body}
=== END SKILL CONTEXT ===
"""
