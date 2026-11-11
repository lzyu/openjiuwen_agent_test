from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import subprocess
from uuid import uuid4

from dotenv import load_dotenv

from marketplace_agent.paths import SKILL_SCRIPT


async def run(args):
    from marketplace_agent.runtime import configure_runtime
    configure_runtime()
    from marketplace_agent.agent import ask, create_agent
    from openjiuwen.core.runner import Runner
    await Runner.start()
    try:
        trace = [] if args.trace else None
        agent = create_agent(trace=trace)
        conversation = uuid4().hex
        if args.query:
            result = await ask(agent, args.query, conversation_id=conversation)
            print(result.get("output", result))
        else:
            print("华为云商店推荐助手（输入 exit 退出）")
            while True:
                query = await asyncio.to_thread(input, "你：")
                if query.strip().lower() in {"exit", "quit"}:
                    break
                if query.strip():
                    result = await ask(agent, query, conversation_id=conversation)
                    print(f"助手：{result.get('output', result)}")
        if trace is not None:
            print(json.dumps(trace, ensure_ascii=False, indent=2), file=sys.stderr)
        return 0
    finally:
        await Runner.stop()


def main():
    load_dotenv(Path.cwd() / ".env")
    os.environ.setdefault("IS_SENSITIVE", "true")
    if len(sys.argv) > 1 and sys.argv[1] == "search":
        raise SystemExit(subprocess.run([sys.executable, str(SKILL_SCRIPT), *sys.argv[2:]]).returncode)
    parser = argparse.ArgumentParser(description="openJiuwen 华为云商店推荐助手")
    sub = parser.add_subparsers(dest="command", required=True)
    chat = sub.add_parser("chat", help="使用模型通过 harness 加载 skill，省略 query 进入多轮交互")
    chat.add_argument("query", nargs="?")
    chat.add_argument("--trace", action="store_true", help="输出工具调用及查询证据，不输出密钥")
    sub.add_parser("search", help="直接执行 Skill 脚本；search --help 查看脚本参数")
    args = parser.parse_args()
    try:
        code = asyncio.run(run(args))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        code = 1
    except (KeyboardInterrupt, EOFError):
        code = 0
    except Exception as exc:
        # Never print raw provider request/config objects (may contain credentials).
        print(f"请求失败（{type(exc).__name__}），请检查网络和模型配置。", file=sys.stderr)
        code = 1
    raise SystemExit(code)
