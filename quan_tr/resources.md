# QuanTr 资源索引文件

## 项目概述
QuanTr是一款基于AI Agent的股票量化分析与策略回测系统，本文件记录了系统所需的各种资源和访问方式。

## 数据源资源

### 1. 财经数据接口

#### AKshare (推荐)
- **类型**: Python开源库
- **网址**: https://github.com/akfamily/akshare
- **特点**: 免费、纯Python、支持多种数据源
- **安装**: `pip install akshare`
- **主要功能**:
  - 股票基本信息
  - 实时行情数据
  - 财务数据
  - 宏观经济数据
  - 行业数据
- **配置说明**: 无需API密钥，直接使用

#### Yahoo Finance (yfinance)
- **类型**: Python库
- **网址**: https://github.com/ranaroussi/yfinance
- **特点**: 国际通用、覆盖全球股市
- **安装**: `pip install yfinance`
- **主要功能**:
  - 历史价格数据（日线/周线/月线）
  - 公司基本信息
  - 分红数据
  - 财务报表
- **配置说明**: 无需API密钥，直接使用

#### 东方财富
- **类型**: 网站数据接口
- **网址**: http://quote.eastmoney.com/
- **特点**: 国内股票数据全面
- **访问方式**: 通过AKshare或直接爬取
- **主要功能**:
  - A股实时行情
  - 财务数据
  - 公司公告
  - 资金流向
- **注意事项**: 注意访问频率限制

#### Ptrade (专业版)
- **类型**: 专业交易接口
- **特点**: 需要券商账户和权限
- **主要功能**:
  - 实时交易数据
  - 账户管理
  - 自动化交易
- **配置说明**: 需要联系券商开通权限

### 2. 知识库资源

#### 本地知识库
- **位置**: `resources/knowledge_base/`
- **内容**:
  - `financial_metrics_explained.md` - 财务指标解释
  - `quantitative_analysis_basics.md` - 量化分析基础
  - 更多文档可自行添加

#### 参考文档
- **位置**: `resources/references/` (可创建)
- **建议内容**:
  - 量化交易策略论文
  - 技术分析教程
  - 风险管理指南

### 3. 模板文件

#### 分析报告模板
- **位置**: `analysis_results/templates/`
- **文件**:
  - `stocks_analysis_template.json` - JSON格式模板
  - `stocks_analysis_template_with_comments.json` - 带注释模板
  - `stocks_analysis_example.json` - 示例文件
  - `stocks_analysis_example_with_comments.json` - 带注释示例
  - `README.md` - 模板说明文档

#### 程序模板
- **位置**: `programs/` (可创建)
- **建议结构**:
  - `data_fetchers/` - 数据获取程序
  - `analyzers/` - 分析程序
  - `backtesters/` - 回测程序
  - `utils/` - 工具函数

## 配置资源

### 配置文件
- **主配置文件**: `config.yaml` - 系统配置和API密钥
- **股票池配置**: `stocks_pool.json` - 要分析的股票列表
- **Python配置**: `config.py` - Python配置模块

### 环境变量
建议在`.env`文件中配置敏感信息:
```bash
# 数据源API密钥（如有）
AKSHARE_API_KEY=your_akshare_key
YFINANCE_API_KEY=your_yfinance_key

# 代理设置（如需）
HTTP_PROXY=http://proxy.example.com:8080
HTTPS_PROXY=http://proxy.example.com:8080

# 日志级别
LOG_LEVEL=INFO
```

## 程序资源

### 预置程序结构（在使用中可进一步优化程序）
系统期望的程序目录结构:
```
programs/
├── data_fetchers/          # 数据获取程序
│   ├── akshare_fetcher.py
│   ├── yfinance_fetcher.py
│   └── eastmoney_fetcher.py
├── analyzers/              # 分析程序
│   ├── fundamental_analyzer.py
│   ├── technical_analyzer.py
│   └── risk_analyzer.py
├── backtesters/            # 回测程序
│   ├── strategy_backtester.py
│   └── performance_evaluator.py
├── utils/                  # 工具函数
│   ├── data_processor.py
│   ├── report_generator.py
│   └── file_manager.py
└── .../                    # 更多
    ├── ...
    └── ...
```

### 程序开发指南
1. **模块化设计**: 每个程序功能单一，易于测试
2. **错误处理**: 完善的异常处理和日志记录
3. **配置化**: 参数通过配置文件管理
4. **可测试性**: 编写单元测试和集成测试

## 外部资源链接

### 学习资源
1. **量化交易学习**:
   - 知乎量化交易专栏
   - 掘金量化社区
   - QuantConnect教程

2. **数据分析工具**:
   - Pandas官方文档
   - NumPy教程
   - Matplotlib示例

3. **金融知识**:
   - 中国证监会官网
   - 上海证券交易所
   - 深圳证券交易所

### 数据源网站
1. **国内数据**:
   - 东方财富网: http://www.eastmoney.com/
   - 同花顺: http://www.10jqka.com.cn/
   - 新浪财经: http://finance.sina.com.cn/

2. **国际数据**:
   - Yahoo Finance: https://finance.yahoo.com/
   - Investing.com: https://www.investing.com/
   - Bloomberg: https://www.bloomberg.com/

3. **宏观经济**:
   - 国家统计局: http://www.stats.gov.cn/
   - 中国人民银行: http://www.pbc.gov.cn/
   - 财政部: http://www.mof.gov.cn/


## 更新记录

- **2026-02-14**: 创建资源索引文件
- **版本**: 1.0.0
- **维护者**: QuanTr AI Agent

---

**提示**: 本文件为资源索引，具体配置和使用方法请参考相关文档和程序注释。
