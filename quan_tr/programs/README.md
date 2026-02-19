# QuanTr 程序开发文档

## 概述

本文档描述了为QuanTr量化交易系统新开发的程序模块。

## 新开发程序列表

### 1. 数据获取模块 (programs/data_fetchers/)

#### AKshare数据获取器 (`akshare_fetcher.py`)
- **功能**: 从AKshare获取A股数据
- **主要方法**:
  - `get_stock_basic_info()` - 获取股票基本信息
  - `get_stock_daily_data()` - 获取日线数据
  - `get_stock_financial_data()` - 获取财务数据
  - `save_data_to_file()` - 保存数据到文件
  - `fetch_all_stock_data()` - 批量获取数据

#### Yahoo Finance数据获取器 (`yfinance_fetcher.py`)
- **功能**: 从Yahoo Finance获取全球股票数据（A股、港股、美股）
- **主要方法**:
  - `get_stock_info()` - 获取股票基本信息（市值、PE、PB等）
  - `get_historical_data()` - 获取历史价格数据
  - `get_financials()` - 获取财务报表
  - `get_recommendations()` - 获取分析师推荐
  - `get_major_holders()` - 获取主要股东信息
  - `get_news()` - 获取相关新闻
  - `convert_symbol_to_yahoo()` - 转换股票代码格式

### 2. 分析模块 (programs/analyzers/)

#### 基本面分析器 (`fundamental_analyzer.py`)
- **功能**: 分析公司基本面
- **分析维度**:
  - 财务指标（盈利能力、流动性、偿债能力、运营效率、成长能力）
  - 公司经营分析
  - 行业趋势分析
  - 宏观经济分析
- **输出**: 综合评分(0-100)和详细报告

#### 技术面分析器 (`technical_analyzer.py`)
- **功能**: 技术指标分析
- **分析维度**:
  - 趋势分析（移动平均线、趋势方向）
  - 动量指标（RSI、MACD）
  - 波动率指标（布林带、ATR）
  - 成交量指标（OBV、量比）
  - 支撑阻力位
- **输出**: 综合评分(0-100)和详细报告

#### 风险分析器 (`risk_analyzer.py`)
- **功能**: 全面风险评估
- **分析维度**:
  - 系统性风险（Beta、市场相关性）
  - 非系统性风险（公司特有风险、财务风险）
  - 流动性风险
  - 尾部风险（VaR、最大回撤）
- **输出**: 风险等级(low/medium/high)和详细报告

#### 情绪分析器 (`sentiment_analyzer.py`)
- **功能**: 分析新闻、社交媒体、分析师报告的情绪
- **支持语言**: 中文和英文
- **分析维度**:
  - 新闻情绪（基于标题和内容）
  - 社交媒体情绪（考虑互动量加权）
  - 分析师报告情绪（基于评级和内容）
- **主要方法**:
  - `analyze_text()` - 分析单条文本
  - `analyze_news()` - 分析新闻列表
  - `analyze_social_media()` - 分析社交媒体帖子
  - `analyze_analyst_reports()` - 分析分析师报告
  - `calculate_sentiment_score()` - 计算综合情绪评分(0-100)
- **输出**: 情绪评分、情绪标签(positive/neutral/negative)、详细报告

### 3. 回测模块 (programs/backtesters/)

#### 策略回测器 (`strategy_backtester.py`)
- **功能**: 对历史分析策略进行回测验证
- **支持策略类型**:
  - `simple` - 简单策略（基于推荐等级）
  - `momentum` - 动量策略（买入高评分股票）
  - `contrarian` - 逆向策略（买入低评分但基本面良好股票）
- **主要功能**:
  - `load_analysis_results()` - 加载历史分析结果
  - `generate_signals()` - 生成交易信号
  - `execute_backtest()` - 执行回测模拟
  - `calculate_performance()` - 计算绩效指标
  - `generate_backtest_report()` - 生成回测报告
- **绩效指标**:
  - 总收益率、年化收益率
  - 胜率、盈亏比
  - 最大回撤
  - 夏普比率
  - 详细交易记录
- **风险控制**:
  - 止损机制
  - 止盈机制
  - 仓位控制
  - 交易成本（佣金、滑点）

### 4. 工具模块 (programs/utils/)

#### 数据处理器 (`data_processor.py`)
- **DataProcessor类**:
  - `normalize_symbol()` - 标准化股票代码
  - `clean_price_data()` - 清洗价格数据
  - `calculate_returns()` - 计算收益率
  - `resample_data()` - 数据重采样
  - `merge_dataframes()` - 合并数据框

- **ReportGenerator类**:
  - `generate_summary_report()` - 生成汇总报告
  - `save_analysis_to_json()` - 保存为JSON
  - `save_analysis_to_csv()` - 保存为CSV

### 5. 主程序 (programs/)

#### 股票分析器 (`stock_analyzer.py`)
- **功能**: 整合所有分析模块，生成完整的股票分析报告
- **工作流程**:
  1. 获取数据（基本信息、价格、财务）
  2. 执行基本面分析
  3. 执行技术面分析
  4. 执行风险分析
  5. 整合结果并生成综合评分
  6. 生成Markdown报告和JSON数据

#### 批量分析器 (`batch_analyzer.py`)
- **功能**: 批量分析股票池中的所有股票
- **工作流程**:
  1. 加载股票池配置
  2. 逐一分析每只股票
  3. 生成汇总统计
  4. 保存汇总报告（JSON、CSV、Markdown）

## 使用说明

### 测试所有程序

```bash
python test_quan_tr.py
```

### 分析单只股票

```bash
python quan_tr/programs/stock_analyzer.py
```

### 批量分析（测试模式）

```bash
python quan_tr/programs/batch_analyzer.py --test
```

### 批量分析（完整模式）

```bash
python quan_tr/programs/batch_analyzer.py
```

### 指定日期分析

```bash
python quan_tr/programs/batch_analyzer.py --date 2026-02-14
```

### 分析指定股票

```bash
python quan_tr/programs/batch_analyzer.py --symbols 000001.SZ 000002.SZ
```

## 输出文件

### 单只股票分析结果
- `analysis_results/YYYY-MM-DD/stock_名称_代码_analysis.md` - Markdown报告
- `analysis_results/YYYY-MM-DD/stock_名称_代码.json` - JSON数据

### 批量分析汇总
- `analysis_results/YYYY-MM-DD/stocks_analysis_YYYY-MM-DD.json` - JSON汇总
- `analysis_results/YYYY-MM-DD/stocks_analysis_YYYY-MM-DD.csv` - CSV汇总
- `analysis_results/YYYY-MM-DD/stocks_analysis_report_YYYY-MM-DD.md` - Markdown报告

## 评分系统

### 综合评分权重
- **基本面分析**: 40% - 反映公司长期价值
- **技术面分析**: 30% - 反映市场短期走势
- **风险分析**: 20% - 反映投资安全性
- **情绪分析**: 10% - 反映市场心理（暂用默认值）

### 推荐等级
- **strong_buy** (≥75分): 强烈买入
- **buy** (60-74分): 买入
- **hold** (40-59分): 持有
- **sell** (25-39分): 卖出
- **strong_sell** (<25分): 强烈卖出

## 技术架构

### 依赖库
- pandas - 数据处理
- numpy - 数值计算
- akshare - A股财经数据接口
- yfinance - Yahoo Finance数据接口（可选，用于港股、美股）

### 日志系统
所有程序都配置了独立的日志记录器，日志文件保存在:
- `quan_tr/logs/*.log`

### 配置管理
使用统一的配置系统 (`quan_tr/config.py`)，支持:
- 默认配置
- 用户自定义配置 (config.yaml)
- 动态配置获取

## 使用示例

### 情绪分析

```python
from quan_tr.programs.analyzers.sentiment_analyzer import SentimentAnalyzer

analyzer = SentimentAnalyzer()

# 分析新闻
news = [
    {"title": "平安银行发布优异年报", "content": "业绩增长强劲"},
    {"title": "市场震荡调整", "content": "短期波动属正常"},
]
result = analyzer.analyze_news(news)
print(f"平均情绪: {result['average_sentiment']}")

# 分析社交媒体
posts = [
    {"content": "这只股票太棒了！", "likes": 100, "comments": 20},
]
result = analyzer.analyze_social_media(posts)
print(f"热度评分: {result['buzz_score']}")
```

### 策略回测

```python
from quan_tr.programs.backtesters.strategy_backtester import StrategyBacktester

backtester = StrategyBacktester(initial_capital=100000)

# 运行回测
result = backtester.run_backtest(
    start_date="2024-01-01",
    end_date="2024-01-31",
    strategy_type="simple"
)

print(f"总收益率: {result['total_return_pct']:.2f}%")
print(f"胜率: {result['win_rate']:.2f}%")
print(f"最大回撤: {result['max_drawdown_pct']:.2f}%")
```

### Yahoo Finance数据获取

```python
from quan_tr.programs.data_fetchers.yfinance_fetcher import YFinanceFetcher

fetcher = YFinanceFetcher()

# 获取股票信息
info = fetcher.get_stock_info("AAPL")
print(f"市值: {info['market_cap']:,}")

# 获取历史数据
hist = fetcher.get_historical_data("AAPL", period="1y")
```

## 注意事项

1. **数据源**: 
   - A股数据：使用AKshare获取
   - 港股、美股数据：使用Yahoo Finance（需要安装`yfinance`库）
2. **网络连接**: 程序需要网络连接获取实时数据
3. **API限制**: 注意控制请求频率，避免被封IP
4. **风险提示**: 所有分析结果仅供参考，不构成投资建议
5. **回测限制**: 回测基于历史数据，不代表未来表现

## 后续开发计划

### 已完成 ✅
- [x] AKshare数据获取器
- [x] Yahoo Finance数据获取器
- [x] 基本面分析器
- [x] 技术面分析器
- [x] 风险分析器
- [x] 情绪分析器
- [x] 策略回测程序
- [x] 数据处理工具
- [x] 股票分析主程序
- [x] 批量分析程序

### 计划中
- [ ] 回测报告自动生成（定期）
- [ ] 实时数据监控
- [ ] 更多技术指标（KDJ、CCI等）
- [ ] 投资组合优化

## 更新记录

### 2026-02-14 - 版本 1.1.0
- ✅ 创建Yahoo Finance数据获取器（支持A股、港股、美股）
- ✅ 创建情绪分析模块（支持新闻、社交媒体、分析师报告）
- ✅ 创建策略回测程序（支持多种策略和风险控制）
- ✅ 完善所有模块测试
- ✅ 更新项目文档

### 2026-02-14 - 版本 1.0.0
- ✅ 创建技术面分析程序
- ✅ 创建风险分析程序
- ✅ 创建数据处理工具
- ✅ 创建报告生成工具
- ✅ 创建股票分析主程序
- ✅ 创建批量分析程序
- ✅ 编写测试脚本
- ✅ 所有测试通过

---

**维护者**: QuanTr AI Agent
**版本**: 1.1.0
