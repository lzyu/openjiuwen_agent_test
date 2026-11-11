import json

import httpx
import pytest

from marketplace_agent.skill_loader import skill

MarketplaceClient = skill.MarketplaceClient
MarketplaceError = skill.MarketplaceError
Product = skill.Product
plain_text = skill.plain_text
recommend = skill.recommend


def raw_product(**changes):
    item = {"id": "email-1", "title": "企业邮箱A", "hcontent": "<span>企业邮箱</span>协同办公",
            "url": "/contents/email-1", "corporation_name": "测试商家", "delivery_code_cn": "SaaS",
            "price": 180, "price_with_unit": "￥180<span>/年</span>", "is_trial": 1,
            "tag_names": ["办公"], "sales_count": 10, "customer_rating": 5}
    return item | changes


def client_for(items, *, capture=None, total=None):
    def handler(request):
        if capture is not None:
            capture.append(json.loads(request.content))
        return httpx.Response(200, json={"error_code": "00000000", "total": len(items) if total is None else total,
                                        "pagination": {"items": items}})
    return MarketplaceClient(transport=httpx.MockTransport(handler))


async def test_constraints_rechecked_when_upstream_ignores_them():
    items = [raw_product(), raw_product(id="expensive", price=999),
             raw_product(id="service", delivery_code_cn="人工服务"),
             raw_product(id="no-trial", is_trial=0), raw_product(id="unknown-price", price=None),
             raw_product(id="irrelevant", title="财务报表", hcontent="财务系统"), raw_product()]
    captured = []
    result = await recommend(client_for(items, capture=captured), "企业邮箱", delivery="SaaS",
                             trial_only=True, max_price=500)
    assert [p["id"] for p in result["products"]] == ["email-1"]
    assert result["products"][0]["price_display"] == "￥180/年"
    assert "非总价核算" in str(result["products"][0]["reasons"])
    assert captured[0]["filter"] == {"content_mode": 5, "price_end": 500, "is_trial": 1}


async def test_no_match_does_not_recommend_search_fallbacks():
    result = await recommend(client_for([raw_product()], total=2417), "量子咖啡机XYZ")
    assert result["status"] == "no_match"
    assert result["products"] == []
    assert result["upstream_total"] == 2417
    assert "不代表全站无货" in result["scope_note"]


async def test_api_fault_is_explicit_and_never_becomes_empty_success():
    def handler(request):
        return httpx.Response(200, json={"error_code": "BAD"})
    result = await recommend(MarketplaceClient(transport=httpx.MockTransport(handler)), "邮箱")
    assert result["status"] == "unavailable"
    assert result["products"] == []


async def test_real_zero_hit_contract_uses_null_pagination():
    data = {"error_code": "00000000", "total": 0, "pagination": None}
    client = MarketplaceClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=data)))
    result = await recommend(client, "ZXQJ999量子咖啡机", delivery="SaaS", max_price=0)
    assert result["status"] == "no_match"
    assert result["products"] == []
    assert result["request"]["filter"] == {"content_mode": 5, "price_end": 0}


async def test_all_unparseable_products_are_contract_failure():
    client = client_for([{"old_title": "邮箱"}])
    result = await recommend(client, "邮箱")
    assert result["status"] == "unavailable"


@pytest.mark.parametrize("data", [[], {"error_code": "00000000", "total": 1},
                                  {"error_code": "00000000", "total": "bad", "pagination": {"items": []}}])
async def test_contract_changes_are_errors(data):
    client = MarketplaceClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=data)))
    with pytest.raises(MarketplaceError):
        await client.search("邮箱")


async def test_transient_server_failure_is_retried():
    attempts = []
    def handler(request):
        attempts.append(1)
        if len(attempts) == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"error_code": "00000000", "total": 0, "pagination": {"items": []}})
    result = await MarketplaceClient(transport=httpx.MockTransport(handler)).search("邮箱")
    assert result.total == 0 and len(attempts) == 2


@pytest.mark.parametrize("url", ["https://evil.example/contents/a", "//evil.example/contents/a",
                                  "javascript:alert(1)", "/seller/someone"])
def test_reject_untrusted_detail_urls(url):
    assert Product.from_api(raw_product(url=url)) is None


@pytest.mark.parametrize("price", [-1, float("nan"), float("inf")])
async def test_invalid_budget_never_sent(price):
    with pytest.raises(ValueError):
        await client_for([]).search("邮箱", max_price=price)


async def test_free_price_and_sort_do_not_drop_zero():
    result = await recommend(client_for([raw_product(), raw_product(id="free", price=0)]),
                             "企业邮箱", max_price=0, sort="price_asc")
    assert [p["id"] for p in result["products"]] == ["free"]


def test_strip_highlighting_and_decode_entities():
    assert plain_text("￥180<span>/年</span>&amp;试用") == "￥180/年&试用"


@pytest.mark.live
async def test_real_marketplace_email_contract_and_filtering():
    result = await recommend(MarketplaceClient(), "企业邮箱", delivery="SaaS", trial_only=True, max_price=500)
    assert result["status"] == "ok"
    assert all(p["trial"] and p["delivery"] == "SaaS" and p["price"] <= 500 for p in result["products"])
