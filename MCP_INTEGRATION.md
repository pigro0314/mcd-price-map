# MCP 集成说明

## 1. 使用的 MCP Server

| 项 | 值 |
|---|---|
| 名称 | `mcd-mcp` |
| 接入地址 | `https://mcp.mcd.cn` |
| 传输协议 | Streamable HTTP |
| 鉴权 | `Authorization: Bearer <token>` |
| 提供方 | 麦当劳中国（GitHub 组织 `M-China`） |
| 实测工具数 | 35 个（`tools/list` 返回，官方文档列为 33 个） |
| Token 申请 | <https://open.mcd.cn/mcp>，手机号登录后在控制台激活，免费 |
| 限流 | 600 次/分钟（官方说明） |

配置示例见 [mcp-config.example.json](mcp-config.example.json)，只使用环境变量占位符。

---

## 2. 实际使用的 Tool

35 个工具中，本项目只编排 **2 个只读工具**。少不是为了省事，是因为这个项目要回答的问题只需要"门店 + 菜单"两件事。

| Tool | 读写 | 调用阶段 | 用途 |
|---|---|---|---|
| `query-nearby-stores` | 读 | COLLECT | 按城市 + 地标取门店列表，拿 `storeCode` 与营业状态 |
| `query-meals` | 读 | COLLECT | 逐店拉当前时段在售商品与价格（`orderType=1, beType=1`） |

### 明确不用的工具及理由

| 不用的工具 | 理由 |
|---|---|
| `calculate-price` | 本项目比较的是**菜单标价**，不是某一张订单的实付价。调核价会把券、起送价、配送费混进来，破坏可比性 |
| `query-store-coupons` / `query-my-coupons` / `available-coupons` | 券是账户维度资产，不同账号结果不同，无法跨城市横向比较。券的差异会另做专题，不混进这份价差表 |
| `query-meal-detail` | 只在需要核验套餐组成时用（见 §5 局限）。全量调用会让 31 家门店的采集量翻 30 倍，收益不匹配 |
| `create-order` / `cancel-order` / `delivery-create-address` | 全部写操作一律不碰。本项目是观察工具，不是下单工具 |
| `mall-*` / `draw-lottery` / `party-*` / `query-promotions` | 积分商城、抽奖、派对预约、企业团餐满减，与比价目标无关；`query-promotions` 另有 `beType=6` 限制 |
| `list-nutrition-foods` | 营养数据与价格无关，且返回 TOON 文本，解析成本高于收益 |

---

## 3. 调用流程

```
START
  │
  ├─ query-nearby-stores {beType:1, searchType:2, city, keyword}
  │      └─ 返回门店列表：storeCode / storeName / distance /
  │         businessStatus / businessStartTime / businessEndTime
  │      └─ 过滤 businessStatus=false（未营业门店菜单为空，会污染样本）
  │      └─ 按 distance 取最近 N 家
  │
  ├─ for each store:
  │     query-meals {storeCode, orderType:1, beType:1}
  │        └─ data.meals 是以「商品编码」为 key 的字典：
  │           {code: {name, currentPrice, originalPrice, discountType?}}
  │
  ├─ [本地] 比价矩阵
  │     code → city → [price...]
  │     ├─ 同款判定：code 严格相等（名称会骗人，见 §5）
  │     ├─ 跨城：逐城中位价 → 篮子合计 / 价差
  │     ├─ 同城：min / max / spread / 百分点幅度
  │     └─ 门店溢价：高于同城中位价的商品占比与累计差额
  │
  └─ [本地] 渲染单文件 HTML 报告
```

**单次全量采集约 40 次调用**（8 城 ×（1 次门店查询 + 4 次菜单）），距 600 次/分钟限流极远。
脚本内置 3 次指数退避重试（2s / 4s），并对 401 直接中止、不重试。

### 实现要点

- MCP 响应可能是 `application/json`，也可能是 `text/event-stream`（SSE），客户端需同时处理
- 工具返回的 `content[0].text` 是「人话 + JSON」的混合文本，需要定位第一个可解析的 JSON 对象，不能整体 `json.loads`
- `query-meals` 返回的是**字典**不是数组，key 就是商品编码。按数组处理会拿到 0 条

---

## 4. 业务价值

对三类人：

1. **普通消费者**：把"连锁品牌应该全国同价"的印象变成可核验的事实，并给出可执行结论——**别为差价换城市，但值得为差价换门店**。
2. **做内容的人**：一条命令复现全部数据，价格、篮子、门店溢价都能重算，不用截图对赌。
3. **开发者**：示范了消费类 MCP 的一种非下单用途——**把接口当测量仪器**，而不是当收银台。35 个工具里只取 2 个只读的，也能产出一份有结论的报告。

对麦当劳：这份数据说明门店维度的促销执行存在可见差异，也说明价格体系在全国范围内高度统一——两件事都是平台方自己不容易从外部视角看到的信息。

---

## 5. 数据口径与局限

| 项 | 处理方式 |
|---|---|
| 渠道 | 仅到店自取（`orderType=1, beType=1`）。外送有独立定价与配送费，混入会破坏可比性 |
| 时段 | 仅单一时段快照（本次为早餐）。麦当劳按时段换菜单，正餐价需另跑一次 |
| 同款判定 | **只看 `code`**。同名不同码视为不同商品 |
| 套餐组成 | 未逐项核验。组合类商品的价差建议先用 `query-meal-detail` 展开再判读 |
| 样本量 | 每城 4 家门店，足以说明现象，不足以下城市级结论 |
| 时效 | 价格为采集时点快照，活动价随时可能变化。仓库内 JSON 带 `collected_at` 时间戳 |
| 个人信息 | 只取门店与菜品公开数据，不读取、不存储任何用户地址、订单、券资产 |

---

## 6. 安全边界

| 项 | 处理方式 |
|---|---|
| Token | 只从环境变量 `MCD_MCP_TOKEN` 读取，不进仓库、不进日志、不进报告 |
| 写操作 | 不使用任何写工具（下单、撤单、建地址） |
| 401 | 提示检查 Token 后中止，不重试 |
| 429 | 指数退避重试，3 次后放弃 |
| 敏感样本 | 快照里只有门店编号、名称、地址与菜品价格，无个人信息 |
