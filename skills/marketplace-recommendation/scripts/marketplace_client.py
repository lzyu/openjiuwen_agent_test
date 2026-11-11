"""Read-only adapter for the public search page's backend contract."""
from __future__ import annotations

import asyncio
import html
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

SEARCH_URL = "https://mkpdata.huaweicloud.com/api/marketplace/user/api/mkp-web-guest/global/rest/mkp/v1/mkpsearchengineservice/search"
DELIVERY_MODES = {"镜像": 1, "SaaS": 5, "人工服务": 4, "硬件": 9, "API": 7,
                  "License": 8, "AI资产": 10, "容器": 11, "数据资产": 15, "应用资产": 16}
SORTS = {"relevance": None, "price_asc": "priceAsc", "sales": "salesRankDesc", "rating": "customerRatingDesc"}


class MarketplaceError(RuntimeError):
    """Search is unavailable or the upstream contract has changed."""


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data):
        self.parts.append(data)


def plain_text(value: Any, limit: int = 1200) -> str:
    parser = _PlainText()
    parser.feed(str(value or ""))
    return " ".join(html.unescape("".join(parser.parts)).split())[:limit]


def number(value: Any) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) and result >= 0 else None
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class Product:
    id: str
    name: str
    seller: str
    description: str
    url: str
    delivery: str
    price: float | None
    price_display: str
    trial: bool
    trial_price_display: str
    rating: float | None
    sales: float | None
    tags: list[str]

    @classmethod
    def from_api(cls, item: dict) -> Product | None:
        url = urljoin("https://marketplace.huaweicloud.com", str(item.get("url") or ""))
        parsed = urlparse(url)
        if (not item.get("id") or not item.get("title") or parsed.scheme != "https"
                or parsed.netloc != "marketplace.huaweicloud.com" or not parsed.path.startswith("/contents/")):
            return None
        return cls(
            id=str(item["id"]), name=plain_text(item["title"], 300),
            seller=plain_text(item.get("corporation_name"), 200),
            description=plain_text(item.get("hcontent")), url=url,
            delivery=plain_text(item.get("delivery_code_cn"), 30), price=number(item.get("price")),
            price_display=plain_text(item.get("price_with_unit"), 200),
            trial=str(item.get("is_trial")) == "1",
            trial_price_display=plain_text(item.get("trial_price_with_unit"), 200),
            rating=number(item.get("customer_rating")), sales=number(item.get("sales_count")),
            tags=[plain_text(t, 100) for t in (item.get("tag_names") or []) if isinstance(t, str)],
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SearchResult:
    products: list[Product]
    total: int
    fetched_at: str
    request: dict


class MarketplaceClient:
    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None, timeout: float = 20):
        self.transport = transport
        self.timeout = timeout

    async def search(self, keyword: str, *, delivery: str = "", max_price: float | None = None,
                     trial_only: bool = False, sort: str = "relevance", limit: int = 40,
                     offset: int = 0) -> SearchResult:
        keyword = keyword.strip()
        if not keyword or len(keyword) > 128:
            raise ValueError("搜索关键词须为 1–128 个字符")
        if delivery and delivery not in DELIVERY_MODES:
            raise ValueError(f"未知交付方式：{delivery}")
        if sort not in SORTS or not 1 <= limit <= 100 or offset < 0:
            raise ValueError("无效排序或分页参数")
        if max_price is not None and (number(max_price) is None):
            raise ValueError("最高展示价格必须为有限非负数")
        filters: dict = {}
        if delivery:
            filters["content_mode"] = DELIVERY_MODES[delivery]
        if max_price is not None:
            filters["price_end"] = max_price
        if trial_only:
            filters["is_trial"] = 1
        body = {"flow_id": "101000", "keyword": keyword, "limit": limit, "offset": offset, "filter": filters}
        if SORTS[sort]:
            body["sort"] = SORTS[sort]
        headers = {"x-language": "zh-cn", "Referer": "https://marketplace.huaweicloud.com/search/"}
        async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport, follow_redirects=False) as client:
            for attempt in range(3):
                try:
                    response = await client.post(SEARCH_URL, json=body, headers=headers)
                    if response.status_code == 429 or response.status_code >= 500:
                        if attempt < 2:
                            await asyncio.sleep(0.3 * (2 ** attempt))
                            continue
                    response.raise_for_status()
                    data = response.json()
                    break
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    if attempt == 2:
                        raise MarketplaceError("云商店搜索暂时不可用，请稍后重试") from exc
                except (httpx.HTTPStatusError, ValueError) as exc:
                    raise MarketplaceError("云商店搜索返回异常响应") from exc
        if not isinstance(data, dict) or data.get("error_code") != "00000000":
            raise MarketplaceError("云商店搜索业务错误，未获取到有效商品")
        try:
            total = int(data["total"])
            if total < 0:
                raise ValueError("negative total")
        except (KeyError, TypeError, ValueError) as exc:
            raise MarketplaceError("云商店搜索数据结构变化：total 无效") from exc
        pagination = data.get("pagination")
        # The real API uses pagination:null for a successful zero-hit search.
        if total == 0 and pagination is None:
            pagination = {"items": []}
        if not isinstance(pagination, dict) or not isinstance(pagination.get("items"), list):
            raise MarketplaceError("云商店搜索数据结构变化：缺少 pagination.items")
        products = []
        seen = set()
        for item in pagination["items"]:
            product = Product.from_api(item) if isinstance(item, dict) else None
            if product and product.id not in seen:
                seen.add(product.id)
                products.append(product)
        if pagination["items"] and not products:
            raise MarketplaceError("云商店商品字段变化：无法解析有效商品及详情链接")
        return SearchResult(products, total, datetime.now(timezone.utc).isoformat(), body)
