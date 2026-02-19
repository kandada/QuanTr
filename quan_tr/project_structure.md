# 项目结构映射

> 本文档包含项目的类、方法、函数等代码结构信息

项目路径: `/Users/xiefujin_mac2025/PycharmProjects/QuanTr/quan_tr`

## 多语言项目概览

| 语言 | 文件数 | 总行数 | 代码行 | 注释行 | 空行 |
|------|--------|--------|--------|--------|------|
| json | 5 | 544 | 544 | 0 | 0 |
| markdown | 10 | 2770 | 1822 | 415 | 533 |
| python | 11 | 6858 | 5146 | 462 | 1250 |
| yaml | 1 | 110 | 77 | 17 | 16 |

## Python代码详细分析



项目路径: `/Users/xiefujin_mac2025/PycharmProjects/QuanTr/quan_tr`
分析时间: 2026-02-19 08:16:16
类数量: 12
函数数量: 10
文件数量: 11

## 文件结构概览

- `config.py`
  - 类: 1 个
  - 函数: 0 个
- `programs/analyzers/fundamental_analyzer.py`
  - 类: 1 个
  - 函数: 1 个
- `programs/analyzers/risk_analyzer.py`
  - 类: 1 个
  - 函数: 1 个
- `programs/analyzers/sentiment_analyzer.py`
  - 类: 1 个
  - 函数: 1 个
- `programs/analyzers/technical_analyzer.py`
  - 类: 1 个
  - 函数: 1 个
- `programs/backtesters/strategy_backtester.py`
  - 类: 1 个
  - 函数: 1 个
- `programs/batch_analyzer.py`
  - 类: 1 个
  - 函数: 1 个
- `programs/data_fetchers/akshare_fetcher.py`
  - 类: 1 个
  - 函数: 1 个
- `programs/data_fetchers/yfinance_fetcher.py`
  - 类: 1 个
  - 函数: 1 个
- `programs/stock_analyzer.py`
  - 类: 1 个
  - 函数: 1 个
- `programs/utils/data_processor.py`
  - 类: 2 个
  - 函数: 1 个

## 类定义详情

### 文件: `config.py`

#### 类: `QuanTrConfig`

- **位置**: 第 14 行
- **文档**: QuanTr量化交易系统配置类...
- **方法**:
  - `__init__(self, config_path)`
  - `load_config(self)`
  - `deep_merge(self, base, update)`
  - `save_config(self, config)`
  - `get(self, key, default)`
  - `set(self, key, value)`
  - `get_stocks_pool(self)`
  - `get_data_dir(self, date_str)`
  - `get_analysis_dir(self, date_str)`
  - `get_backtest_dir(self)`
  - `get_programs_dir(self)`
  - `get_resources_dir(self)`
  - `get_templates_dir(self)`
  - `validate_config(self)`
  - `print_summary(self)`

### 文件: `programs/analyzers/fundamental_analyzer.py`

#### 类: `FundamentalAnalyzer`

- **位置**: 第 24 行
- **文档**: 基本面分析器...
- **方法**:
  - `__init__(self)`
  - `_setup_logger(self)`
  - `analyze_financial_metrics(self, financial_data)`
  - `_get_latest_period_data(self, df)`
  - `_analyze_profitability(self, income, balance)`
  - `_analyze_liquidity(self, balance)`
  - `_analyze_solvency(self, balance)`
  - `_analyze_efficiency(self, income, balance)`
  - `_analyze_growth(self, income_statement, balance_sheet)`
  - `_parse_numeric(self, value)`
  - `analyze_company_operations(self, basic_info)`
  - `analyze_industry_trends(self, industry)`
  - `analyze_macroeconomic_factors(self)`
  - `generate_fundamental_score(self, analysis_results)`
  - `_score_financial_metrics(self, financial_metrics)`
  - `_score_company_operations(self, operations_analysis)`
  - `_score_industry_trends(self, industry_analysis)`
  - `_score_macroeconomic_factors(self, macro_analysis)`
  - `_determine_rating(self, score)`
  - `generate_fundamental_report(self, symbol, analysis_results)`

### 文件: `programs/analyzers/risk_analyzer.py`

#### 类: `RiskAnalyzer`

- **位置**: 第 24 行
- **文档**: 风险分析器...
- **方法**:
  - `__init__(self)`
  - `_setup_logger(self)`
  - `analyze_systematic_risk(self, price_data, market_data)`
  - `analyze_unsystematic_risk(self, price_data, financial_data)`
  - `_analyze_financial_risk(self, financial_data)`
  - `analyze_liquidity_risk(self, price_data)`
  - `analyze_tail_risk(self, price_data)`
  - `generate_risk_assessment(self, risk_results)`
  - `analyze_all(self, price_data, market_data, financial_data)`
  - `generate_risk_report(self, symbol, risk_results)`

### 文件: `programs/analyzers/sentiment_analyzer.py`

#### 类: `SentimentAnalyzer`

- **位置**: 第 27 行
- **文档**: 情绪分析器...
- **方法**:
  - `__init__(self)`
  - `_setup_logger(self)`
  - `_load_positive_words(self)`
  - `_load_negative_words(self)`
  - `_load_intensifiers(self)`
  - `_load_negations(self)`
  - `analyze_text(self, text)`
  - `analyze_news(self, news_list)`
  - `analyze_social_media(self, posts)`
  - `analyze_analyst_reports(self, reports)`
  - `calculate_sentiment_score(self, sentiment_results)`
  - `analyze_all(self, news, social_posts, analyst_reports)`
  - `generate_sentiment_report(self, symbol, results)`

### 文件: `programs/analyzers/technical_analyzer.py`

#### 类: `TechnicalAnalyzer`

- **位置**: 第 24 行
- **文档**: 技术面分析器...
- **方法**:
  - `__init__(self)`
  - `_setup_logger(self)`
  - `analyze_trend(self, price_data)`
  - `_calculate_trend_strength(self, price_data)`
  - `analyze_momentum(self, price_data)`
  - `_calculate_rsi(self, prices, period)`
  - `_calculate_macd(self, prices, fast, slow, signal)`
  - `analyze_volatility(self, price_data)`
  - `_calculate_atr(self, price_data, period)`
  - `analyze_volume(self, price_data)`
  - `_calculate_obv(self, price_data)`
  - `analyze_support_resistance(self, price_data)`
  - `generate_technical_score(self, technical_results)`
  - `analyze_all(self, price_data)`
  - `generate_technical_report(self, symbol, technical_results)`

### 文件: `programs/backtesters/strategy_backtester.py`

#### 类: `StrategyBacktester`

- **位置**: 第 25 行
- **文档**: 策略回测器...
- **方法**:
  - `__init__(self, initial_capital)`
  - `_setup_logger(self)`
  - `load_analysis_results(self, start_date, end_date)`
  - `generate_signals(self, analysis_results, strategy_type)`
  - `execute_backtest(self, signals, price_data, rebalance_freq)`
  - `_get_price_on_date(self, price_df, date_str)`
  - `_calculate_performance(self, initial_capital, final_value, trades, daily_values, start_date, end_date)`
  - `generate_backtest_report(self, result)`
  - `run_backtest(self, start_date, end_date, strategy_type, price_data)`
  - `_save_backtest_result(self, result, start_date, end_date)`

### 文件: `programs/batch_analyzer.py`

#### 类: `BatchAnalyzer`

- **位置**: 第 23 行
- **文档**: 批量分析器...
- **方法**:
  - `__init__(self)`
  - `load_stocks_pool(self)`
  - `analyze_all_stocks(self, date_str, symbols)`
  - `_save_summary_results(self, results, date_str)`
  - `_display_summary(self, results)`

### 文件: `programs/data_fetchers/akshare_fetcher.py`

#### 类: `AKshareFetcher`

- **位置**: 第 24 行
- **文档**: AKshare数据获取器...
- **方法**:
  - `__init__(self)`
  - `_setup_logger(self)`
  - `_check_akshare_availability(self)`
  - `get_stock_basic_info(self, symbol)`
  - `get_stock_daily_data(self, symbol, start_date, end_date)`
  - `get_stock_financial_data(self, symbol, report_type)`
  - `save_data_to_file(self, data, symbol, data_type, date_str)`
  - `fetch_all_stock_data(self, symbols, date_str)`

### 文件: `programs/data_fetchers/yfinance_fetcher.py`

#### 类: `YFinanceFetcher`

- **位置**: 第 26 行
- **文档**: Yahoo Finance数据获取器...
- **方法**:
  - `__init__(self)`
  - `_setup_logger(self)`
  - `_check_yfinance_availability(self)`
  - `convert_symbol_to_yahoo(self, symbol)`
  - `get_stock_info(self, symbol)`
  - `get_historical_data(self, symbol, period, interval, start_date, end_date)`
  - `get_financials(self, symbol)`
  - `get_recommendations(self, symbol)`
  - `get_major_holders(self, symbol)`
  - `get_news(self, symbol, max_news)`
  - `save_data_to_file(self, data, symbol, data_type, date_str)`

### 文件: `programs/stock_analyzer.py`

#### 类: `StockAnalyzer`

- **位置**: 第 29 行
- **文档**: 股票分析器主类...
- **方法**:
  - `__init__(self)`
  - `_setup_logger(self)`
  - `analyze_stock(self, symbol, date_str, save_results)`
  - `_compile_analysis_result(self, symbol, date_str, basic_info, price_data, fundamental_analysis, technical_analysis, risk_analysis)`
  - `_determine_recommendation(self, score, risk_analysis)`
  - `_create_empty_result(self, symbol, error_msg)`
  - `_create_empty_fundamental_analysis(self)`
  - `_save_analysis_result(self, symbol, date_str, result)`
  - `_generate_markdown_report(self, symbol, result)`

### 文件: `programs/utils/data_processor.py`

#### 类: `DataProcessor`

- **位置**: 第 23 行
- **文档**: 数据处理器...
- **方法**:
  - @staticmethod `normalize_symbol(symbol)`
  - @staticmethod `clean_price_data(df)`
  - @staticmethod `calculate_returns(prices, periods)`
  - @staticmethod `resample_data(df, freq)`
  - @staticmethod `merge_dataframes(dfs, on, how)`

#### 类: `ReportGenerator`

- **位置**: 第 128 行
- **文档**: 报告生成器...
- **方法**:
  - @staticmethod `generate_summary_report(analysis_results, date_str)`
  - @staticmethod `save_analysis_to_json(analysis_results, output_path)`
  - @staticmethod `save_analysis_to_csv(analysis_results, output_path)`

## 函数定义详情

### 文件: `programs/analyzers/fundamental_analyzer.py`

#### 函数: `main`

- **位置**: 第 789 行
- **参数**: `()`
- **文档**: 主函数，用于测试...

### 文件: `programs/analyzers/risk_analyzer.py`

#### 函数: `main`

- **位置**: 第 750 行
- **参数**: `()`
- **文档**: 主函数，用于测试...

### 文件: `programs/analyzers/sentiment_analyzer.py`

#### 函数: `main`

- **位置**: 第 811 行
- **参数**: `()`
- **文档**: 主函数，用于测试...

### 文件: `programs/analyzers/technical_analyzer.py`

#### 函数: `main`

- **位置**: 第 798 行
- **参数**: `()`
- **文档**: 主函数，用于测试...

### 文件: `programs/backtesters/strategy_backtester.py`

#### 函数: `main`

- **位置**: 第 784 行
- **参数**: `()`
- **文档**: 主函数，用于测试...

### 文件: `programs/batch_analyzer.py`

#### 函数: `main`

- **位置**: 第 218 行
- **参数**: `()`
- **文档**: 主函数...

### 文件: `programs/data_fetchers/akshare_fetcher.py`

#### 函数: `main`

- **位置**: 第 412 行
- **参数**: `()`
- **文档**: 主函数，用于测试...

### 文件: `programs/data_fetchers/yfinance_fetcher.py`

#### 函数: `main`

- **位置**: 第 518 行
- **参数**: `()`
- **文档**: 主函数，用于测试...

### 文件: `programs/stock_analyzer.py`

#### 函数: `main`

- **位置**: 第 488 行
- **参数**: `()`
- **文档**: 主函数，用于测试...

### 文件: `programs/utils/data_processor.py`

#### 函数: `main`

- **位置**: 第 280 行
- **参数**: `()`
- **文档**: 测试函数...

## 导入关系

### `config.py`

- `import os`
- `import json`
- `from pathlib import Path`
- `from typing import Dict`
- `from typing import Any`
- `from typing import Optional`
- `from typing import List`
- `from datetime import datetime`
- `import yaml`
- `import yaml`

### `programs/analyzers/fundamental_analyzer.py`

- `import os`
- `import sys`
- `import json`
- `import logging`
- `from datetime import datetime`
- `from pathlib import Path`
- `from typing import Dict`
- `from typing import List`
- `from typing import Optional`
- `from typing import Any`
- `from typing import Tuple`
- `import pandas as pd`
- `import numpy as np`
- `from quan_tr.config import config`

### `programs/analyzers/risk_analyzer.py`

- `import os`
- `import sys`
- `import json`
- `import logging`
- `import numpy as np`
- `import pandas as pd`
- `from datetime import datetime`
- `from pathlib import Path`
- `from typing import Dict`
- `from typing import List`
- `from typing import Optional`
- `from typing import Any`
- `from typing import Tuple`
- `from quan_tr.config import config`

### `programs/analyzers/sentiment_analyzer.py`

- `import os`
- `import sys`
- `import json`
- `import re`
- `import logging`
- `from datetime import datetime`
- `from pathlib import Path`
- `from typing import Dict`
- `from typing import List`
- `from typing import Optional`
- `from typing import Any`
- `from typing import Tuple`
- `from collections import Counter`
- `import pandas as pd`
- `import numpy as np`
- `from quan_tr.config import config`

### `programs/analyzers/technical_analyzer.py`

- `import os`
- `import sys`
- `import json`
- `import logging`
- `import numpy as np`
- `import pandas as pd`
- `from datetime import datetime`
- `from pathlib import Path`
- `from typing import Dict`
- `from typing import List`
- `from typing import Optional`
- `from typing import Any`
- `from typing import Tuple`
- `from quan_tr.config import config`

### `programs/backtesters/strategy_backtester.py`

- `import os`
- `import sys`
- `import json`
- `import logging`
- `from datetime import datetime`
- `from datetime import timedelta`
- `from pathlib import Path`
- `from typing import Dict`
- `from typing import List`
- `from typing import Optional`
- `from typing import Any`
- `from typing import Tuple`
- `import pandas as pd`
- `import numpy as np`
- `from quan_tr.config import config`

### `programs/batch_analyzer.py`

- `import os`
- `import sys`
- `import json`
- `from datetime import datetime`
- `from pathlib import Path`
- `from typing import Dict`
- `from typing import List`
- `from typing import Optional`
- `from typing import Any`
- `from quan_tr.config import config`
- `from quan_tr.programs.stock_analyzer import StockAnalyzer`
- `from quan_tr.programs.utils.data_processor import ReportGenerator`
- `import argparse`

### `programs/data_fetchers/akshare_fetcher.py`

- `import os`
- `import sys`
- `import json`
- `import time`
- `import logging`
- `from datetime import datetime`
- `from datetime import timedelta`
- `from pathlib import Path`
- `from typing import Dict`
- `from typing import List`
- `from typing import Optional`
- `from typing import Any`
- `from typing import Tuple`
- `import pandas as pd`
- `from quan_tr.config import config`
- `import akshare as ak`
- `import akshare as ak`
- `import akshare as ak`
- `import akshare as ak`

### `programs/data_fetchers/yfinance_fetcher.py`

- `import os`
- `import sys`
- `import json`
- `import time`
- `import logging`
- `from datetime import datetime`
- `from datetime import timedelta`
- `from pathlib import Path`
- `from typing import Dict`
- `from typing import List`
- `from typing import Optional`
- `from typing import Any`
- `from typing import Union`
- `import pandas as pd`
- `import numpy as np`
- `from quan_tr.config import config`
- `import yfinance as yf`
- `import yfinance as yf`
- `import yfinance as yf`
- `import yfinance as yf`
- `import yfinance as yf`
- `import yfinance as yf`
- `import yfinance as yf`

### `programs/stock_analyzer.py`

- `import os`
- `import sys`
- `import json`
- `import logging`
- `from datetime import datetime`
- `from pathlib import Path`
- `from typing import Dict`
- `from typing import List`
- `from typing import Optional`
- `from typing import Any`
- `import pandas as pd`
- `from quan_tr.config import config`
- `from quan_tr.programs.data_fetchers.akshare_fetcher import AKshareFetcher`
- `from quan_tr.programs.analyzers.fundamental_analyzer import FundamentalAnalyzer`
- `from quan_tr.programs.analyzers.technical_analyzer import TechnicalAnalyzer`
- `from quan_tr.programs.analyzers.risk_analyzer import RiskAnalyzer`
- `from quan_tr.programs.utils.data_processor import DataProcessor`
- `from quan_tr.programs.utils.data_processor import ReportGenerator`
- `import traceback`

### `programs/utils/data_processor.py`

- `import os`
- `import sys`
- `import json`
- `import pandas as pd`
- `import numpy as np`
- `from datetime import datetime`
- `from datetime import timedelta`
- `from pathlib import Path`
- `from typing import Dict`
- `from typing import List`
- `from typing import Optional`
- `from typing import Any`
- `from typing import Union`
- `from quan_tr.config import config`
