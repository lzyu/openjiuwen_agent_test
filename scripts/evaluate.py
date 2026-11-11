"""Explicit opt-in evaluation: real DeepSeek + real Marketplace, writes reviewable evidence.

Run from project root: uv run python scripts/evaluate.py
This makes paid model API calls using .env.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import re
import time
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()
from marketplace_agent.runtime import configure_runtime
configure_runtime()
from marketplace_agent.agent import ask, create_agent
from openjiuwen.core.runner import Runner


CASES = [
    {"id": "email", "query": "我们公司20人，找SaaS企业邮箱，必须支持试用，列表展示价500元以内，推荐2款。能保证20人全年总价吗？",
     "delivery": "SaaS", "trial": True, "max_price": 500},
    {"id": "crm", "query": "给10人销售团队推荐2款SaaS CRM客户管理商品，比较用途、价格单位、试用情况。", "delivery": "SaaS"},
    {"id": "invoice", "query": "想通过API识别增值税发票内容，推荐华为云商店的2款商品。", "delivery": "API"},
    {"id": "waf", "query": "公司网站想防SQL注入和XSS攻击，推荐2款WAF相关商品，给出商家和详情链接。"},
    {"id": "clarify", "query": "帮我推荐几个华为云商店商品。", "clarify": True},
    {"id": "no_match", "query": "只找名称或简介含ZXQJ999量子咖啡机的SaaS商品，列表价0元，不能用别的商品替代。", "no_match": True,
     "delivery": "SaaS", "max_price": 0},
]


def validate(case, output, trace):
    errors = []
    results = [e["result"] for e in trace if e["event"] == "recommendation"]
    products = {p["id"]: p for result in results for p in result.get("products", [])}
    known_urls = {p["url"] for p in products.values()}
    emitted_urls = set(re.findall(r"https://marketplace\.huaweicloud\.com/contents/[A-Za-z0-9_-]+", output))
    if not output.strip():
        errors.append("empty answer")
    if not any(e["event"] == "skill_loaded" for e in trace):
        errors.append("skill body was not loaded successfully")
    if emitted_urls - known_urls:
        errors.append("answer contains ungrounded product URLs")
    if case.get("clarify"):
        if results:
            errors.append("vague request searched random products")
        if not any(word in output for word in ["用途", "场景", "业务", "需求"]):
            errors.append("no clarification about intended use")
    elif case.get("no_match"):
        if not results or any(r["status"] != "no_match" for r in results):
            errors.append("did not produce a grounded no-match result")
        if emitted_urls:
            errors.append("no-match answer includes a product")
    else:
        if not any(e["event"] == "script_execution" and e["success"] and "recommendation.py" in e["command"] for e in trace):
            errors.append("Skill script was not executed successfully by native bash")
        if not products or not emitted_urls:
            errors.append("no usable grounded recommendation")
    for result in results:
        filters = result.get("request", {}).get("filter", {})
        if case.get("delivery"):
            if filters.get("content_mode") != {"SaaS": 5, "API": 7}[case["delivery"]]:
                errors.append("delivery constraint was relaxed")
        if case.get("trial") and filters.get("is_trial") != 1:
            errors.append("trial constraint was relaxed")
        if "max_price" in case and filters.get("price_end") != case["max_price"]:
            errors.append("price constraint was relaxed")
    return {"passed": not errors, "errors": errors, "product_count": len(products),
            "grounded_url_count": len(emitted_urls)}


async def main():
    report = {"tested_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
              "model": os.getenv("MODEL_NAME", "deepseek-flash"), "mode": "real LLM + real marketplace", "cases": []}
    path = Path("docs/evaluation-results.json")
    await Runner.start()
    try:
        for case in CASES:
            trace = []
            started = time.monotonic()
            try:
                agent = create_agent(trace=trace)
                result = await ask(agent, case["query"], conversation_id=uuid4().hex)
                output = str(result.get("output", ""))
                checks = validate(case, output, trace)
            except Exception as exc:
                # Do not serialize raw API exceptions, requests or model config.
                output = f"Error: {type(exc).__name__}"
                checks = {"passed": False, "errors": [output]}
            entry = {**case, "elapsed_seconds": round(time.monotonic() - started, 2),
                     "output": output, "checks": checks, "trace": trace}
            report["cases"].append(entry)
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"{case['id']}: {'PASS' if checks['passed'] else 'FAIL'} ({entry['elapsed_seconds']}s)", flush=True)
    finally:
        await Runner.stop()
    failures = sum(not c["checks"]["passed"] for c in report["cases"])
    print(f"Evidence: {path.resolve()}; failures={failures}")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
