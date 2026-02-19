# 股票分析JSON模板说明

## 文件说明

本目录包含股票分析结果JSON文件的模板和示例：

### 模板文件
1. **stocks_analysis_template.json** - 完整的JSON结构模板，包含所有可能的字段
2. **stocks_analysis_template_with_comments.json** - 带中文注释的完整模板，便于理解每个字段含义

### 示例文件
3. **stocks_analysis_example.json** - 实际使用示例，展示如何填充数据
4. **stocks_analysis_example_with_comments.json** - 带中文注释的示例，展示实际数据填充

### 使用建议
- **开发阶段**：使用带注释版本理解字段含义
- **生产环境**：使用无注释版本减少文件大小
- **学习参考**：对照带注释版本理解数据结构

## 设计原则

### 1. 结构化设计
- **层次清晰**：从元数据到详细数据，层次分明
- **模块化**：每个分析维度独立成模块
- **可扩展**：预留字段支持未来功能扩展

### 2. 数据完整性
- **必填字段**：基本信息、价格信息、评分系统、投资建议
- **可选字段**：详细分析数据，根据数据可用性填充
- **默认值**：数值字段使用0，字符串字段使用空字符串

### 3. 标准化
- **字段命名**：使用snake_case，保持一致性
- **数据类型**：明确数值、字符串、数组、对象类型
- **单位规范**：价格使用元，百分比使用小数或百分比值

## 核心结构说明

### 1. 元数据部分 (metadata)
```json
{
  "metadata": {
    "analysis_date": "分析日期",
    "generated_at": "生成时间",
    "version": "模板版本",
    "total_stocks_analyzed": "分析股票数量",
    "analysis_type": "分析类型",
    "data_sources": ["数据源列表"]
  }
}
```

### 2. 汇总部分 (summary)
- 市场概况统计
- 行业分布
- 推荐汇总
- 表现摘要

### 3. 股票详情部分 (stocks)
每个股票包含以下核心模块：

#### 3.1 基本信息 (basic_info)
- 股票名称、代码、市场、行业
- 公司全称、上市日期、股票类型

#### 3.2 价格信息 (price_info)
- 当前价格、涨跌幅
- 成交量、市值
- 52周高低位

#### 3.3 基本面分析 (fundamental_analysis)
- 财务指标：营收、利润、毛利率等
- 估值指标：PE、PB、PS等
- 增长指标：复合增长率
- 盈利能力指标

#### 3.4 技术面分析 (technical_analysis)
- 趋势指标：移动平均线
- 动量指标：RSI、MACD
- 波动率指标：布林带
- 成交量指标
- 支撑阻力位

#### 3.5 风险分析 (risk_analysis)
- 系统性风险
- 非系统性风险
- 流动性风险
- 总体风险评估

#### 3.6 情绪分析 (sentiment_analysis)
- 新闻情绪
- 社交媒体情绪
- 分析师情绪

#### 3.7 评分系统 (scoring_system)
- 基本面评分（权重40%）
- 技术面评分（权重30%）
- 风险评分（权重20%）
- 情绪评分（权重10%）
- 综合评分

#### 3.8 投资建议 (investment_recommendation)
- 推荐等级：strong_buy/buy/hold/sell/strong_sell
- 目标价格：保守/基准/乐观
- 仓位建议：建议配置比例
- 进出策略：入场点、止盈止损

#### 3.9 比较分析 (comparative_analysis)
- 行业排名
- 同行比较
- 竞争地位

#### 3.10 关键亮点 (key_highlights)
- SWOT分析：优势、劣势、机会、威胁

#### 3.11 参考资料 (reference_documents)
**官方文档** (official_documents)：
- 年报、季报、中报等财务报告
- 包含URL链接和本地文件路径
- 报告摘要信息

**研究报告** (research_reports)：
- 券商研究报告
- 评级和目标价格
- 研究报告链接

**新闻文章** (news_articles)：
- 相关新闻报道
- 新闻情绪分析
- 新闻来源和日期

**监管文件** (regulatory_filings)：
- 公司公告、披露文件
- 交易所备案文件
- 法律文件

**公司网站** (company_website)：
- 公司官网主页
- 投资者关系页面
- 新闻中心

**本地分析文件** (local_analysis_files)：
- 详细分析报告（Markdown）
- 财务模型文件（Excel）
- 分析图表文件（图片）

#### 3.12 数据源信息 (data_sources)
- 价格数据来源
- 财务数据来源
- 新闻数据来源
- 情绪数据来源
- 额外数据源

#### 3.13 相关文件 (related_files)
- 分析过程中生成的相关文件路径
- 便于追溯和查看详细分析

### 4. 分析部分 (analytics)
- 相关性分析
- 聚类分析
- 异常检测

### 5. 报告元数据 (report_metadata)
- 生成信息
- 分析方法
- 免责声明

## 使用指南

### 1. 文件命名规范
```
stocks_analysis_YYYY-MM-DD.json
```
例如：`stocks_analysis_2025-02-13.json`

### 2. 数据填充规则

#### 必填字段
```json
{
  "metadata": {
    "analysis_date": "必须填写",
    "generated_at": "必须填写",
    "total_stocks_analyzed": "必须填写"
  },
  "stocks": [
    {
      "basic_info": {
        "stock_name": "必须填写",
        "stock_code": "必须填写"
      },
      "price_info": {
        "current_price": "必须填写"
      },
      "scoring_system": {
        "overall_score": "必须填写"
      },
      "investment_recommendation": {
        "recommendation": "必须填写"
      }
    }
  ]
}
```

#### 重要可选字段
- **详细的技术指标**：趋势、动量、波动率等
- **完整的财务数据**：营收、利润、资产负债表等
- **情绪分析数据**：新闻、社交、分析师情绪
- **高级分析结果**：相关性、聚类、异常检测

#### 参考资料字段（强烈建议填写）
```json
"reference_documents": {
  "official_documents": [
    {
      "type": "annual_report",
      "year": "2024",
      "title": "年度报告标题",
      "url": "在线文档链接",
      "local_path": "本地文件路径",
      "summary": "报告摘要"
    }
  ],
  "local_analysis_files": [
    {
      "type": "detailed_analysis",
      "path": "analysis_results/日期/stock_名称_代码_analysis.md",
      "description": "详细分析报告"
    }
  ]
},
"data_sources": {
  "price_data": {
    "source": "数据源名称",
    "url": "数据源链接"
  }
},
"related_files": [
  "analysis_results/日期/stock_名称_代码_analysis.md"
]
```

**参考资料字段的重要性**：
1. **可追溯性**：提供分析依据的来源
2. **可验证性**：便于验证分析结论
3. **完整性**：展示分析的全面性
4. **实用性**：方便后续查阅详细资料

### 3. 数据类型规范

#### 数值类型
- 价格：浮点数，单位元
- 百分比：浮点数（如0.15表示15%）
- 比率：浮点数
- 计数：整数

#### 字符串类型
- 使用中文描述
- 枚举值使用英文小写加下划线
- 日期格式：YYYY-MM-DD
- 时间格式：YYYY-MM-DD HH:MM:SS

#### 枚举值规范
```json
{
  "recommendation": "strong_buy/buy/hold/sell/strong_sell",
  "confidence_level": "high/medium/low",
  "risk_level": "low/medium/high",
  "trend_direction": "up/down/sideways",
  "rsi_status": "overbought/oversold/neutral"
}
```

### 4. 评分系统说明

#### 权重分配
- 基本面：40% - 反映公司长期价值
- 技术面：30% - 反映市场短期走势
- 风险：20% - 反映投资安全性
- 情绪：10% - 反映市场心理

#### 评分标准
- 优秀：≥80分
- 良好：60-79分
- 一般：40-59分
- 较差：20-39分
- 很差：<20分

### 5. 投资建议规范

#### 推荐等级定义
- **strong_buy** (强烈买入)：综合评分≥80，基本面和技术面都优秀
- **buy** (买入)：综合评分60-79，有明确的投资价值
- **hold** (持有)：综合评分40-59，无明显买卖信号
- **sell** (卖出)：综合评分20-39，存在明显问题
- **strong_sell** (强烈卖出)：综合评分<20，存在重大风险

#### 目标价格计算
- 保守目标：基于历史估值下限
- 基准目标：基于合理估值
- 乐观目标：基于历史估值上限
- 上涨空间：(目标价-现价)/现价

## 实际应用示例

### 示例1：完整分析
```json
{
  "stock_name": "贵州茅台",
  "current_price": 1680.5,
  "overall_score": 85.6,
  "recommendation": "strong_buy",
  "target_price": {
    "base_case": 1950,
    "current_price_upside": 16.1
  }
}
```

### 示例2：简化分析（数据有限时）
```json
{
  "stock_name": "某股票",
  "current_price": 10.5,
  "overall_score": 65.2,
  "recommendation": "buy",
  "reasoning": "估值合理，技术面转好"
}
```

## 数据验证

### 1. 完整性检查
- 必填字段是否齐全
- 数据类型是否正确
- 数值范围是否合理

### 2. 一致性检查
- 评分与建议是否匹配
- 数据之间逻辑是否一致
- 时间戳是否正确

### 3. 质量检查
- 数据来源是否可靠
- 分析逻辑是否合理
- 建议是否有依据

## 扩展建议

### 1. 未来可添加的字段
- ESG评分（环境、社会、治理）
- 供应链分析
- 专利和技术分析
- 管理层质量评估

### 2. 高级分析功能
- 机器学习预测
- 自然语言处理情绪分析
- 实时数据流分析
- 多因子模型

## 注意事项

1. **数据质量**：确保数据准确性和时效性
2. **分析客观**：避免主观偏见，基于数据说话
3. **风险提示**：充分提示投资风险
4. **持续更新**：随着市场变化更新分析模型
5. **合规性**：遵守相关法律法规

---

**版本历史**
- v1.0.0 (2025-02-13)：初始版本，定义完整JSON结构
- 未来版本将根据实际使用反馈进行优化

**维护说明**
- 模板结构应保持向后兼容
- 新增字段应作为可选字段
- 重大变更需要版本升级