# quan_tr/programs/run_pipeline.py
"""可复现的量化流水线（替代按日期新建的一次性脚本）。

一条命令完成：真实取数 → 确定性因子/指标 → 生成模板化 JSON + 单股 MD →
写 manifest → 运行校验器。支持多标的、离线复用本地数据仓。

用法：
    python programs/run_pipeline.py --symbols 000001.SZ,600000.SH --date 2026-11-24
    python programs/run_pipeline.py --pool --offline          # 用本地数据仓
    python programs/run_pipeline.py --symbols 000001.SZ --mode fetch
"""

from __future__ import annotations

import argparse
import copy
import json
import sys

import pandas as pd
from datetime import date as _date
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

_PROG = Path(__file__).resolve().parent
for _sub in ("", "utils", "analyzers", "backtesters", "data_fetchers"):
    _path = _PROG / _sub
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from .schema import parse_symbol  # noqa: E402
from ._paths import workspace_root  # noqa: E402
from .data_store import (  # noqa: E402
    get_meta,
    load_fundamentals,
    load_ohlcv,
    save_ohlcv,
)
from .data_provenance import write_manifest  # noqa: E402
from .validate_report import load_example, validate_date  # noqa: E402
from .market_clock import describe as market_describe  # noqa: E402
from .factor_engine import compute_scores, rank_scores  # noqa: E402
from .portfolio import build_portfolio  # noqa: E402
from .universe import load_universe  # noqa: E402
from .engine import walk_forward_ma  # noqa: E402

MD_SECTIONS = ("基本信息", "价格", "基本面", "技术面", "风险", "投资建议")


def _load_pool(base: Path) -> Dict[str, Dict[str, Any]]:
    pool_path = base / "stocks_pool.json"
    pool: Dict[str, Dict[str, Any]] = {}
    if not pool_path.exists():
        return pool
    data = json.loads(pool_path.read_text(encoding="utf-8"))
    for item in data.get("stocks", []):
        raw = item.get("symbol")
        if not raw:
            continue
        try:
            canonical = parse_symbol(raw)["canonical"]
        except ValueError:
            continue
        pool[canonical] = item
    return pool


def _load_fundamentals(
    base: Path, canonical: str, as_of: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """PIT fundamentals: only announcements visible on/before ``as_of``."""
    return load_fundamentals(canonical, as_of=as_of, base_dir=base)


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _opt(value: Any) -> Optional[float]:
    """Return a rounded float or None for missing (v2 distinguishes null vs 0)."""
    try:
        if value is None:
            return None
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _pct(fund: Dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        if fund.get(key) is not None:
            return _opt(fund[key])
    return None


def _build_stock(
    template_stock: Dict[str, Any],
    symbol: str,
    pool_item: Dict[str, Any],
    df,
    result: Dict[str, Any],
    fundamentals: Optional[Dict[str, Any]],
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    info = parse_symbol(symbol)
    snap = result["snapshot"]
    subs = result["subscores"]
    risk = result["risk"]
    last = df.iloc[-1]
    prev_close = df["close"].iloc[-2] if len(df) > 1 else last["close"]
    change_pct = (last["close"] / prev_close - 1) * 100 if prev_close else 0.0
    fund = fundamentals or {}
    meta = meta or {}

    stock = copy.deepcopy(template_stock)
    stock["basic_info"] = {
        "name": pool_item.get("name") or info["code"],
        "code": info["canonical"],
        "market": info["market"],
        "sector": pool_item.get("industry") or "",
    }
    stock["price"] = {
        "current": round(_num(last["close"]), 3),
        "change_pct": round(change_pct, 3),
        "high": round(_num(last["high"]), 3),
        "low": round(_num(last["low"]), 3),
        "volume": int(_num(last["volume"])),
        "market_cap_cny": _opt(fund.get("market_cap_cny") or fund.get("market_cap")),
        "pe": _opt(fund.get("pe") or fund.get("pe_ratio")),
        "pb": _opt(fund.get("pb") or fund.get("pb_ratio")),
    }
    stock["fundamental"] = {
        "revenue_growth_pct": _pct(fund, "revenue_growth_pct", "revenue_growth"),
        "profit_growth_pct": _pct(fund, "profit_growth_pct", "profit_growth"),
        "gross_margin_pct": _pct(fund, "gross_margin_pct", "gross_margin"),
        "net_margin_pct": _pct(fund, "net_margin_pct", "net_margin"),
        "roe_pct": _pct(fund, "roe_pct", "roe"),
        "debt_ratio_pct": _pct(fund, "debt_ratio_pct", "debt_ratio"),
    }
    stock["technical"] = {
        "trend": snap.get("trend") or "sideways",
        "ma20": _opt(snap.get("ma20")),
        "ma50": _opt(snap.get("ma50")),
        "ma200": _opt(snap.get("ma200")),
        "rsi": _opt(snap.get("rsi")),
        "macd": _opt(snap.get("macd")),
        "volume_ratio": _opt(snap.get("volume_ratio")),
        "support": _opt(snap.get("support")),
        "resistance": _opt(snap.get("resistance")),
    }
    stock["risk"] = {
        "level": risk["level"],
        "score": risk["score"],
        "factors": list(risk["factors"]),
    }
    stock["sentiment"] = {"score": subs["sentiment"], "news": "neutral", "buzz": 0}
    stock["scores"] = {
        "fundamental": subs["fundamental"],
        "technical": subs["technical"],
        "risk_safety": subs["risk"],
        "sentiment": subs["sentiment"],
        "overall": result["overall"],
    }

    atr = snap.get("atr")
    close = _num(last["close"])
    target = round(close + 2 * atr, 3) if atr else 0.0
    stop = round(close - 1.5 * atr, 3) if atr else 0.0
    reason_parts = [f"技术面评分{subs['technical']}", f"趋势{snap.get('trend')}"]
    if result["notes"]:
        reason_parts.append("；".join(result["notes"]))
    stock["recommendation"] = {
        "action": result["action"],
        "confidence": result["confidence"],
        "target_price": target,
        "stop_loss": stop,
        "reason": "; ".join(reason_parts),
    }

    strengths: List[str] = []
    risks: List[str] = list(risk["factors"])
    opportunities: List[str] = []
    if snap.get("trend") == "up":
        strengths.append("均线多头排列")
    if snap.get("rsi") and 50 <= _num(snap["rsi"]) <= 70:
        strengths.append("RSI 处于健康区间")
    if snap.get("macd") and _num(snap["macd"]) > 0:
        opportunities.append("MACD 位于零轴上方")
    if not fundamentals:
        risks.append("缺少基本面数据，结论以技术面为主")
    stock["highlights"] = {
        "strengths": strengths,
        "risks": risks,
        "opportunities": opportunities,
    }
    stock["provenance"] = {
        "price_source": meta.get("source") or "",
        "fundamentals_source": (fund.get("source") if fundamentals else None),
        "is_simulated": bool(meta.get("is_simulated")),
    }
    return stock


def _summary(payload: Dict[str, Any]) -> None:
    stocks = payload["stocks"]
    counts = {"strong_buy": 0, "buy": 0, "hold": 0, "sell": 0, "strong_sell": 0}
    overalls = []
    risk_scores = []
    for stock in stocks:
        action = stock["recommendation"]["action"]
        counts[action] = counts.get(action, 0) + 1
        overalls.append(_num(stock["scores"]["overall"], 50))
        risk_scores.append(_num(stock["risk"]["score"]))
    avg = sum(overalls) / len(overalls) if overalls else 50
    avg_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 50
    payload["summary"] = {
        "market_sentiment": "bullish" if avg >= 65 else ("bearish" if avg <= 40 else "neutral"),
        "risk_level": "high" if avg_risk >= 60 else ("medium" if avg_risk >= 40 else "low"),
        "recommendations": counts,
    }
    payload["metadata"]["total_stocks"] = len(stocks)


def _md_report(stock: Dict[str, Any], date_str: str, data_quality: Dict[str, Any]) -> str:
    info = stock["basic_info"]
    price = stock["price"]
    tech = stock["technical"]
    risk = stock["risk"]
    rec = stock["recommendation"]
    scores = stock["scores"]
    fund = stock["fundamental"]
    highlights = stock["highlights"]

    def _fmt(value):
        return "—" if value is None else value

    lines = [
        f"# {info['name']} ({info['code']}) 分析报告 {date_str}",
        "",
        "## 基本信息",
        f"- 名称/代码: {info['name']} / {info['code']}",
        f"- 市场/行业: {info['market']} / {info['sector']}",
        "",
        "## 价格数据",
        f"- 现价: {price['current']}  涨跌幅: {price['change_pct']}%",
        f"- 当日高/低: {price['high']} / {price['low']}  成交量: {price['volume']}",
        f"- PE/PB/市值(CNY): {_fmt(price['pe'])} / {_fmt(price['pb'])} / {_fmt(price['market_cap_cny'])}",
        "",
        "## 基本面",
        f"- 营收/利润增速: {_fmt(fund['revenue_growth_pct'])}% / {_fmt(fund['profit_growth_pct'])}%",
        f"- 毛利/净利率: {_fmt(fund['gross_margin_pct'])}% / {_fmt(fund['net_margin_pct'])}%",
        f"- ROE/负债率: {_fmt(fund['roe_pct'])}% / {_fmt(fund['debt_ratio_pct'])}%",
        "",
        "## 技术面",
        f"- 趋势: {tech['trend']}  MA20/50/200: {tech['ma20']}/{tech['ma50']}/{tech['ma200']}",
        f"- RSI: {tech['rsi']}  MACD: {tech['macd']}  量比: {tech['volume_ratio']}",
        f"- 支撑/阻力: {tech['support']} / {tech['resistance']}",
        "",
        "## 风险分析",
        f"- 风险等级/风险分: {risk['level']} / {risk['score']}",
        f"- 风险因素: {', '.join(risk['factors']) or '无'}",
        "",
        "## 情绪分析",
        f"- 情绪分: {_fmt(stock['sentiment']['score'])}（新闻情绪: {stock['sentiment']['news']}）",
        "",
        "## 综合评分",
        f"- 基本面/技术面/风险安全/情绪: {_fmt(scores['fundamental'])} / {_fmt(scores['technical'])} / "
        f"{_fmt(scores['risk_safety'])} / {_fmt(scores['sentiment'])}",
        f"- 综合分: {scores['overall']}",
        "",
        "## 投资建议",
        f"- 建议: {rec['action']}（置信度: {rec['confidence']}）",
        f"- 目标价/止损: {rec['target_price']} / {rec['stop_loss']}",
        f"- 理由: {rec['reason']}",
        f"- 亮点: {', '.join(highlights['strengths']) or '无'}",
        "",
        "## 数据质量",
        f"- status: {data_quality['status']}  as_of: {data_quality['as_of']}",
        f"- sources: {', '.join(s.get('source', '') for s in data_quality['sources'] if s.get('source')) or '无'}",
        f"- notes: {data_quality['notes']}",
        "",
        "> 本报告由确定性指标与因子引擎生成，仅供参考，不构成投资建议。",
        "",
    ]
    return "\n".join(lines)


def _resolve_benchmark(
    base: Path,
    entries: List[Dict[str, Any]],
    as_of: str,
    offline: bool,
    source: str,
    config: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Load (or fetch) a real benchmark and compute its return to ``as_of``."""
    a_share = any(e["symbol"].endswith((".SH", ".SZ", ".BJ")) for e in entries)
    bt = (config or {}).get("backtest", {})
    symbol = bt.get("benchmark_symbol") or ("000300.SH" if a_share else "SPY")
    df = load_ohlcv(symbol, end=as_of, base_dir=base)
    if (df is None or len(df) < 2) and not offline:
        try:
            from .market_data import fetch_ohlcv

            fetched, used = fetch_ohlcv(symbol, source=source)
            save_ohlcv(
                fetched, symbol, source=used,
                note=f"real benchmark via {used}", base_dir=base,
            )
            df = load_ohlcv(symbol, end=as_of, base_dir=base)
        except Exception:  # noqa: BLE001
            return None
    if df is None or len(df) < 2:
        return None
    df = df[df["date"] <= pd.to_datetime(as_of)]
    if len(df) < 2:
        return None
    ret = float(df["close"].iloc[-1] / df["close"].iloc[0] - 1)
    meta = get_meta(symbol, base) or {}
    return {
        "symbol": parse_symbol(symbol)["canonical"],
        "source": meta.get("source") or "",
        "return": round(ret, 4),
        "as_of": str(df["date"].iloc[-1].date()),
        "excess_return": None,
    }


def run_pipeline(
    date_str: Optional[str] = None,
    symbols: Optional[List[str]] = None,
    base_dir: Optional[Path] = None,
    offline: bool = False,
    source: str = "auto",
    lookback: int = 400,
    mode: str = "all",
    config: Optional[Dict[str, Any]] = None,
    run_backtest: bool = True,
    universe: Optional[str] = None,
    portfolio_top_n: int = 5,
    portfolio_method: str = "score_weight",
) -> Dict[str, Any]:
    base = workspace_root(base_dir)
    date_str = date_str or _date.today().isoformat()
    market = market_describe(date_str)
    requested_as_of = market["as_of"]

    pool = _load_pool(base)
    if not symbols:
        symbols = list(pool.keys())
    if universe:
        members = load_universe(universe, date_str, base)
        if members is not None:
            allowed = set(members)
            symbols = [s for s in symbols if parse_symbol(s)["canonical"] in allowed]
    if not symbols:
        raise ValueError("no symbols: pass --symbols or configure stocks_pool.json")

    example = load_example(base)
    template_stock = example["stocks"][0]

    # 1) ensure data
    entries: List[Dict[str, Any]] = []
    errors: List[str] = []
    for raw in symbols:
        info = parse_symbol(raw)
        canonical = info["canonical"]
        df = None
        if mode == "fetch" or not offline:
            try:
                from .market_data import fetch_ohlcv  # lazy to avoid hard dep at import

                df, used = fetch_ohlcv(canonical, source=source)
                save_ohlcv(df, canonical, source=used, note=f"real market data via {used}", base_dir=base)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{canonical}: fetch failed ({type(exc).__name__})")
                df = None
        if df is None:
            df = load_ohlcv(canonical, base_dir=base)
        if df is None or len(df) < 30:
            errors.append(f"{canonical}: insufficient local data")
            continue
        df = df.tail(max(lookback, 60)).reset_index(drop=True)
        entries.append(
            {
                "symbol": canonical,
                "df": df,
                "meta": get_meta(canonical, base_dir=base) or {},
                "fundamentals": _load_fundamentals(base, canonical, as_of=date_str),
                "pool": pool.get(canonical, {}),
            }
        )

    if mode == "fetch":
        return {"date": date_str, "fetched": len(entries), "errors": errors}

    if not entries:
        raise ValueError(f"no usable data for {symbols}; errors={errors}")

    # as_of is the ACTUAL data cutoff (never claim a fresher date than the data)
    data_last = max(entry["df"]["date"].iloc[-1].date() for entry in entries)
    as_of = min(_date.fromisoformat(requested_as_of), data_last).isoformat()

    # 2) data quality (from the local store metadata)
    simulated = [e for e in entries if (e["meta"] or {}).get("is_simulated")]
    sources: List[Dict[str, Any]] = []
    seen_sources = set()
    for entry in entries:
        meta = entry["meta"] or {}
        src = meta.get("source")
        if not src:
            continue
        key = (src, bool(meta.get("is_simulated")))
        if key in seen_sources:
            continue
        seen_sources.add(key)
        sources.append(
            {
                "source": src,
                "is_simulated": bool(meta.get("is_simulated")),
                "retrieved_at": meta.get("retrieved_at"),
            }
        )
    if simulated and len(simulated) == len(entries):
        status = "simulated"
    elif simulated or errors:
        status = "partial"
    else:
        status = "real"
    quality_notes = list(errors)
    if simulated:
        quality_notes.append(f"{len(simulated)} 个标的的数据被标记为模拟，已禁止买入结论")
    gap_days = (_date.fromisoformat(requested_as_of) - data_last).days
    if gap_days > 3:
        quality_notes.append(f"数据截止 {data_last}，落后分析日 {gap_days} 天")
    data_quality = {
        "status": status,
        "as_of": as_of,
        "sources": sources,
        "notes": "；".join(quality_notes),
    }
    manifest_records = [
        {
            "symbol": entry["symbol"],
            "source": (entry["meta"] or {}).get("source"),
            "is_simulated": bool((entry["meta"] or {}).get("is_simulated")),
            "rows": (entry["meta"] or {}).get("rows"),
            "first_date": (entry["meta"] or {}).get("first_date"),
            "last_date": (entry["meta"] or {}).get("last_date"),
            "retrieved_at": (entry["meta"] or {}).get("retrieved_at"),
        }
        for entry in entries
    ]

    # 3) scores + payload (contract v2)
    payload = {
        "schema_version": "2.1.0",
        "metadata": {
            "analysis_date": date_str,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "generated_by": "QuanTr run_pipeline (deterministic v2)",
            "total_stocks": 0,
        },
        "summary": {},
        "data_quality": data_quality,
        "stocks": [],
    }

    backtests: List[Dict[str, Any]] = []
    ranking_rows: List[Dict[str, Any]] = []
    for entry in entries:
        allow_buy = status == "real" and entry["fundamentals"] is not None
        result = compute_scores(
            entry["df"],
            fundamentals=entry["fundamentals"],
            config=config,
            allow_buy=allow_buy,
        )
        stock = _build_stock(
            template_stock,
            entry["symbol"],
            entry["pool"],
            entry["df"],
            result,
            entry["fundamentals"],
            meta=entry["meta"],
        )
        payload["stocks"].append(stock)
        ranking_rows.append(
            {
                "symbol": entry["symbol"],
                "overall": result["overall"],
                "action": result["action"],
                "technical": result["subscores"]["technical"],
                "risk_level": result["risk"]["level"],
            }
        )
        if run_backtest:
            try:
                bt_cfg = (config or {}).get("backtest", {}).get("walk_forward", {})
                wf = walk_forward_ma(
                    entry["df"],
                    train_days=int(bt_cfg.get("train_days", 250)),
                    test_days=int(bt_cfg.get("test_days", 60)),
                    config=config,
                )
                if wf.get("window_count"):
                    backtests.append({"symbol": entry["symbol"], **wf})
            except Exception:  # noqa: BLE001
                pass

    _summary(payload)

    # cross-sectional ranking + portfolio + benchmark
    ranking = rank_scores(ranking_rows)
    payload["ranking"] = ranking
    bt_all = (config or {}).get("backtest", {})
    payload["portfolio"] = build_portfolio(
        ranking,
        method=portfolio_method,
        top_n=portfolio_top_n,
        max_position_ratio=float(bt_all.get("max_position_ratio", 0.8)),
    )
    benchmark = _resolve_benchmark(base, entries, as_of, offline, source, config)
    if benchmark:
        payload["benchmark"] = benchmark

    # 4) write outputs
    out_dir = base / "analysis_results" / date_str
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"stocks_analysis_{date_str}.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md_paths = []
    for stock in payload["stocks"]:
        info = stock["basic_info"]
        md_name = f"stock_{info['name']}_{info['code'].replace('.', '_')}_analysis_{date_str}.md"
        md_path = out_dir / md_name
        md_path.write_text(_md_report(stock, date_str, data_quality), encoding="utf-8")
        md_paths.append(str(md_path))

    write_manifest(date_str, records=manifest_records, base_dir=base, as_of=as_of)

    if backtests:
        report = base / "backtest_reports" / f"backtest_result_for_analysis_in_{date_str}.md"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(
            _backtest_md(date_str, backtests, data_quality, benchmark), encoding="utf-8"
        )
    else:
        report = None

    validation = validate_date(date_str, base_dir=base, strict=False, allow_v1=False)
    return {
        "date": date_str,
        "data_quality": data_quality,
        "symbols": [s["basic_info"]["code"] for s in payload["stocks"]],
        "ranking": ranking,
        "portfolio": payload["portfolio"],
        "benchmark": benchmark,
        "json": str(json_path),
        "markdown": md_paths,
        "backtest_report": str(report) if report else None,
        "backtests": backtests,
        "validation": validation,
        "errors": errors,
    }


def _backtest_md(
    date_str: str,
    backtests: List[Dict[str, Any]],
    data_quality: Dict[str, Any],
    benchmark: Optional[Dict[str, Any]] = None,
) -> str:
    lines = [
        f"# 策略回测报告 {date_str}",
        "",
        f"- 数据质量: {data_quality['status']}（as_of {data_quality['as_of']}）",
        "- 方法: 滚动走查 (walk-forward)，训练区间选 MA 参数，测试区间评估；计入成本。",
    ]
    if benchmark:
        lines.append(
            f"- 基准: {benchmark.get('symbol')} 区间收益 {benchmark.get('return')} "
            f"(as_of {benchmark.get('as_of')}, 来源 {benchmark.get('source')})"
        )
    lines.append("")
    for item in backtests:
        lines.append(f"## {item['symbol']}")
        lines.append(f"- 窗口数: {item['window_count']}，正收益窗口: {item['positive_windows']}")
        lines.append(f"- 平均窗口收益: {item['avg_return']}")
        for win in item.get("windows", []):
            lines.append(
                f"  - {win['window_start']}~{win['window_end']} MA({win['ma_fast']},{win['ma_slow']}) "
                f"ret={win['total_return']} sharpe={win['sharpe']} mdd={win['max_drawdown']}"
            )
        lines.append("")
    if data_quality["status"] != "real":
        lines.append("> 数据非全部真实，回测结论仅供参考，不代表可获得收益。")
    lines.append("")
    return "\n".join(lines)


def _load_config(base_dir: Optional[Path]) -> Optional[Dict[str, Any]]:
    import importlib.util

    root = workspace_root(base_dir)
    path = root / "config.py"
    if not path.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location("quantr_config", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.config.config
    except Exception:  # noqa: BLE001
        return None


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="QuanTr 可复现量化流水线")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD（默认今天）")
    parser.add_argument("--symbols", default=None, help="逗号分隔；默认读 stocks_pool.json")
    parser.add_argument("--pool", action="store_true", help="使用 stocks_pool.json")
    parser.add_argument("--offline", action="store_true", help="只读本地数据仓，不联网")
    parser.add_argument("--source", default="auto", choices=["auto", "akshare", "yfinance"])
    parser.add_argument("--lookback", type=int, default=400)
    parser.add_argument("--mode", default="all", choices=["all", "fetch", "analyze", "backtest"])
    parser.add_argument("--no-backtest", action="store_true")
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    symbols = [s.strip() for s in args.symbols.split(",")] if args.symbols else None
    base = Path(args.base_dir) if args.base_dir else None
    try:
        result = run_pipeline(
            date_str=args.date,
            symbols=symbols,
            base_dir=base,
            offline=args.offline,
            source=args.source,
            lookback=args.lookback,
            mode=args.mode,
            config=_load_config(base),
            run_backtest=(not args.no_backtest and args.mode in ("all", "backtest")),
        )
    except Exception as exc:  # noqa: BLE001
        print(f"❌ pipeline failed: {type(exc).__name__}: {exc}")
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        dq = result["data_quality"]
        print(f"✅ {result['date']} symbols={result['symbols']} data_status={dq['status']}")
        print(f"   json: {result['json']}")
        if result.get("validation"):
            v = result["validation"]
            print(f"   validation: {'OK' if v['ok'] else 'FAIL'} errors={len(v['errors'])} warnings={len(v['warnings'])}")
    return 0 if result.get("validation", {}).get("ok", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
