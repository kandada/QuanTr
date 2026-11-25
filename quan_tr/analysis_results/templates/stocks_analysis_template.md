# 股票分析报告模板 (contract v2)

> 机器契约以 `stocks_analysis.schema.json` 为准；字段单位：所有 `*_pct` 为百分数
> （12.5 表示 12.5%），`market_cap_cny` 为人民币绝对值，`scores.*` 为 0–100。
> 缺失数据写 `null`，**不要用 0 冒充缺失**。

## 元数据
- schema_version: 2.0.0
- analysis_date: YYYY-MM-DD
- generated_at: ISO 时间
- total_stocks: N

## 市场概览
- market_sentiment: bullish / neutral / bearish
- risk_level: low / medium / high
- recommendations: { strong_buy: N, buy: N, hold: N, sell: N, strong_sell: N }

## 数据质量
- status: real / partial / simulated / missing
- as_of: 数据截止交易日 YYYY-MM-DD（不得晚于 analysis_date）
- sources: [{ source, is_simulated, retrieved_at }]
- notes: 数据缺口/降级说明

> 若 status != real，禁止给出 buy / strong_buy 结论，且回测需标注样本不足。

---

## 股票: {名称} ({代码})

### 基本信息
- name: 股票名称
- code: 规范化代码（如 000001.SZ）
- market: SH / SZ / BJ / HK / US
- sector: 行业板块

### 价格数据
- current: 当前价格（>0）
- change_pct: 涨跌幅（百分数，可负）
- high / low: 当日高低价
- volume: 成交量
- market_cap_cny: 总市值（人民币，缺失为 null）
- pe / pb: 市盈率 / 市净率（缺失为 null）

### 基本面（缺失为 null）
- revenue_growth_pct / profit_growth_pct: 营收 / 利润增长率(%)
- gross_margin_pct / net_margin_pct: 毛利率 / 净利率(%)
- roe_pct: ROE(%)
- debt_ratio_pct: 资产负债率(%)

### 技术面（缺失为 null）
- trend: up / down / sideways
- ma20 / ma50 / ma200: 均线值
- rsi: RSI(14)，0–100
- macd: MACD 值
- volume_ratio: 量比
- support / resistance: 支撑位 / 阻力位

### 风险分析
- level: low / medium / high
- score: 风险评分(0–100，越高风险越大)
- factors: 风险因素列表

### 情绪分析
- score: 情绪评分(0–100，缺失为 null)
- news: positive / negative / neutral
- buzz: 关注度

### 综合评分（0–100）
- fundamental: 基本面评分（缺失为 null）
- technical: 技术面评分
- risk_safety: 风险安全评分（越高越安全，= 100 - 风险评分）
- sentiment: 情绪评分（缺失为 null）
- overall: 综合评分（对可用维度按权重重新归一）

### 投资建议
- action: strong_buy / buy / hold / sell / strong_sell
- confidence: high / medium / low
- target_price: 目标价（给出时应 > current）
- stop_loss: 止损价（给出时应 < current）
- reason: 推荐理由

### 亮点
- strengths / risks / opportunities: 字符串列表

### 溯源（可选）
- price_source / fundamentals_source: 数据来源
- is_simulated: 是否包含模拟数据
