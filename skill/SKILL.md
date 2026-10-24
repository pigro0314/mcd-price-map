---
name: 麦价地图
description: 用麦当劳官方 MCP 采集指定城市/商圈的门店菜单，按商品编码做同款比价，输出"城市篮子、同城价差、门店溢价、菜单宽度"四项结论与单文件 HTML 报告。当用户问"附近麦当劳哪家便宜""同城麦当劳价格差多少""帮我拉一下麦当劳菜单价格""做个麦当劳比价报告"时使用。
---

# 麦价地图

把麦当劳 MCP 当测量仪器用：只读、只比价、不下单。

## 何时使用

- "附近哪家麦当劳更便宜 / 我该去哪家"
- "同城麦当劳价差有多大"
- "拉一下这几个城市的麦当劳菜单价格"
- "帮我出一份麦当劳比价报告 / 数据"

## 前置

需要环境变量 `MCD_MCP_TOKEN`（<https://open.mcd.cn/mcp> 免费申请）。
未配置时，先告知用户申请地址，**不要**用任何替代数据源编造价格。

## 执行流程

### 1. 采集

```bash
python skill/scripts/collect_batch.py <标签> <每城门店数>
# 或在 collect_batch.py 的 CITIES 里改城市与地标后运行
```

单城市快速采集：

```bash
python skill/scripts/collect.py --city 北京市 --landmark 国贸 --stores 4 \
    --out data/snapshot-beijing.json
```

### 2. 分析

```bash
python skill/scripts/analyze.py --snap data/<snapshot>.json --out data/analysis.json
```

### 3. 出报告

```bash
python skill/scripts/render.py --analysis data/analysis.json --out index.html
```

三步都用 Python 标准库，无需安装依赖。

## 硬规则（违反则结论无效）

1. **同款判定只看商品编码 `code`，不看名称。** 实测「精选麦满分套餐」对应 3 个编码，价格 13.5 / 15.3 / 28.5 元。按名称匹配会得出「同款差 111%」的假结论。
2. **只用到店自取**（`orderType=1, beType=1`）。外送有独立定价与配送费，混入即失去可比性。
3. **过滤 `businessStatus=false` 的门店。** 未营业门店菜单返回空，会把样本拉偏。
4. **不调用 `calculate-price`、不调用任何券接口。** 券是账户维度资产，不同账号结果不同，无法横向比较。
5. **不调用任何写操作**（`create-order` / `cancel-order` / `delivery-create-address`）。
6. **同一份报告只用一个时段的数据。** 麦当劳按时段换菜单，早餐与正餐不能混算。

## 输出格式

先给三行结论，再给文件：

```
已采集：X 城 / Y 店 / Z 个商品编码（快照时间 <collected_at>）
城市篮子：最低 <城> <金额> 元，最高 <城> <金额> 元，极差 <金额> 元
同城同码最大价差：<商品名> <低价> → <高价>（+<幅度>%）
报告：<html 路径>
```

随后按需补充：门店溢价榜、菜单宽度区间、数据局限（时段/渠道/样本量）。

## 已知局限（必须随结论一起说明）

- 单时段快照，价格为采集时点，活动价会变
- 每城默认 4 家门店，属"能说明现象"的样本量
- 套餐组成未逐项核验，组合类价差建议先用 `query-meal-detail` 展开再判读
