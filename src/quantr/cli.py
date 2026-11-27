# src/quantr/cli.py
"""Unified `quantr` CLI.

Stable JSON contract for humans, cron and agents:

    {"ok": bool, "command": str, "result": {...}}      # success
    {"ok": false, "command": str, "error": "..."}       # failure

Exit code: 0 on ok, 1 otherwise.

Examples:
    quantr --version
    quantr doctor
    quantr init my-research
    quantr fetch --symbols 000001.SZ --save --json
    quantr factors --symbol 000001.SZ --json
    quantr backtest --symbol 000001.SZ --walk-forward --json
    quantr pipeline --date 2026-11-24 --offline --json
    quantr validate --date 2026-11-24 --strict --json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from . import __version__, service


def _ok_of(command: str, result: Any) -> bool:
    if not isinstance(result, dict):
        return True
    if "ok" in result:
        return bool(result["ok"])
    if command == "pipeline":
        return bool(result.get("validation", {}).get("ok", True))
    return True


def _emit(command: str, result: Any, json_mode: bool) -> int:
    ok = _ok_of(command, result)
    payload = {"ok": ok, "command": command, "result": result}
    if json_mode:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        _human(command, payload)
    return 0 if ok else 1


def _fail(command: str, exc: Exception, json_mode: bool) -> int:
    message = f"{type(exc).__name__}: {exc}"
    low = message.lower()
    hint = ""
    if "no local data" in low or "insufficient local data" in low:
        hint = "先补数据：`quantr fetch --symbols <symbol> --save`，并确认 --base-dir 指向正确工作区。"
    elif "no symbols" in low:
        hint = "用 `--symbols` 或 `--pool`；新工作区先 `quantr init <dir>`。"
    elif "no usable data" in low:
        hint = "检查数据仓（`quantr fetch --pool --save`），或去掉 `--offline` 联网取数。"
    elif "legacy_or_unsupported" in low:
        hint = "旧 v1 报告加 `--allow-v1`，或重新 `quantr pipeline` 生成 v2。"
    elif "jsonschema" in low and "missing" in low:
        hint = "安装依赖：`pip install jsonschema`。"
    payload = {"ok": False, "command": command, "error": message}
    if hint:
        payload["hint"] = hint
    if json_mode:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"❌ {command}: {message}")
        if hint:
            print(f"   → {hint}")
    return 1


def _human(command: str, payload: Dict[str, Any]) -> None:
    if not payload["ok"]:
        print(f"❌ {command}: {payload.get('error', 'failed')}")
        if payload.get("hint"):
            print(f"   → {payload['hint']}")
        return

    r = payload.get("result", {})
    if command == "fetch":
        records = r.get("records", [])
        if not records:
            print("no records")
        for rec in records:
            if rec.get("ok"):
                print(
                    f"✅ {rec['symbol']}  {rec.get('source', '')}  rows={rec.get('rows')}  "
                    f"{rec.get('first_date')}..{rec.get('last_date')}"
                )
            else:
                print(f"❌ {rec.get('symbol')}: {rec.get('error')}")
    elif command == "store":
        print(f"store: {r.get('count', 0)} symbol(s)")
        for item in r.get("symbols", []):
            sim = "  [SIMULATED]" if item.get("is_simulated") else ""
            print(
                f"  - {item['symbol']}  rows={item.get('rows')}  "
                f"{item.get('first_date')}..{item.get('last_date')}{sim}"
            )
    elif command == "indicators":
        snap = r.get("snapshot", {}) or {}
        print(f"{r.get('symbol')}  bars={snap.get('bars')}  last={snap.get('last_date')}")
        print(
            f"  trend={snap.get('trend')}  close={snap.get('close')}  "
            f"MA20/50/200={snap.get('ma20')}/{snap.get('ma50')}/{snap.get('ma200')}"
        )
        print(
            f"  RSI={snap.get('rsi')}  MACD={snap.get('macd')}  vol_ratio={snap.get('volume_ratio')}  "
            f"support/resistance={snap.get('support')}/{snap.get('resistance')}"
        )
        print(
            f"  vol_annual={snap.get('volatility_annual')}  max_dd={snap.get('max_drawdown')}"
        )
    elif command == "factors":
        risk = r.get("risk", {}) or {}
        subs = r.get("subscores", {}) or {}
        print(
            f"{r.get('symbol')}  overall={r.get('overall')}  action={r.get('action')}  "
            f"confidence={r.get('confidence')}"
        )
        print(
            f"  subscores: fundamental={subs.get('fundamental')} technical={subs.get('technical')} "
            f"risk_safety={subs.get('risk')} sentiment={subs.get('sentiment')}"
        )
        print(
            f"  risk: level={risk.get('level')} score={risk.get('score')} factors={risk.get('factors')}"
        )
        for note in r.get("notes", []) or []:
            print(f"  note: {note}")
    elif command == "backtest":
        if r.get("mode") == "walk_forward":
            print(
                f"{r.get('symbol')}  walk-forward windows={r.get('window_count')}  "
                f"positive={r.get('positive_windows')}  avg_return={r.get('avg_return')}"
            )
        else:
            m = r.get("metrics", {}) or {}
            print(
                f"{r.get('symbol')}  total_return={m.get('total_return')} cagr={m.get('cagr')} "
                f"max_dd={m.get('max_drawdown')} sharpe={m.get('sharpe')}"
            )
            print(
                f"  trades={m.get('trades')} win_rate={m.get('win_rate')} "
                f"profit_factor={m.get('profit_factor')} exposure={m.get('exposure')}"
            )
    elif command == "validate":
        verdict = "OK" if r.get("ok") else "FAIL"
        print(
            f"validate {r.get('date')}: {verdict}  data_status={r.get('data_quality_status')}  "
            f"schema={r.get('schema_version')}"
        )
        for err in r.get("errors", [])[:10]:
            print(f"  ❌ {err.get('path')}: {err.get('issue')} {err.get('detail', '')}".rstrip())
        for warn in r.get("warnings", [])[:10]:
            print(f"  ⚠️  {warn.get('path')}: {warn.get('issue')} {warn.get('detail', '')}".rstrip())
        total = len(r.get("errors", [])) + len(r.get("warnings", []))
        if total > 20:
            print(f"  ... ({total} total)")
    elif command == "pipeline":
        dq = r.get("data_quality", {}) or {}
        print(
            f"pipeline {r.get('date')}  symbols={len(r.get('symbols', []))}  "
            f"data_status={dq.get('status')}  as_of={dq.get('as_of')}"
        )
        ranking = r.get("ranking", []) or []
        if ranking:
            print("  ranking:")
            for row in ranking[:10]:
                print(
                    f"    #{row.get('rank')} {row.get('symbol')}  "
                    f"overall={row.get('overall')}  action={row.get('action')}"
                )
        pf = r.get("portfolio", {}) or {}
        if pf:
            print(
                f"  portfolio: {pf.get('method')}  invested={pf.get('invested_weight')}  "
                f"cash={pf.get('cash_weight')}"
            )
            for item in pf.get("constituents", []):
                print(f"    - {item.get('symbol')}  weight={item.get('weight')}  score={item.get('score')}")
        bm = r.get("benchmark")
        if bm:
            print(f"  benchmark: {bm.get('symbol')}  return={bm.get('return')}  as_of={bm.get('as_of')}")
        print(f"  wrote: {r.get('json')}")
        print(f"  validation: {'OK' if r.get('validation', {}).get('ok') else 'FAIL'}")
    elif command == "doctor":
        print(f"quantr {r.get('version')}  python {r.get('python')}  {r.get('platform')}")
        print(f"  workspace: {r.get('workspace')}  is_workspace={r.get('is_workspace')}")
        print(f"  templates: {r.get('templates_source')} ({r.get('templates_dir')})")
        print(f"  store symbols: {r.get('store_symbols')}")
        deps = r.get("dependencies", {}) or {}
        print("  deps: " + ", ".join(f"{k}={v}" for k, v in deps.items()))
        print(f"  aacode={r.get('aacode')}  mcp={r.get('mcp')}")
        for hint in r.get("hints", []) or []:
            print(f"  hint: {hint}")
    elif command == "init":
        print(f"workspace: {r.get('root')}  (created {len(r.get('created', []))} files)")
        print("next:")
        print("  cd <workspace>")
        print("  quantr fetch --pool --save")
        print("  quantr pipeline --offline --json")
        print("  quantr validate --date <today> --strict")
    elif command == "skill":
        print(f"skill: {r.get('target')}")
        print("  → restart the agent so it re-discovers skills")
    else:
        print(json.dumps(r, ensure_ascii=False, indent=2, default=str))


def _load_json(path: Optional[str]) -> Optional[Dict[str, Any]]:
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="输出 JSON（推荐给 agent/cron）")
    common.add_argument("--base-dir", default=None, help="工作区根目录（默认按文件位置推断）")

    parser = argparse.ArgumentParser(
        prog="quantr",
        description="QuanTr CLI — deterministic, reproducible quant workflow (real data only).",
    )
    parser.add_argument("--version", action="version", version=f"quantr {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("fetch", parents=[common], help="抓取真实行情到本地数据仓")
    p.add_argument("--symbols", default=None, help="逗号分隔，如 000001.SZ,600000.SH")
    p.add_argument("--pool", action="store_true", help="从 stocks_pool.json 读取股票池")
    p.add_argument("--start", default=None, help="YYYY-MM-DD")
    p.add_argument("--end", default=None, help="YYYY-MM-DD")
    p.add_argument("--source", default="auto", choices=["auto", "akshare", "yfinance"])
    p.add_argument("--save", action="store_true", default=True, help="写入数据仓（默认）")
    p.add_argument("--no-save", dest="save", action="store_false")

    sub.add_parser("store", parents=[common], help="列出本地数据仓")
    sub.add_parser("doctor", parents=[common], help="环境/工作区自检")

    p = sub.add_parser("indicators", parents=[common], help="计算技术指标快照")
    p.add_argument("--symbol", required=True)

    p = sub.add_parser("factors", parents=[common], help="计算确定性因子/评分/建议")
    p.add_argument("--symbol", required=True)
    p.add_argument("--fundamentals-file", default=None, help="基本面 JSON 文件")

    p = sub.add_parser("backtest", parents=[common], help="回测（默认 walk-forward）")
    p.add_argument("--symbol", required=True)
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--signals-file", default=None, help="JSON: {date: action}")
    p.add_argument("--walk-forward", action="store_true", help="滚动走查（默认）")

    p = sub.add_parser("validate", parents=[common], help="校验当日产出（契约 v2）")
    p.add_argument("--date", required=True)
    p.add_argument("--strict", action="store_true")
    p.add_argument("--allow-v1", action="store_true", help="兼容校验旧版 v1 报告")

    p = sub.add_parser("pipeline", parents=[common], help="取数→因子→报告→校验 全流程")
    p.add_argument("--date", default=None)
    p.add_argument("--symbols", default=None, help="逗号分隔；默认读 stocks_pool.json")
    p.add_argument("--pool", action="store_true", help="使用 stocks_pool.json（默认行为）")
    p.add_argument("--offline", action="store_true")
    p.add_argument("--source", default="auto", choices=["auto", "akshare", "yfinance"])
    p.add_argument("--mode", default="all", choices=["all", "fetch", "analyze", "backtest"])
    p.add_argument("--no-backtest", dest="run_backtest", action="store_false", default=True)
    p.add_argument("--universe", default=None, help="PIT 成分股索引名（store/universe/<index>.csv）")
    p.add_argument("--portfolio-top-n", type=int, default=5)
    p.add_argument("--portfolio-method", default="score_weight", choices=["score_weight", "equal_weight"])

    p = sub.add_parser("init", parents=[common], help="初始化 Quantr 工作区（目录/模板/skill/config）")
    p.add_argument("path", nargs="?", default=".", help="目标目录（默认当前目录）")
    p.add_argument("--force", action="store_true", help="覆盖已存在的脚手架文件")

    p = sub.add_parser("skill", parents=[common], help="安装/定位 QuanTr skill（供 aacode 发现）")
    p.add_argument("action", nargs="?", choices=["install", "path"], default="install",
                   help="install（默认）或 path")
    p.add_argument("--dest", default=None, help="自定义安装根目录（默认 aacode 用户目录）")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    json_mode = bool(getattr(args, "json", False))
    base = getattr(args, "base_dir", None)
    command = args.command

    try:
        if command == "fetch":
            symbols = [s.strip() for s in args.symbols.split(",") if s.strip()] if args.symbols else []
            if not symbols and args.pool:
                symbols = service.workspace_symbols(base)
            if not symbols:
                raise ValueError("no symbols: pass --symbols or --pool (needs stocks_pool.json)")
            result = service.fetch(symbols, args.start, args.end, args.source, args.save, base)
        elif command == "store":
            result = service.store(base)
        elif command == "doctor":
            result = service.doctor(base)
        elif command == "indicators":
            result = service.indicators(args.symbol, base)
        elif command == "factors":
            fundamentals = _load_json(args.fundamentals_file)
            result = service.factors(args.symbol, base, fundamentals)
        elif command == "backtest":
            signals = _load_json(args.signals_file)
            result = service.backtest(
                args.symbol, args.start, args.end, signals,
                walk_forward=(args.walk_forward or not signals), base_dir=base,
            )
        elif command == "validate":
            result = service.validate(args.date, base, args.strict, args.allow_v1)
        elif command == "pipeline":
            symbols = [s.strip() for s in args.symbols.split(",")] if args.symbols else None
            result = service.pipeline(
                date=args.date, symbols=symbols, base_dir=base,
                offline=args.offline, source=args.source, mode=args.mode,
                run_backtest=args.run_backtest, universe=args.universe,
                portfolio_top_n=args.portfolio_top_n,
                portfolio_method=args.portfolio_method,
            )
        elif command == "init":
            result = service.init_workspace(args.path, args.force)
        elif command == "skill":
            if args.action == "path":
                result = {"ok": True, "target": str(service.skill_path(args.dest))}
            else:
                result = service.install_skill(args.dest)
        else:  # pragma: no cover - argparse enforces choices
            raise ValueError(f"unknown command: {command}")
        return _emit(command, result, json_mode)
    except Exception as exc:  # noqa: BLE001
        return _fail(command, exc, json_mode)


if __name__ == "__main__":
    raise SystemExit(main())
