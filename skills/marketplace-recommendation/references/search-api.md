# 商品搜索接口记录

页面：https://marketplace.huaweicloud.com/search/?selectedListIndex=0

在 2026-11-11 读取页面引用的公开前端脚本：
https://res.hc-cdn.com/cpage-pep-mkp-list-cn/11.10.1/pc/index.js

`getSearchList` 和参数转换函数使用如下请求，无需登录：

```http
POST https://mkpdata.huaweicloud.com/api/marketplace/user/api/mkp-web-guest/global/rest/mkp/v1/mkpsearchengineservice/search
Content-Type: application/json
x-language: zh-cn
Referer: https://marketplace.huaweicloud.com/search/

{"flow_id":"101000","keyword":"企业邮箱","limit":40,"offset":0,"filter":{"content_mode":5,"is_trial":1,"price_end":500}}
```

`sort` 可用 `priceAsc`、`priceDesc`、`salesRankDesc`、`customerRatingDesc` 等。
`content_mode`: 镜像1、人工服务4、SaaS5、API7、License8、硬件9；其余映射见 client.py。

响应成功码为字符串 `00000000`；列表位于 `pagination.items`，总数为 `total`。
成功但无结果时 `total=0` 且 `pagination=null`，应作为有效空列表处理。
字段：id、title、hcontent（HTML 高亮简介）、corporation_name、url（相对详情路径）、
delivery_code_cn、price、price_with_unit（含 HTML 单位）、is_trial、trial_price_with_unit、
customer_rating、sales_count、tag_names。

这是网页使用的公开接口，未发现稳定公开版本承诺；生产应用需确认接口使用条件，保留适配层并监控字段变化。
列表会返回弱相关建议，本项目额外核验词匹配及筛选条件。仅查前40个候选，保留查询时间和来源。
