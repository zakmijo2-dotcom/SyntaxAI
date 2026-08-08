"""Skill loading and parsing for SyntaxAI.

Mobile optimisation: skills are parsed **lazily**. ``extract_skills_from_project``
reads only the YAML front-matter (cheap) and caches the parsed metadata; the
( potentially large) markdown body is loaded via ``load_skill_full`` only when a
skill actually matches the current request. This avoids dragging every skill's
full text into the context window on a small device.
"""

from __future__ import annotations

import os
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# Metadata cache: (file_path, mtime) -> SkillDefinition (content empty)
_METADATA_CACHE: dict[tuple[str, float], "SkillDefinition"] = {}


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


def load_skill_file(skill_path: str) -> Optional[SkillDefinition]:
    """Load only the *metadata* (front-matter) of a skill file.

    The body is not read here; use :func:`load_skill_full` to fetch it.
    """
    try:
        path = Path(skill_path)
        if not path.exists():
            return None

        mtime = path.stat().st_mtime
        cache_key = (str(path), mtime)
        if cache_key in _METADATA_CACHE:
            return _METADATA_CACHE[cache_key]

        with open(path, "r", encoding="utf-8") as f:
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
            content="",  # lazy
            file_path=str(path),
            enabled=frontmatter.get("enabled", True),
        )
        _METADATA_CACHE[cache_key] = skill
        return skill

    except Exception as e:
        print(f"Warning: Failed to load skill from {skill_path}: {e}")
        return None


def load_skill_full(skill: SkillDefinition) -> str:
    """Read and cache the full markdown body of *skill*.

    Returns the body text (or an empty string on failure). Idempotent.
    """
    if skill.is_loaded():
        return skill.content

    path = Path(skill.file_path)
    try:
        if not path.exists():
            return ""
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        _front, body = parse_markdown_frontmatter(content)
        skill.content = body.strip()
        return skill.content
    except Exception as e:
        print(f"Warning: Failed to read skill body {skill.file_path}: {e}")
        return ""


def parse_markdown_frontmatter(content: str) -> tuple[Optional[dict], str]:
    """Parse YAML frontmatter from markdown content."""
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
    """Extract skill *metadata* from the ``.skills/`` directory (fast path)."""
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


def load_skills(path: str = None) -> list[SkillDefinition]:
    """Alias for :func:`extract_skills_from_project`."""
    return extract_skills_from_project(path)


def find_matching_skills(
    query: str, skills: list[SkillDefinition]
) -> list[SkillDefinition]:
    """Find skills matching *query* by trigger / name / description."""
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


def skill_matches_trigger(
    trigger: str, skills: list[SkillDefinition]
) -> list[SkillDefinition]:
    return [
        s for s in skills
        if trigger.lower() in s.name.lower()
        or any(t.lower() == trigger.lower() for t in s.triggers)
    ]


def get_skill_by_name(
    name: str, skills: list[SkillDefinition]
) -> Optional[SkillDefinition]:
    for skill in skills:
        if skill.name.lower() == name.lower():
            return skill
    return None


def list_all_skills(skills_dir: str = None) -> list[str]:
    if skills_dir is None:
        skills_dir = os.environ.get(
            "SYNTAXAI_SKILLS_DIR", str(Path.home() / ".syntaxai" / "skills")
        )

    skills_path = Path(skills_dir)
    if not skills_path.exists():
        return []

    out: list[str] = []
    for item in sorted(skills_path.iterdir()):
        if item.is_dir() and (item / "SKILL.md").exists():
            skill_md = item / "SKILL.md"
            try:
                with open(skill_md) as f:
                    content = f.read()
                frontmatter, _ = parse_markdown_frontmatter(content)
                if frontmatter:
                    name = frontmatter.get("name", item.name)
                    status = "✓" if frontmatter.get("enabled", True) else "✗"
                    out.append(f"{status} {name}")
                else:
                    out.append(f"? {item.name}")
            except Exception:
                out.append(f"? {item.name}")

    return out


def inject_skill_context(skill: SkillDefinition) -> str:
    """Format a skill (loading its full body if needed) for the prompt."""
    body = skill.content or load_skill_full(skill)
    return f"""
=== SKILL CONTEXT ===
Name: {skill.name}
Description: {skill.description}

Full skill definition:
{body}
=== END SKILL CONTEXT ===
"""
