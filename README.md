# 华为云商店推荐 Agent

基于 [openJiuwen agent-core](https://github.com/openJiuwen-ai/agent-core) 的原生 harness `DeepAgent` 实现，接入 DeepSeek。
推荐工作流封装在 [商品推荐 skill](skills/marketplace-recommendation/SKILL.md)，由 `SkillUseRail` 发现、
`skill_tool` 实际加载，再通过 SDK `LocalFunction` 工具查询华为云商店实时商品。

## 启动

需要 Python 3.11–3.13 和 [uv](https://docs.astral.sh/uv/)。在项目根目录运行：

```bash
uv sync --locked
cp .env.example .env  # 已有 .env 时不要覆盖
# 在 .env 中填写 API_KEY；当前环境已经配置
uv run marketplace-agent chat "给10人销售团队推荐2款SaaS CRM，比较用途和计费单位"
```

默认 `API_BASE=https://api.deepseek.com`、`MODEL_PROVIDER=OpenAI`、`MODEL_NAME=deepseek-flash`。
该名称已通过 DeepSeek `/models` 实测确认；接口配置依据 [DeepSeek 官方文档](https://api-docs.deepseek.com/)。
可以在 `.env` 修改模型、请求超时和迭代次数。`.env` 已忽略提交，本地权限设为 `600`，不在日志或报告中输出密钥。

```bash
# 进入多轮对话；输入 exit 退出
uv run marketplace-agent chat

# 查看 skill 调用和真实商品查询证据
uv run marketplace-agent chat "推荐支持试用的SaaS企业邮箱，展示价500元以内" --trace

# 无需模型密钥：直接验证搜索、筛选和推荐证据
uv run marketplace-agent search 企业邮箱 --delivery SaaS --trial --max-price 500
uv run marketplace-agent search 发票 --delivery API --json
```

`chat` 通过真实模型运行 harness；`search` 是工具层的直接调用，不经过模型。

## 推荐能力

- 将自然语言场景转为核心检索词，支持 SaaS/API/License/镜像等交付方式、试用条件、最高列表价及排序。
- 展示名称、商家、价格及原始单位、试用、适配理由和商品详情链接，支持候选对比和多轮追问。
- 模糊诉求先问业务用途；无匹配如实说明，不用搜索引擎的弱相关兜底商品凑数。
- 价格筛选、交付方式和试用标注在本地再次核验；查询失败返回明确错误，不伪装成“无商品”。
- 只向模型开放 `skill_tool` 和 `recommend_products`。skill 正文成功加载后才允许搜索。
  文件操作边界限制在 skill 目录和被忽略的 `.workspace/`；模型只可通过 skill 工具读取 skill 文件，
  harness 在 `.workspace/` 保存运行文件。

## 实现结构

```text
用户 → openJiuwen DeepAgent / ReAct → skill_tool 加载 SKILL.md
                                  → recommend_products (LocalFunction)
                                  → MarketplaceClient → 云商店搜索 API
                                  → 相关性与条件校验 → 有来源的中文建议
```

| 文件 | 职责 |
| --- | --- |
| `skills/marketplace-recommendation/SKILL.md` | 推荐、追问、比较、无结果与价格口径的业务规则 |
| `skills/marketplace-recommendation/references/search-api.md` | 从前端脚本确认的接口契约与来源 |
| `src/marketplace_agent/agent.py` | 创建 harness、装载 SkillUseRail、注册工具和调用追踪 |
| `src/marketplace_agent/skill_loader.py` | 从源码目录或安装包加载 Skill 自带的 Python 工具 |
| `skills/marketplace-recommendation/scripts/marketplace_client.py` | 异步 HTTP、有限重试、字段与 HTML 归一化、详情链接校验 |
| `skills/marketplace-recommendation/scripts/recommendation.py` | 条件校验、去重、排序、推荐证据与独立命令入口 |
| `skills/marketplace-recommendation/scripts/__init__.py` | 导出工具实现、说明和参数 schema，不依赖宿主或 SDK |
| `scripts/evaluate.py` | 真实模型和真实搜索接口的场景评估，写入可复查报告 |

SDK 固定到 `4836fc2815b897bf022e36d5df22481fb446047d`，依赖固定在 `uv.lock`，避免 develop 分支漂移。
项目不修改上游 SDK。构建 wheel 时会把 skill 一起打包。

推荐逻辑、搜索适配、工具 schema 和依赖声明都位于 Skill 内。复制
`skills/marketplace-recommendation/` 到其他项目并安装其中的 `requirements.txt` 后，即可独立使用：

```bash
python skills/marketplace-recommendation/scripts/recommendation.py 企业邮箱 --delivery SaaS --trial --max-price 500 --json
```

主程序仅负责加载 Skill、模型与 harness 配置、工具注册和交互。

## 测试

```bash
# 离线确定性测试：搜索适配、条件校验、异常处理、实际 harness 和 skill 读取
uv run pytest -q

# 增加真实云商店接口测试，无模型费用
RUN_LIVE=1 uv run pytest -q

# 真实 DeepSeek 多轮上下文测试，会产生模型 API 费用
RUN_LLM=1 uv run pytest tests/test_conversation.py -q

# 真实 DeepSeek + 云商店对话评估，会产生模型 API 费用
uv run python scripts/evaluate.py
```

评估覆盖企业邮箱、SaaS CRM、发票识别 API、WAF、模糊诉求和无匹配商品。
报告保存用户问题、回答、skill 加载记录、查询条件、商品证据和检查结果：
[测试报告](docs/test-report.md)、[完整场景记录](docs/evaluation-results.json)。
自动检查覆盖 skill 成功加载、详情链接来源、硬条件是否保留、无匹配与追问行为；
这些基础检查不等于生产推荐质量评估，仍需按真实业务数据扩充用例。

## 接口及范围

商品 API 来自[云商店搜索页面](https://marketplace.huaweicloud.com/search/?selectedListIndex=0)加载的公开前端脚本，
当前无需登录；它是网页后端接口，尚未确认稳定公开 API 承诺。适配层对业务错误、HTTP 错误和结构变化显式报错。

目前每次核验前 40 个候选；“无匹配”只指这个范围，不代表全站无货。
相关性通过核心词在商品名称、简介或标签中的匹配核验，复杂语义由模型结合证据判断；
关键词可能需要同义词重试，尚未实现全站召回或商品详情规格查询。
展示价可能是每用户、每次或某个规格的起售价，不能保证人数、年限和整套方案的总预算。
私有化部署、SLA、认证与兼容性等未结构化返回的信息需要商家确认。

SDK 当前可能输出缺少可选 `redis` 的 online training 警告，不影响本项目所用 harness、skill 和搜索；
部分 SDK 依赖还会输出弃用提示，基础测试记录中保留这些信息。
