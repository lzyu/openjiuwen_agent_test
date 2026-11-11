"""Deterministic grounding, constraints and evidence for the recommendation skill."""
from __future__ import annotations

import re

if __package__:
    from .marketplace_client import DELIVERY_MODES, MarketplaceClient, MarketplaceError
else:
    from marketplace_client import DELIVERY_MODES, MarketplaceClient, MarketplaceError

PRICE_NOTE = "价格是云商店搜索列表展示价，可能按用户、次数、资源或规格计费；不能据此保证整套方案或多人总预算。最终以详情页规格和商家报价为准。"


def terms(keyword: str) -> list[str]:
    # Explicit alternatives are allowed; an unbroken Chinese phrase remains exact.
    return [t.casefold() for t in re.split(r"[\s,，、/|]+", keyword) if t]


async def recommend(client: MarketplaceClient, keyword: str, *, delivery: str = "",
                    max_price: float | None = None, trial_only: bool = False,
                    top_k: int = 3, sort: str = "relevance") -> dict:
    if not 1 <= top_k <= 5:
        raise ValueError("推荐数量须为 1–5")
    try:
        result = await client.search(keyword, delivery=delivery, max_price=max_price,
                                     trial_only=trial_only, sort=sort)
    except MarketplaceError as exc:
        return {"status": "unavailable", "message": str(exc), "products": [], "keyword": keyword}
    matches = []
    query_terms = terms(keyword)
    for index, product in enumerate(result.products):
        text = f"{product.name} {product.description} {' '.join(product.tags)}".casefold()
        hits = [term for term in query_terms if term in text]
        # Search engine also returns suggestions; do not recommend irrelevant suggestions.
        if not hits or (delivery and product.delivery.casefold() != delivery.casefold()):
            continue
        if trial_only and not product.trial:
            continue
        if max_price is not None and (product.price is None or product.price > max_price):
            continue
        evidence = [f"商品名称/简介/标签包含：{'、'.join(hits)}"]
        if delivery:
            evidence.append(f"交付方式为 {product.delivery}")
        if trial_only:
            evidence.append("列表标注支持试用；试用是否免费需查看试用规格")
        if max_price is not None:
            evidence.append(f"列表展示价格 {product.price:g} 元 ≤ {max_price:g} 元（非总价核算）")
        item = product.to_dict()
        item["reasons"] = evidence
        # Preserve upstream relevance unless the user explicitly requests another sort.
        matches.append((index, item))
    if sort == "price_asc":
        matches.sort(key=lambda pair: pair[1]["price"] if pair[1]["price"] is not None else float("inf"))
    elif sort in {"sales", "rating"}:
        field = "sales" if sort == "sales" else "rating"
        matches.sort(key=lambda pair: pair[1][field] or 0, reverse=True)
    return {
        "status": "ok" if matches else "no_match", "keyword": keyword,
        "products": [p for _, p in matches[:top_k]],
        "upstream_total": result.total, "candidates_checked": len(result.products),
        "matches_in_candidates": len(matches), "fetched_at": result.fetched_at,
        "source": "https://marketplace.huaweicloud.com/search/", "request": result.request,
        "price_note": PRICE_NOTE,
        "scope_note": "仅核验当前返回的前 40 个候选；无匹配不代表全站无货。可简化关键词或经用户同意放宽条件。",
    }


def format_recommendations(result: dict) -> str:
    """Grounded plain-text output for the no-LLM search command."""
    if result["status"] == "unavailable":
        return result["message"]
    if not result["products"]:
        return f"当前候选中没有符合“{result['keyword']}”及筛选条件的商品。\n{result['scope_note']}"
    lines = [f"为你找到以下“{result['keyword']}”候选："]
    for index, product in enumerate(result["products"], 1):
        lines.extend([
            f"{index}. {product['name']}｜{product['seller']}",
            f"   {product['delivery']}；列表价：{product['price_display'] or '未标注计费单位，需询价'}；支持试用：{'是' if product['trial'] else '未标注'}",
            f"   推荐依据：{'；'.join(product['reasons'])}", f"   {product['url']}",
        ])
    return "\n".join([*lines, result["price_note"]])


def main():
    """Run directly after copying the skill directory, without the Agent application."""
    import argparse
    import asyncio
    import json

    parser = argparse.ArgumentParser(description="华为云商店推荐 Skill（无需模型密钥）")
    parser.add_argument("keyword")
    parser.add_argument("--delivery", choices=["", *DELIVERY_MODES], default="")
    parser.add_argument("--max-price", type=float)
    parser.add_argument("--trial", action="store_true")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--sort", choices=["relevance", "price_asc", "sales", "rating"], default="relevance")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = asyncio.run(recommend(MarketplaceClient(), args.keyword, delivery=args.delivery,
                                      max_price=args.max_price, trial_only=args.trial,
                                      top_k=args.top_k, sort=args.sort))
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else format_recommendations(result))
    return 1 if result["status"] == "unavailable" else 0


if __name__ == "__main__":
    raise SystemExit(main())
