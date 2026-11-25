> 说明：确定性引擎已抽成 `quantr` 包（`pip install quantr`）。本 `programs/` 目录仅保留
> 工作区自有/历史脚本；下文中提到的 schema/indicators/data_store/engine 等模块位于 `quantr` 包内。

# QuanTr 程序索引（programs/README.md）

> 保持简洁：这里只做**模块索引**与**变更记录**。每次有意义改动追加一条。

## 0. 对外接口（同一套确定性引擎）

- **CLI**（推荐入口，统一 JSON 契约）：
  - 安装后：`quantr <command> [--json]`；仓库内也可用 `./quantr ...`（从 `src/` 运行）
  - 命令：`fetch / store / indicators / factors / backtest / validate / pipeline / skill`
  - 输出：`{"ok": bool, "command": str, "result": {...}}`，退出码 0/1。
- **MCP server**：`python -m quantr.mcp_server`（stdio）
  - 工具：`fetch_ohlcv / list_store / compute_indicators / compute_factors / run_backtest / validate_report / run_pipeline`
  - `--list` 打印工具 schema。
- **Library**：
  - `import sys; sys.path.insert(0,"quan_tr/programs"); from api import Quantr`
  - `from service import fetch, factors, backtest, pipeline, validate`（稳定函数层）
- **Skill**（给 aacode/opencode 等 agent）：
  - `./quantr skill install` → 安装到 aacode 用户 skills 目录，agent 可用 `run_skills("quan_tr", ...)`
  - `./quantr skill path` → 查看安装位置
  - 源文件：`quan_tr/skills/quan_tr/SKILL.md`

## 1. 可复用模块

### 主流程（推荐入口）
- `run_pipeline.py` — **可复现流水线**：真实取数 → 确定性指标/因子 → 模板化 JSON + 单股 MD → manifest → 校验。
  - `quantr pipeline --pool --offline`
  - `quantr pipeline --symbols 000001.SZ,600000.SH --date 2026-11-24`
  - `--mode fetch` 只更新数据仓；`--no-backtest` 跳过回测。

### data_fetchers/ 数据获取
- `market_data.py` — **参数化真实取数**（AKshare/Yahoo），失败即报错，**绝不造数**；`--save` 写入数据仓。
- `akshare_fetcher.py` / `yfinance_fetcher.py` — 早期封装（保留参考）。

> 约定：新需求参数化改造现有程序（日期/股票/周期走参数），不要新建按日期命名的脚本。

### analyzers/ 分析
- `factor_engine.py` — **确定性评分/排序**：技术面、风险由指标计算；基本面/情绪仅在真实数据存在时计分；`allow_buy=False` 时强制降级买入；`rank_scores/rank_universe` 横截面排序。
- `portfolio.py` — **组合构建**：从排名选 top-N（剔除卖出），score_weight / equal_weight，总仓位受 `max_position_ratio` 限制，剩余为现金。
- `fundamental_analyzer.py` — 基本面（盈利/偿债/运营/成长/估值）
- `technical_analyzer.py` — 技术面
- `risk_analyzer.py` / `sentiment_analyzer.py` — 风险 / 情绪

### backtesters/ 回测
- `engine.py` — **严谨回测**：T+1 执行、佣金/滑点/印花税、收益/回撤/夏普/索提诺/Calmar/胜率/盈亏比、基准对比、walk-forward。
- `strategy_backtester.py` — 早期回测（保留参考）。

### utils/ 工具
- `schema.py` — 代码规范化（`000001_SZ`/`sh600000`/`0700.HK`/`AAPL`）与 OHLCV 标准化/校验。
- `indicators.py` — 纯代码技术指标（MA/EMA/RSI/MACD/BOLL/ATR/OBV/量比/支撑阻力/回撤）。
- `data_store.py` — **PIT 数据仓（Parquet + DuckDB）**：`store/ohlcv/<symbol>.parquet` 多版本（`ingest_time`，支持 `ingest_as_of` 查询）；财报 `store/fundamentals/<symbol>.parquet`（`report_date`/`announce_date`，`load_fundamentals(as_of)` 防前视）。
- `universe.py` — **PIT 成分股**：`store/universe/<index>.csv`（symbol/start/end），`load_universe(index, as_of)` 过滤历史成员，避免幸存者偏差。
- `data_provenance.py` — 数据来源与真实性标记，生成 `data_files/<日期>/manifest.json`。
- `market_clock.py` — 交易日历（非交易日取最近交易日 `as_of`）。
- `validate_report.py` — 产出校验器（模板字段完整性 + 模拟数据 + 买入结论门禁）。
  - `quantr validate --date YYYY-MM-DD --strict`
- `data_processor.py` — 数据清洗/转换（早期）。

## 2. 数据真实性门禁（重要）

- 抓数时用 `data_provenance.provenance_block()` 标注来源；任务结束调用 `write_manifest(date)`。
- 汇总 JSON 的 `data_quality.status` 必须如实（real/partial/simulated/missing）。
- `status != real` 时禁止 `buy/strong_buy`，回测须标注“样本不足”。
- 完成前必须通过 `validate_report.py --strict`。

## 2.5 数据契约（v2）

- 机器契约：`analysis_results/templates/stocks_analysis.schema.json`（JSON Schema 2020-12，唯一契约源）。
- 人类/示例：`analysis_results/templates/stocks_analysis.example.json`（真实取值示例，pipeline 用它做骨架）。
- 关键约定：
  - `schema_version: "2.1.0"`（2.x 兼容）；`market` 取 `SH/SZ/BJ/HK/US`；`*_pct` 表示百分数；`market_cap_cny` 为人民币。
  - 可选扩展：`ranking`（横截面排名）、`portfolio`（选股/权重/现金）、`benchmark`（基准区间收益）。
  - 风险双标已消除：`risk.score` 越高=风险越大；`scores.risk_safety` 越高=越安全（= 100 - score）。
  - 缺失一律 `null`，禁止用 0 冒充缺失。
  - `metadata.total_stocks`、`summary.recommendations` 必须与 `stocks` 一致（校验器会重算）。
  - `data_quality.as_of <= analysis_date` 且为交易日；`target_price > current`、`stop_loss < current`。
- 校验：`validate_report.py` = JSON Schema + 跨字段不变量 + 数据真实性门禁。
  - **买入门禁取"报告声明"和"审计结果"中更差的状态**，报告自称 `real` 无法绕过审计。
  - 新报告必须 v2；旧 v1 报告用 `--allow-v1` 兼容（仅警告）。

## 3. 历史遗留脚本（只读参考，勿新增同类）

`fetch_2026xxxx.py`、`final_analyze_2026xxxx*.py`、`reanalyze_*`、`stock_analyzer*.py_*` 等为早期一次性脚本，
其中部分使用了**模拟数据**。后续请把能力合并进上面的可复用模块，不再按日期新增。

## 4. 变更记录（最近在前，保持简短）

- 2026-11-24（PIT/组合）：数据仓升级 Parquet+DuckDB（OHLCV 多版本 `ingest_time`、财报 `report_date/announce_date` PIT）；新增 `universe.py`（PIT 成分股）与 `portfolio.py`（排序选股/权重/现金）；pipeline 输出 `ranking`/`portfolio`/`benchmark`（契约 2.1.0）；新增指标 golden 测试（对独立参考实现，TA-Lib 可用时自动对比）。
- 2026-11-24（契约 v2）：新增 `stocks_analysis.schema.json` + `.example.json`；校验器升级为 schema + 不变量 + 数据真实性门禁（修复"报告自称 real 绕过审计"漏洞）；pipeline 输出 v2（market 枚举、`*_pct`、`risk_safety`、`sources` 对象）；v1 报告走 `--allow-v1`。
- 2026-11-24（接口版）：新增统一 CLI（`cli.py` + 根目录 `quantr`）、MCP server（`mcp_server.py`）、库门面（`service.py`/`api.py`）与 `skill install`；同一服务层被 CLI/MCP/Library/Skill 复用。
- 2026-11-24（引擎版）：新增 `run_pipeline.py`、`data_fetchers/market_data.py`、`analyzers/factor_engine.py`、`backtesters/engine.py`、`utils/{schema,indicators,data_store}.py`；数值改由确定性代码计算，回测支持成本/基准/walk-forward；本地数据仓落盘。
- 2026-11-24：新增 `utils/data_provenance.py`、`utils/market_clock.py`、`utils/validate_report.py`；建立数据真实性与模板校验门禁；明确“禁止按日期新建脚本”。
- 2026-05-19：内联技术指标（MA/RSI/MACD/布林/ATR），严格对齐模板；基于 05-18 数据生成 05-19 数据（**含模拟，仅演示**）。
- 2026-03-07：修复价格字段为 0、补齐 JSON 结构；数据获取失败时使用模拟数据（**仅演示**）。
- 2026-03-03：修复 JSON 模板字段缺失、股票代码后缀解析、`template_version` KeyError。
- 2026-03-02：修复 `stock_analyzer` 导入路径（`quan_tr.config` → `config`）；简化分析脚本。
- 2026-02-25：统一分析器调用签名；修复 numpy 类型 JSON 序列化；增加数据源失败回退。
