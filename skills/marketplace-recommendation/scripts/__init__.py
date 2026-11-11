"""Portable skill tools and contract; no dependency on the host or openJiuwen."""
from .marketplace_client import DELIVERY_MODES, MarketplaceClient, MarketplaceError, Product, plain_text
from .recommendation import format_recommendations, recommend

TOOL_DESCRIPTION = "实时搜索华为云商店，校验相关性和硬条件，返回有来源的推荐候选。使用前先加载 marketplace-recommendation skill。价格是列表展示价，不是整套预算。"
TOOL_INPUT_PARAMS = {
    "type": "object", "properties": {
        "keyword": {"type": "string", "description": "核心检索词，例如 企业邮箱、CRM、发票、WAF；不要整句自然语言"},
        "delivery": {"type": "string", "enum": ["", *DELIVERY_MODES], "default": ""},
        "max_price": {"type": ["number", "null"], "minimum": 0,
                      "description": "最高列表展示价（元），不能保证多人/全年/整套方案总预算"},
        "trial_only": {"type": "boolean", "default": False},
        "top_k": {"type": "integer", "minimum": 1, "maximum": 5, "default": 3},
        "sort": {"type": "string", "enum": ["relevance", "price_asc", "sales", "rating"], "default": "relevance"},
    }, "required": ["keyword"], "additionalProperties": False,
}
