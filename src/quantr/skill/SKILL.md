## Description
QuanTr quantitative research toolkit. Fetch REAL market data, compute deterministic technical indicators and factor scores, run cost-aware backtests, generate template-conforming analysis reports, and validate them. Use it for single-stock analysis, factor scoring, strategy backtesting, and daily research report generation. Never used for live order execution.

## When to use
- 用户要求分析 / 评分某只股票或一个股票池
- 回测某个策略或历史建议的有效性
- 生成每日分析产出（JSON 汇总 + 单股 Markdown）并校验
- 计算技术指标（MA/RSI/MACD/BOLL/ATR…）

Do NOT use for: live trading, guaranteeing returns, or fabricating data when a source fails.

## Data & correctness rules (mandatory)
1. Only REAL data. If fetching fails, report the failure — never simulate or invent prices.
2. Numbers must come from the tools below, not your own estimation.
3. If `data_quality.status != "real"`, never output `buy` / `strong_buy`.
4. Before finishing, `validate --strict` must pass.
5. Output is research only, not investment advice.

## Commands (run via run_shell; working dir = `quan_tr/`)
- Update real data into the local store:
  `quantr fetch --symbols 000001.SZ --source auto --save --json`
- Technical indicators:
  `quantr indicators --symbol 000001.SZ --json`
- Deterministic factors / recommendation:
  `quantr factors --symbol 000001.SZ --json`
- Backtest (default walk-forward; costs included):
  `quantr backtest --symbol 000001.SZ --walk-forward --json`
- Full pipeline (fetch → factors → ranking/portfolio → JSON + MD + manifest → validate):
  `quantr pipeline --symbols 000001.SZ --date YYYY-MM-DD --json`
  (add `--offline` to reuse the local store; `--no-backtest` to skip backtest;
   `--universe <index>` to restrict to PIT constituents; output includes
   `ranking`, `portfolio` and (if available) `benchmark`)
- Validate a date's outputs:
  `quantr validate --date YYYY-MM-DD --strict --json`
- Inspect local store:
  `quantr store --json`

All commands return a stable JSON envelope: `{"ok": bool, "command": str, "result": {...}}`
(exit code 0 on success, 1 otherwise). Parse `result`, not stdout prose.

## Examples
- "分析 000001.SZ 最近走势":
  1. `quantr fetch --symbols 000001.SZ --save --json`
  2. `quantr factors --symbol 000001.SZ --json`
  3. Explain the returned indicators/scores in natural language; do not change the numbers.
- "回测一下这只票":
  `quantr backtest --symbol 000001.SZ --walk-forward --json`
  Then summarize metrics (return, max drawdown, sharpe, win rate) and data caveats.
- "生成今天的报告":
  `quantr pipeline --date <today> --json` (ensure data is real first)
  Then `quantr validate --date <today> --strict --json`.

## Alternative interfaces
- MCP: `python -m quantr.mcp_server` exposes the same capabilities as MCP tools
  (`fetch_ohlcv`, `compute_indicators`, `compute_factors`, `run_backtest`,
  `validate_report`, `run_pipeline`, `list_store`).
- Library: `from quantr.api import Quantr`.
