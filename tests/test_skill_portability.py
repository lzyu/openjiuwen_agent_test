"""The skill can be copied and run without its original Agent application."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

from marketplace_agent.skill_loader import SKILL_DIR


def test_copied_skill_recommends_without_host_or_sdk(tmp_path):
    copied = tmp_path / "copied-skill"
    shutil.copytree(SKILL_DIR, copied, ignore=shutil.ignore_patterns("__pycache__"))
    code = '''
import asyncio, importlib.abc, json, sys
class NoHostImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {"marketplace_agent", "openjiuwen"}:
            raise ImportError("Skill must not import its host or SDK")
sys.meta_path.insert(0, NoHostImports())
sys.path.insert(0, sys.argv[1])
from scripts import MarketplaceClient, recommend
import httpx
item = {"id":"portable", "title":"企业邮箱", "url":"/contents/portable",
        "delivery_code_cn":"SaaS", "price":100, "is_trial":1}
transport = httpx.MockTransport(lambda request: httpx.Response(200, json={
    "error_code":"00000000", "total":1, "pagination":{"items":[item]}}))
result = asyncio.run(recommend(MarketplaceClient(transport=transport), "企业邮箱",
                              delivery="SaaS", max_price=200, trial_only=True))
print(json.dumps(result))
'''
    result = subprocess.run([sys.executable, "-I", "-c", code, str(copied)],
                            cwd=tmp_path, capture_output=True, text=True, check=True)
    recommendation = json.loads(result.stdout)
    assert recommendation["status"] == "ok"
    assert recommendation["products"][0]["id"] == "portable"


def test_copied_skill_has_standalone_command(tmp_path):
    copied = tmp_path / "copied-skill"
    shutil.copytree(SKILL_DIR, copied, ignore=shutil.ignore_patterns("__pycache__"))
    result = subprocess.run([sys.executable, "-E", str(copied / "scripts" / "recommendation.py"), "--help"],
                            cwd=tmp_path, capture_output=True, text=True, check=True)
    assert "--delivery" in result.stdout and "--max-price" in result.stdout
