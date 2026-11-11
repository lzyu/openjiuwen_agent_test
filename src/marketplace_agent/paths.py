"""Locate source/wheel Skill resources without importing any Skill code."""
from pathlib import Path

SKILL_NAME = "marketplace-recommendation"
SKILLS_ROOT = Path(__file__).resolve().parents[2] / "skills"
if not (SKILLS_ROOT / SKILL_NAME / "SKILL.md").is_file():
    SKILLS_ROOT = Path(__file__).parent / "bundled_skills"
SKILL_DIR = SKILLS_ROOT / SKILL_NAME
SKILL_SCRIPT = SKILL_DIR / "scripts" / "recommendation.py"
