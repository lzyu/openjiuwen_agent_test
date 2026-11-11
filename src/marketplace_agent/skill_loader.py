"""Load the self-contained skill package from source or the installed wheel."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


SKILL_NAME = "marketplace-recommendation"
SKILLS_ROOT = Path(__file__).resolve().parents[2] / "skills"
if not (SKILLS_ROOT / SKILL_NAME / "SKILL.md").is_file():
    SKILLS_ROOT = Path(__file__).parent / "bundled_skills"
SKILL_DIR = SKILLS_ROOT / SKILL_NAME


def _load_skill():
    name = "_marketplace_recommendation_skill"
    if name in sys.modules:
        return sys.modules[name]
    entry = SKILL_DIR / "scripts" / "__init__.py"
    spec = spec_from_file_location(name, entry, submodule_search_locations=[str(entry.parent)])
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载商品推荐 skill：{entry}")
    module = module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


skill = _load_skill()
