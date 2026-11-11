"""Opt-in real model check of conversational constraint refinement."""
import json
from pathlib import Path
import re
from uuid import uuid4

from dotenv import load_dotenv
import pytest


@pytest.mark.llm
async def test_real_multiturn_preserves_crm_intent_and_refines_filters():
    load_dotenv()
    from marketplace_agent.runtime import configure_runtime
    configure_runtime()
    from marketplace_agent.agent import ask, create_agent
    from openjiuwen.core.runner import Runner
    await Runner.start()
    trace = []
    try:
        agent = create_agent(trace=trace)
        conversation_id = uuid4().hex
        first_query = "推荐2款给销售团队用的SaaS CRM，附上商品链接。"
        first = await ask(agent, first_query, conversation_id=conversation_id)
        boundary = len(trace)
        followup_query = "还是这个用途和交付方式，只保留支持试用、列表展示价200元以内的，推荐1款。"
        followup = await ask(agent, followup_query, conversation_id=conversation_id)
        followup_trace = trace[boundary:]
        evidence = {"mode": "real DeepSeek + real marketplace, same conversation_id",
                    "first_query": first_query, "first_answer": first.get("output"),
                    "followup_query": followup_query, "followup_answer": followup.get("output"),
                    "trace": trace}
        Path("docs/conversation-results.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        assert any(e["event"] == "skill_loaded" for e in followup_trace)
        results = [e["result"] for e in followup_trace if e["event"] == "recommendation"]
        assert results and any(r["products"] for r in results)
        for result in results:
            assert result["request"]["filter"] == {"content_mode": 5, "is_trial": 1, "price_end": 200}
            for product in result["products"]:
                assert "crm" in str(product).lower() or "客户" in str(product)
        urls = set(re.findall(r"https://marketplace\.huaweicloud\.com/contents/[A-Za-z0-9_-]+", followup["output"]))
        known = {p["url"] for r in results for p in r["products"]}
        assert urls and urls <= known
    finally:
        await Runner.stop()
