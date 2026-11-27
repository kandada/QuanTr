# QuanTr / quantr-engine

[![PyPI](https://img.shields.io/pypi/v/quantr-engine.svg)](https://pypi.org/project/quantr-engine/)
[![Python](https://img.shields.io/pypi/pyversions/quantr-engine.svg)](https://pypi.org/project/quantr-engine/)
[![License: GPL-3.0-or-later](https://img.shields.io/badge/license-GPL--3.0--or--later-blue.svg)](LICENSE)

**Deterministic, auditable quantitative research engine** — real data only,
numbers computed by code, reports validated against a versioned contract.

> 定位：**可审计的 AI 研究助理**。LLM 负责规划/解释/写报告，**数值全部由确定性代码计算**；
> 数据缺失或模拟时，禁止给出买入结论。研究结果仅供参考，不构成投资建议。

- 引擎（`src/quantr`）不依赖 LLM，可独立安装/调用。
- 可选的自主分析 agent（`agent/`）基于 [aacode](https://pypi.org/project/aacode/)。
- 行情数据只落在本地，**发布包内不含任何市场数据**。

---

## 安装

```bash
pip install quantr-engine                  # 引擎 + CLI
pip install "quantr-engine[mcp]"           # 可选：MCP server
pip install "quantr-engine[agent]"         # 可选：aacode 自主分析
pip install "quantr-engine[talib]"         # 可选：TA-Lib 数值对齐测试
```

要求 Python >= 3.10。分发名是 `quantr-engine`，导入名是 `quantr`，命令是 `quantr`。

## 快速开始

```bash
quantr --version
quantr doctor                       # 环境 / 工作区自检

quantr init my-research && cd my-research
quantr fetch --pool --save          # 按 stocks_pool.json 抓真实行情（失败即报错，不造数）
quantr factors --symbol 000001.SZ   # 确定性评分与建议
quantr pipeline --offline           # 因子 → 报告 → manifest → 校验
quantr validate --date <today> --strict
```

`quantr init` 会生成：`init.md`、`config.yaml`、`stocks_pool.json`、`analysis_results/templates/`、
`store/`、`programs/`、`skills/quan_tr/`、`.gitignore`。

## 命令一览

所有命令支持 `--json`，返回统一契约：

```json
{"ok": true,  "command": "factors", "result": { "...": "..." }}
{"ok": false, "command": "factors", "error": "...", "hint": "..."}
```

| 命令 | 作用 | 关键参数 |
|---|---|---|
| `quantr init [dir]` | 初始化工作区（目录/模板/skill/配置） | `--force` |
| `quantr doctor` | 环境与工作区自检（版本/依赖/数据仓/提示） | `--base-dir` |
| `quantr fetch` | 抓取真实行情到本地数据仓 | `--symbols` / `--pool`, `--start/--end`, `--source`, `--no-save` |
| `quantr store` | 列出数据仓（含 `[SIMULATED]` 标记） | |
| `quantr indicators` | 技术指标快照（MA/RSI/MACD/BOLL/ATR/支撑阻力…） | `--symbol` |
| `quantr factors` | 确定性评分 + 建议（买入门禁） | `--symbol`, `--fundamentals-file` |
| `quantr backtest` | 成本回测 / walk-forward | `--symbol`, `--walk-forward`, `--signals-file` |
| `quantr pipeline` | 取数→因子→排名/组合→报告→校验 | `--date`, `--symbols/--pool`, `--offline`, `--universe`, `--portfolio-top-n` |
| `quantr validate` | 契约 v2 校验（schema + 不变量 + 数据门禁） | `--date`, `--strict`, `--allow-v1` |
| `quantr skill` | 安装/定位 agent skill | `install` / `path`, `--dest` |

### MCP

```bash
python -m quantr.mcp_server          # stdio
python -m quantr.mcp_server --list   # 打印工具 schema
```

工具：`fetch_ohlcv`、`list_store`、`compute_indicators`、`compute_factors`、
`run_backtest`、`validate_report`、`run_pipeline`。

客户端配置示例：

```json
{"mcpServers":{"quantr":{"command":"python3","args":["-m","quantr.mcp_server"]}}}
```

### Library

```python
from quantr.api import Quantr
q = Quantr(base_dir="my-research")
q.fetch(["000001.SZ"], save=True)
print(q.factors("000001.SZ")["action"])
print(q.pipeline(offline=True)["validation"]["ok"])
```

或直接用稳定函数层：`from quantr.service import fetch, factors, backtest, pipeline, validate`。

### Skill（给 agent）

```bash
quantr skill install     # 安装到 aacode 用户 skills 目录
```

之后 aacode 可通过 `run_skills("quan_tr", ...)` 使用；skill 会强制“真实数据 + `validate --strict`”。

---

## 项目结构

```
QuanTr/
├── src/quantr/            # PyPI 包：确定性引擎 + CLI + MCP + templates/skill
├── tests/                 # 契约 / 引擎 / PIT / 打包测试
├── agent/                 # 可选：基于 aacode 的自主分析入口
│   ├── main_quan_tr.py
│   ├── aacode_config.yaml
│   ├── cron_run_quan_tr.py / .sh
│   └── README.md
├── examples/workspace/    # 参考工作区（`quantr init` 生成同构）
├── docs/                  # 文档；legacy/ 为 aacode 旧文档
├── scripts/run_agent.sh
├── pyproject.toml / MANIFEST.in / requirements.txt
├── README.md / CHANGELOG.md / LICENSE / .gitignore
└── quantr                 # 仓库内 CLI shim（等价于安装后的 quantr）
```

## 数据层（PIT / 可审计）

- **OHLCV**：`store/ohlcv/<symbol>.parquet`（DuckDB 读写 Parquet，无需 pyarrow）。
  追加式多版本，行带 `ingest_time`；`load_ohlcv(..., ingest_as_of=T)` 只读取 T 之前已知的版本。
- **财报**：`store/fundamentals/<symbol>.parquet`，同时记录 `report_date` 与 `announce_date`；
  `load_fundamentals(as_of=T)` 只使用 `announce_date <= T` 的报告（防前视偏差）。
- **成分股**：`store/universe/<index>.csv`（`symbol,start_date,end_date`），
  `quantr pipeline --universe <index>` 只分析当日成员（避免幸存者偏差）。
- **来源与真实性**：`data_files/<date>/manifest.json` + `data_quality`，模拟数据会被标记并在门禁中拦截。
- **as_of**：取真实数据截止日（非交易日回退最近交易日），不会谎报“今天”。

## 数据契约（v2.1）

- 唯一契约源：`analysis_results/templates/stocks_analysis.schema.json`（JSON Schema 2020-12）；
  工作区模板优先，缺失时用包内同源模板。
- 约定：`schema_version: "2.x"`；`market ∈ {SH,SZ,BJ,HK,US}`；`*_pct` 为百分数；
  `market_cap_cny`；缺失写 `null`（禁止用 0 冒充缺失）。
- 风险不歧义：`risk.score` 越高越危险；`scores.risk_safety` 越高越安全。
- 校验器：schema + 跨字段不变量（派生字段一致性、action/overall 一致性、target/stop、
  `as_of<=analysis_date`、代码去重）+ **数据真实性门禁**。
- **买入门禁取“报告声明”和“审计结果”中更差的状态**，报告自称 `real` 无法绕过模拟数据审计。
- 旧 v1 报告需 `--allow-v1`（仅警告）。

## 回测与组合

- T+1 执行、佣金/滑点/印花税、仓位上限。
- 指标：总收益、CAGR、最大回撤、Sharpe、Sortino、Calmar、胜率、盈亏比、持仓天数、暴露度。
- `walk-forward`：MA 参数网格在训练区间选择、测试区间评估。
- 基准：A股默认 `000300.SH`，美股默认 `SPY`；离线缺失则跳过（不造假）。
- 横截面 `ranking` + `portfolio`（score/equal 权重、top-N、现金）。
- 不引入 vectorbt/backtrader：内置引擎已覆盖成本/基准/walk-forward，够用。

## 自主分析 agent（可选）

```bash
pip install -e ".[agent,mcp]"
cp .env.example .env            # 填 LLM_API_KEY / LLM_API_URL / LLM_MODEL_NAME
python3 agent/main_quan_tr.py   # 默认工作区 examples/workspace
scripts/run_agent.sh --backtest
```

- `agent/aacode_config.yaml` 通过 `AACODE_CONFIG_FILE` 固定加载，cwd 无关。
- 定时任务：`bash agent/cron_run_quan_tr.sh -t 10:00`（日志在 `<workspace>/cron_run_quan_tr.log`）。
- Agent 只做规划/解释；数值来自 `quantr`，完成前必须 `quantr validate --strict`。

## 开发与发布

```bash
pip install -e ".[dev,agent,mcp]"
python3 -m pytest -q
python3 -m build
python3 -m twine check dist/*
python3 -m twine upload --repository testpypi dist/*   # 可选
python3 -m twine upload dist/*
```

版本号单一来源：`pyproject.toml` 与 `src/quantr/__init__.py` 必须一致（有测试强制）。
发版流程见 [CHANGELOG.md](CHANGELOG.md)。

## 已知边界

- **不提供行情数据**：数据需自行抓取（AKshare/Yahoo）或导入；请遵守数据源授权。
- **不自动拉取成分股/财报 vendor 数据**：用 `universe` CSV + `save_fundamentals` 自行接入。
- **不执行交易**：只做研究分析，输出风险提示与建议。
- **TA-Lib 可选**：未安装时用独立参考实现做 golden 测试；安装后自动追加对齐测试。
- 回测不代表未来收益；过拟合与幸存者偏差仍需自行警惕。

## 免责声明

本项目仅用于研究与教育，**不构成任何投资建议**。市场有风险，决策需谨慎。

## License

GPL-3.0-or-later，见 [LICENSE](LICENSE)。
