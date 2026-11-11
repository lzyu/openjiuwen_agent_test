"""Exercise the real SDK loop and skill filesystem loading, without a paid LLM."""
import json
import shlex
import sys

from marketplace_agent.agent import ask, create_agent
from marketplace_agent.runtime import configure_runtime
from marketplace_agent.paths import SKILL_SCRIPT


async def test_harness_loads_skill_then_executes_script_with_native_bash():
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
                    "bash", {"command": shlex.join([sys.executable, str(SKILL_SCRIPT), "--help"])})
                return AssistantMessage(content="", tool_calls=[ToolCall(id=f"call-{self.calls}", type="function",
                                        name=name, arguments=json.dumps(arguments, ensure_ascii=False))])
            return AssistantMessage(content="已通过原生 bash 执行 Skill 脚本，脚本支持交付方式和最高价筛选。")

    model = ScriptedModel()
    trace = []
    await Runner.start()
    try:
        agent = create_agent(model=model, trace=trace)
        result = await ask(agent, "推荐支持试用的SaaS企业邮箱")
        assert result["result_type"] == "answer"
        assert "原生 bash" in result["output"]
        assert any(e["event"] == "skill_loaded" for e in trace)
        executions = [e for e in trace if e["event"] == "script_execution"]
        assert executions and executions[0]["success"]
        assert str(SKILL_SCRIPT) in executions[0]["command"]
        assert "--delivery" in executions[0]["content"]
        assert "--max-price" in model.messages[2]
        assert "# 华为云商店商品推荐" in model.messages[1]
        tool_names = {c.name for c in agent.ability_manager.list()}
        assert tool_names == {"skill_tool", "read_file", "bash"}
    finally:
        await Runner.stop()
