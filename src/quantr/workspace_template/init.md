# QuanTr 项目指导（init.md）

> 本文件是每次任务注入的系统约束，务必遵守。最后更新：2026-11-24，版本 2.0.0。

## 0. 铁律（最高优先级）

1. **数据真实性**：只允许用真实获取的数据作为分析与回测依据。**严禁**用随机/模拟/伪造数据冒充真实行情。
2. **数据不可得时**：如实降级并标注（见 §2），**不得给出 `buy` / `strong_buy` 结论**，回测须标注“样本不足、仅演示”。
3. **程序复用**：**禁止**为单个日期新建一次性脚本（如 `fetch_20260307.py`、`final_analyze_20260307_fixed.py`）。优先参数化复用 `programs/` 下现有程序。
4. **完成前自检**：必须运行 `quantr validate --date <日期> --strict` 并修复所有错误，才算任务完成。
5. **路径标注**：每个代码文件顶部注释相对路径 `# {relative_path}`；所有文件操作在项目目录 `quan_tr/` 内。
6. **不编造结论**：没有数据支撑就不下结论；不确定时明确说明不确定性与风险。

## 1. 目录与产出

```
quan_tr/
├── init.md                     # 本文件（项目约束）
├── resources.md                # 资源索引（网址/文档/账号等）
├── stocks_pool.json            # 股票池（用户维护，只读）
├── config.yaml / config.py     # 量化参数配置
├── data_files/<日期>/          # 原始数据归档（按数据源分子目录）+ manifest.json
├── analysis_results/
│   ├── <日期>/stock_<名称>_<代码>_analysis_<日期>.md   # 单股报告
│   ├── <日期>/stocks_analysis_<日期>.json              # 汇总（严格遵循模板）
│   └── templates/                                     # 模板（唯一结构来源）
├── backtest_reports/backtest_result_for_analysis_in_<日期>.md
├── programs/                   # 可复用程序（data_fetchers/ analyzers/ backtesters/ utils/）
└── resources/                  # 知识库/参考/模板
```

**分析汇总 JSON 与单股 Markdown 必须严格遵循 `analysis_results/templates/` 中的模板。** 模板是字段的唯一来源，不要在报告里自创结构。

## 2. 数据完整性（强制）

- 所有抓取到的数据归档到 `data_files/<日期>/<数据源>/`，并在 JSON 内写入来源信息：
  - 推荐用 `quantr.data_provenance.provenance_block(source, note)`，其中 `note` 说明来源与是否模拟。
- 本地 PIT 数据仓（Parquet + DuckDB）：`store/ohlcv`（多版本 `ingest_time`）、`store/fundamentals`（`report_date`/`announce_date`）。分析与回测只能用 `as_of` 当时可见的数据，禁止前视。
- 若配置了 PIT 成分股（`store/universe/<index>.csv`），只分析当日成分股，避免幸存者偏差。
- 任务结束前生成 `data_files/<日期>/manifest.json`（调用 `write_manifest(date)`）。
- 汇总 JSON 必须符合 `analysis_results/templates/stocks_analysis.schema.json`（`schema_version: "2.0.0"`）：
  - `market` 用 `SH/SZ/BJ/HK/US`；所有 `*_pct` 为百分数；`market_cap_cny` 为人民币。
  - 缺失数据写 `null`，**不要用 0 冒充缺失**。
  - `risk.score` 越高风险越大；`scores.risk_safety` 越高越安全（= 100 - risk.score）。
- 在汇总 JSON 的 `data_quality` 如实填写：
  - `status`: `real` / `partial` / `simulated` / `missing`
  - `as_of`: 数据截止交易日（非交易日取最近交易日，且不得晚于 analysis_date）
  - `sources`: `[{source, is_simulated, retrieved_at}]`
  - `notes`: 缺口/降级说明
- **判定规则**：存在任何模拟数据 → `status` 不得为 `real`；若 `status != real` 且给出 `buy/strong_buy`，校验器会直接判失败。
- 数据源优先级：AKshare（A股）> 东方财富 > Yahoo Finance（港美股/补充）；网站抓取可用 `fetch_url` / `fetch_rendered`（JS 站点）。网络失败时换源，不要造数。

## 3. 程序开发与复用（强制）

- **优先使用确定性流水线**：每日分析/回测优先用 `quantr pipeline`；技术指标与评分用 `quantr.indicators` + `quantr.factor_engine` 计算。**数值归代码，你只负责解释与文字结论**，不要自行“估”分数。
- 真实行情先落本地数据仓：`quantr fetch --save`（失败即报错，禁止造数）。
- 新能力优先**改造现有程序**并参数化，例如：
  - `programs/data_fetchers/akshare_fetcher.py`、`yfinance_fetcher.py`
  - `programs/analyzers/{fundamental,technical,risk,sentiment}_analyzer.py`
  - `programs/backtesters/strategy_backtester.py`
- 需要新增脚本时，命名体现功能而非日期；日期/股票/周期用命令行参数或配置传入。
- 历史遗留的按日期脚本（`*_2026xxxx.py`）视为只读参考，不要继续新增同类文件。
- 每次有意义的改动，在 `programs/README.md` 追加一条**简短**变更记录（日期 + 改了什么 + 为什么）。
- 代码质量：模块化、类型注解、完善异常与日志；函数尽量短小、单一职责。

## 4. 每日分析流程

1. **准备**：检查 `stocks_pool.json`、`config.yaml`、近期回测报告；按回测结论反思并优化程序（先测试）。
2. **取数**：按股票池抓取真实数据并归档；记录 provenance；生成/更新 manifest。
3. **分析**（逐股）：基本面（经营/财务/行业/宏观）+ 技术面（趋势/均线/RSI/MACD/布林/量能/支撑阻力）+ 风险 + 情绪；产出单股 Markdown。
4. **汇总**：生成符合模板的 `stocks_analysis_<日期>.json`（含 `data_quality`）与汇总说明。
5. **自检**：运行 `validate_report.py --date <日期> --strict`，修复后收尾。
6. **归档**：所有产出按日期目录归档，更新必要的索引。

**综合评分**：基本面 40% + 技术面 30% + 风险 20% + 情绪 10%（以 `config.py get_scoring_weights()` 为准）。
**推荐等级**：strong_buy ≥80；buy 60–79；hold 40–59；sell 20–39；strong_sell <20。

## 5. 策略回测流程

1. 收集近 N 天（周=7，月=30）的历史**分析结果**与对应**真实历史价格**。
2. 依据历史建议生成交易信号并模拟成交：计入佣金/滑点/仓位/止损止盈（取 `config.yaml` 的 `backtest.*`）。
3. 计算指标：累计收益、年化、最大回撤、夏普、胜率、盈亏比、交易次数、平均持仓天数。
4. 产出 `backtest_reports/backtest_result_for_analysis_in_<日期>.md`：
   - 明确**样本量、数据来源与质量**；若数据不足/含模拟，必须标注“样本不足，结论仅供参考”。
   - 给出策略有效性与优化建议，不得夸大。
5. `data_quality != real` 时，回测**不得**输出确定性盈利结论。

## 6. 分析维度（要点）

- **基本面**：治理/竞争力/行业地位；盈利（毛利、净利、ROE、ROA）、偿债（负债率、流动/速动）、运营（周转）、成长（营收/净利增速）、估值（PE/PB/股息率）。
- **技术面**：当前价与历史高低位、趋势、均线、RSI、MACD、布林带、成交量/量比、支撑阻力。
- **风险**：系统性（市场/行业/宏观）+ 非系统性（经营/财务/合规/流动性）+ 尾部风险。
- **情绪**：新闻/研报/社媒情绪与关注度（可用 `search_web`/`fetch_url` 获取真实信息）。

## 7. 配置与资源

- `stocks_pool.json`：用户维护，只读。
- `config.yaml`：数据源、权重、阈值、技术参数、回测参数；敏感信息不入库，从 `resources.md`/环境变量读取并写入本机配置。
- `resources.md`：资源索引（数据源、文档、账号说明等）。

## 8. 执行与工具约定（aacode >= 1.8.17）

- **长任务**（抓取/回测/装依赖）：用 `run_shell` 的 `background=true` 或 `action="spawn"`，再用 `action="check"/"read"/"jobs"` 查看，不要 sleep 空等；需要 TTY 的 CLI 用 `use_pty=true`。
- **大文件**：优先 `rg`/`sed`/`head`/`tail`，必要时用 `full_output`；输出过长会归档到 `.aacode/extracts/`。
- **上下文过长**：历史可能被裁剪，用 `search_history` / `read_history` 检索，切勿 `cat` 大型 session JSON。
- **改动可见**：编辑文件后留意 diff 反馈，避免盲改。

## 9. 安全与合规

- 不硬编码密钥；妥善处理敏感数据；避免危险命令。
- 分析仅供参考，**不构成投资建议**；充分提示风险；遵守数据源条款与版权。

## 10. 任务类型速览

- **股票分析**：按 §4 执行，产出单股报告 + 汇总 JSON + 数据归档 + manifest。
- **策略回测**：按 §5 执行，产出回测报告并标注数据质量与样本量。
- **程序开发/优化**：先查重、再参数化改造，写测试，更新 `programs/README.md`。
