# quan_tr/programs/cli.py
"""Unified `quantr` CLI.

Stable JSON contract for humans, cron and agents:

    {"ok": bool, "command": str, "result": {...}}      # success
    {"ok": false, "command": str, "error": "..."}       # failure

Exit code: 0 on ok, 1 otherwise.

Examples:
    python programs/cli.py fetch --symbols 000001.SZ --source auto --save
    python programs/cli.py indicators --symbol 000001.SZ --json
    python programs/cli.py factors --symbol 000001.SZ --json
    python programs/cli.py backtest --symbol 000001.SZ --walk-forward --json
    python programs/cli.py pipeline --date 2026-11-24 --symbols 000001.SZ --offline --json
    python programs/cli.py validate --date 2026-11-24 --strict --json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from . import service


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
    payload = {
        "ok": False,
        "command": command,
        "error": f"{type(exc).__name__}: {exc}",
    }
    if json_mode:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"❌ {command}: {payload['error']}")
    return 1


def _human(command: str, payload: Dict[str, Any]) -> None:
    if not payload["ok"]:
        print(f"❌ {command}: {payload.get('error', 'failed')}")
        return
    result = payload.get("result", {})
    if command == "fetch":
        for rec in result.get("records", []):
            if rec.get("ok"):
                print(f"✅ {rec['symbol']} {rec.get('source', '')} rows={rec.get('rows')}")
            else:
                print(f"❌ {rec.get('symbol')}: {rec.get('error')}")
    elif command == "store":
        print(f"store: {result.get('count', 0)} symbols")
        for item in result.get("symbols", []):
            print(f"  - {item['symbol']} rows={item.get('rows')} {item.get('first_date')}..{item.get('last_date')}")
    elif command == "indicators":
        print(f"{result.get('symbol')} snapshot: {json.dumps(result.get('snapshot', {}), ensure_ascii=False)}")
    elif command == "factors":
        print(
            f"{result.get('symbol')} overall={result.get('overall')} "
            f"action={result.get('action')} risk={result.get('risk', {}).get('level')}"
        )
    elif command == "backtest":
        metrics = result.get("metrics", result)
        print(f"{result.get('symbol')} {json.dumps(metrics, ensure_ascii=False, default=str)}")
    elif command == "validate":
        verdict = "OK" if result.get("ok") else "FAIL"
        print(f"validate {result.get('date')}: {verdict} "
              f"errors={len(result.get('errors', []))} warnings={len(result.get('warnings', []))}")
    elif command == "pipeline":
        dq = result.get("data_quality", {})
        print(f"pipeline {result.get('date')} symbols={result.get('symbols')} data_status={dq.get('status')}")
        print(f"  json: {result.get('json')}")
    elif command == "skill":
        print(f"skill: {result.get('target')}")
    elif command == "init":
        print(f"workspace: {result.get('root')} (created {len(result.get('created', []))} files)")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def _load_json(path: Optional[str]) -> Optional[Dict[str, Any]]:
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="输出 JSON（推荐给 agent/cron）")
    common.add_argument("--base-dir", default=None, help="quan_tr 根目录（默认按文件位置推断）")

    parser = argparse.ArgumentParser(
        prog="quantr",
        description="QuanTr CLI — deterministic, reproducible quant workflow (real data only).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("fetch", parents=[common], help="抓取真实行情到本地数据仓")
    p.add_argument("--symbols", required=True, help="逗号分隔，如 000001.SZ,600000.SH")
    p.add_argument("--start", default=None, help="YYYY-MM-DD")
    p.add_argument("--end", default=None, help="YYYY-MM-DD")
    p.add_argument("--source", default="auto", choices=["auto", "akshare", "yfinance"])
    p.add_argument("--save", action="store_true", default=True, help="写入数据仓（默认）")
    p.add_argument("--no-save", dest="save", action="store_false")

    sub.add_parser("store", parents=[common], help="列出本地数据仓")

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
            symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
            result = service.fetch(symbols, args.start, args.end, args.source, args.save, base)
        elif command == "store":
            result = service.store(base)
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
