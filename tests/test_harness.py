"""Exercise the real SDK loop and skill filesystem loading, without a paid LLM."""
import json

from marketplace_agent.agent import ask, create_agent
from marketplace_agent.runtime import configure_runtime
from test_recommendation import client_for, raw_product


async def test_harness_loads_skill_then_calls_business_tool():
    configure_runtime()
    from openjiuwen.core.foundation.llm import ModelClientConfig, ModelRequestConfig
    from openjiuwen.core.foundation.llm.schema.message import AssistantMessage
    from openjiuwen.core.foundation.llm.schema.tool_call import ToolCall
    from openjiuwen.core.runner import Runner

    class ScriptedModel:
        model_client_config = ModelClientConfig(client_provider="OpenAI", api_key="test-only", api_base="https://example.invalid")
        model_config = ModelRequestConfig(model="scripted-test")

        def __init__(self):
            self.calls = 0
            self.messages = []

        async def invoke(self, messages, **kwargs):
            self.messages.append(str(messages))
            self.calls += 1
            if self.calls <= 2:
                name, arguments = ("skill_tool", {"skill_name": "marketplace-recommendation"}) if self.calls == 1 else (
                    "recommend_products", {"keyword": "企业邮箱", "delivery": "SaaS", "trial_only": True})
                return AssistantMessage(content="", tool_calls=[ToolCall(id=f"call-{self.calls}", type="function",
                                        name=name, arguments=json.dumps(arguments, ensure_ascii=False))])
            return AssistantMessage(content="企业邮箱A，列表价180元/年，需核验人数规格。")

    model = ScriptedModel()
    trace = []
    await Runner.start()
    try:
        agent = create_agent(client_for([raw_product()]), model=model, trace=trace)
        result = await ask(agent, "推荐支持试用的SaaS企业邮箱")
        assert result["result_type"] == "answer"
        assert "企业邮箱A" in result["output"]
        assert any(e["event"] == "skill_loaded" for e in trace)
        recommendations = [e["result"] for e in trace if e["event"] == "recommendation"]
        assert recommendations[0]["products"][0]["id"] == "email-1"
        assert "# 华为云商店商品推荐" in model.messages[1]
        tool_names = {c.name for c in agent.ability_manager.list()}
        assert tool_names == {"skill_tool", "recommend_products"}
    finally:
        await Runner.stop()
