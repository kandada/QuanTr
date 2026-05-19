# 股票分析报告模板

## 元数据
- analysis_date: YYYY-MM-DD
- version: 1.0.0
- total_stocks: N

## 市场概览
- market_sentiment: neutral / bullish / bearish
- risk_level: low / medium / high
- recommendation_summary: { strong_buy: N, buy: N, hold: N, sell: N, strong_sell: N }

---

## 股票: {名称} ({代码})

### 基本信息
- name: 股票名称
- code: 股票代码
- market: A股 / 港股 / 美股
- sector: 行业板块

### 价格数据
- current: 当前价格
- change_pct: 涨跌幅(%)
- high / low: 当日高低价
- volume: 成交量
- market_cap: 总市值
- pe / pb: 市盈率 / 市净率

### 基本面
- revenue_growth: 营收增长率(%)
- profit_growth: 利润增长率(%)
- gross_margin: 毛利率(%)
- net_margin: 净利率(%)
- roe: ROE(%)
- debt_ratio: 资产负债率(%)

### 技术面
- trend: up / down / sideways
- ma20 / ma50 / ma200: 均线值
- rsi: RSI(14)
- macd: MACD值
- volume_ratio: 量比
- support / resistance: 支撑位 / 阻力位

### 风险分析
- level: low / medium / high
- score: 风险评分(0-100)
- factors: 风险因素列表

### 情绪分析
- score: 情绪评分
- news: positive / negative / neutral
- buzz: 关注度

### 综合评分
- fundamental: 基本面评分(0-100, 权重40%)
- technical: 技术面评分(0-100, 权重30%)
- risk: 风险评分(0-100, 权重20%)
- sentiment: 情绪评分(0-100, 权重10%)
- overall: 综合评分(加权计算)

### 投资建议
- action: strong_buy / buy / hold / sell / strong_sell
- confidence: high / medium / low
- target_price: 目标价
- stop_loss: 止损价
- reason: 推荐理由

### 亮点
- strengths: 优势列表
- risks: 风险注意事项
- opportunities: 潜在机会
