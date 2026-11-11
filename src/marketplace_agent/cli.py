from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

from dotenv import load_dotenv

from marketplace_agent.client import DELIVERY_MODES, MarketplaceClient, MarketplaceError
from marketplace_agent.recommendation import format_recommendations, recommend


async def run(args):
    if args.command == "search":
        result = await recommend(MarketplaceClient(), args.keyword, delivery=args.delivery,
                                 max_price=args.max_price, trial_only=args.trial,
                                 top_k=args.top_k, sort=args.sort)
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else format_recommendations(result))
        return 1 if result["status"] == "unavailable" else 0
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
    parser = argparse.ArgumentParser(description="openJiuwen 华为云商店推荐助手")
    sub = parser.add_subparsers(dest="command", required=True)
    chat = sub.add_parser("chat", help="使用模型通过 harness 加载 skill，省略 query 进入多轮交互")
    chat.add_argument("query", nargs="?")
    chat.add_argument("--trace", action="store_true", help="输出工具调用及查询证据，不输出密钥")
    search = sub.add_parser("search", help="无需模型的实时搜索与筛选，用于诊断和演示")
    search.add_argument("keyword")
    search.add_argument("--delivery", choices=["", *DELIVERY_MODES], default="")
    search.add_argument("--max-price", type=float)
    search.add_argument("--trial", action="store_true")
    search.add_argument("--top-k", type=int, default=3)
    search.add_argument("--sort", choices=["relevance", "price_asc", "sales", "rating"], default="relevance")
    search.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        code = asyncio.run(run(args))
    except (ValueError, MarketplaceError) as exc:
        print(str(exc), file=sys.stderr)
        code = 1
    except (KeyboardInterrupt, EOFError):
        code = 0
    except Exception as exc:
        # Never print raw provider request/config objects (may contain credentials).
        print(f"请求失败（{type(exc).__name__}），请检查网络和模型配置。", file=sys.stderr)
        code = 1
    raise SystemExit(code)
