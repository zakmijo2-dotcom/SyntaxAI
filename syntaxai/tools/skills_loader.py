"""Skill loading and parsing for SyntaxAI."""

import os
import yaml
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class SkillDefinition:
    name: str
    description: str
    triggers: list[str]
    content: str
    file_path: str
    enabled: bool = True


def load_skill_file(skill_path: str) -> Optional[SkillDefinition]:
    """Load a single skill file from SKILL.md."""
    try:
        path = Path(skill_path)
        if not path.exists():
            return None
        
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        
        frontmatter, body = parse_markdown_frontmatter(content)
        
        if not frontmatter:
            return None
        
        name = frontmatter.get("name", "unnamed")
        description = frontmatter.get("description", "")
        triggers = frontmatter.get("triggers", [])
        
        if isinstance(triggers, str):
            triggers = [t.strip() for t in triggers.split(",")]
        
        full_content = f"---\n{yaml.dump(frontmatter)}\n---\n{body}"
        
        return SkillDefinition(
            name=name,
            description=description,
            triggers=triggers,
            content=full_content,
            file_path=str(path),
            enabled=frontmatter.get("enabled", True)
        )

    except Exception as e:
        print(f"Warning: Failed to load skill from {skill_path}: {e}")
        return None


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
    """Extract skills from .skills/ directory in project root."""
    return _extract_skills(project_path)


def _extract_skills(project_path: str = None) -> list[SkillDefinition]:
    """Internal implementation for extracting skills."""
    skills = []
    
    if project_path is None:
        project_path = os.getcwd()
    
    project_root = Path(project_path)
    
    if not project_root.exists():
        return skills
    
    skills_dir = project_root / ".skills"
    
    if not skills_dir.exists():
        return skills
    
    for skill_subdir in skills_dir.iterdir():
        if not skill_subdir.is_dir():
            continue
        
        skill_md = skill_subdir / "SKILL.md"
        if skill_md.exists():
            skill = load_skill_file(str(skill_md))
            if skill:
                skills.append(skill)
    
    return skills


def load_skills(path: str = None) -> list[SkillDefinition]:
    """Load all skills from .skills/ directory. Alias for extract_skills_from_project."""
    return extract_skills_from_project(path)


def find_matching_skills(query: str, skills: list[SkillDefinition]) -> list[SkillDefinition]:
    """Find skills matching the query based on triggers, name, or content."""
    query_lower = query.lower()
    
    matching = []
    for skill in skills:
        trigger_match = any(t.lower() in query_lower for t in skill.triggers)
        name_match = skill.name.lower() in query_lower
        desc_match = any(w.lower() in query_lower for w in query_lower.split())
        
        if trigger_match or name_match:
            matching.insert(0, skill)
        elif desc_match:
            matching.append(skill)
    
    return matching


def skill_matches_trigger(trigger: str, skills: list[SkillDefinition]) -> list[SkillDefinition]:
    """Get all skills that match a specific trigger."""
    return [s for s in skills if trigger.lower() in s.name.lower() or 
            any(t.lower() == trigger.lower() for t in s.triggers)]


def get_skill_by_name(name: str, skills: list[SkillDefinition]) -> Optional[SkillDefinition]:
    """Get a skill by its exact name (case-insensitive)."""
    for skill in skills:
        if skill.name.lower() == name.lower():
            return skill
    return None


def list_all_skills(skills_dir: str = None) -> list[str]:
    """List all available skills from a skills directory."""
    if skills_dir is None:
        skills_dir = os.environ.get("SYNTAXAI_SKILLS_DIR", str(Path.home() / ".syntaxai" / "skills"))
    
    skills_path = Path(skills_dir)
    if not skills_path.exists():
        return []
    
    skills = []
    for item in skills_path.iterdir():
        if item.is_dir() and (item / "SKILL.md").exists():
            skill_md = item / "SKILL.md"
            try:
                with open(skill_md) as f:
                    content = f.read()
                frontmatter, _ = parse_markdown_frontmatter(content)
                if frontmatter:
                    name = frontmatter.get("name", item.name)
                    status = "✓" if frontmatter.get("enabled", True) else "✗"
                    skills.append(f"{status} {name}")
                else:
                    skills.append(f"? {item.name}")
            except Exception:
                skills.append(f"? {item.name}")
    
    return skills


def inject_skill_context(skill: SkillDefinition) -> str:
    """Format skill for inclusion in prompt context."""
    return f"""
=== SKILL CONTEXT ===
Name: {skill.name}
Description: {skill.description}

Full skill definition:
{skill.content}
=== END SKILL CONTEXT ===
"""