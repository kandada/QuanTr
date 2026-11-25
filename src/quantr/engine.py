# quan_tr/programs/backtesters/engine.py
"""严谨（够用）的向量化回测引擎。

特性：
- 基于真实 OHLCV；缺失即报错，不做任何模拟。
- 信号在 T 日产生、T+1 执行（避免前视偏差）。
- 计入佣金、滑点、卖出印花税、仓位上限。
- 输出标准绩效指标 + 交易明细；可选基准对比。
- 提供滚动窗口/走查（walk-forward）辅助，评估稳定性。

约定：position 取值 0（空仓）~1（满仓），按 ``max_position_ratio`` 缩放。
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union

import numpy as np
import pandas as pd

_UTILS = Path(__file__).resolve().parents[1] / "utils"
if str(_UTILS) not in sys.path:
    sys.path.insert(0, str(_UTILS))

from .data_store import load_ohlcv  # noqa: E402
from .schema import parse_symbol  # noqa: E402

TRADING_DAYS = 252
BUY = {"buy", "strong_buy"}
SELL = {"sell", "strong_sell"}


def _config_backtest(config: Optional[Dict[str, Any]]) -> Dict[str, float]:
    bt = (config or {}).get("backtest", {}) if config else {}
    return {
        "initial_capital": float(bt.get("initial_capital", 100000)),
        "commission_rate": float(bt.get("commission_rate", 0.0003)),
        "slippage_rate": float(bt.get("slippage_rate", 0.0001)),
        "stamp_duty_rate": float(bt.get("stamp_duty_rate", 0.0005)),
        "max_position_ratio": float(bt.get("max_position_ratio", 0.8)),
    }


def _normalize_action(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().lower()
    aliases = {
        "买入": "buy",
        "增持": "buy",
        "卖出": "sell",
        "减持": "sell",
        "持有": "hold",
        "观望": "hold",
        "强烈买入": "strong_buy",
        "强烈卖出": "strong_sell",
    }
    return aliases.get(text, text)


def signals_to_target(
    prices: pd.DataFrame, signals: Union[Dict[Any, str], pd.Series, pd.DataFrame]
) -> pd.Series:
    """Convert recommendation actions into a target position series (0/1)."""
    dates = pd.to_datetime(prices["date"]).dt.normalize()
    actions: Dict[pd.Timestamp, Optional[str]] = {}

    if isinstance(signals, pd.DataFrame):
        frame = signals.copy()
        if "date" in frame.columns:
            for _, row in frame.iterrows():
                actions[pd.Timestamp(row["date"]).normalize()] = _normalize_action(
                    row.get("action")
                )
        else:
            for idx, row in frame.iterrows():
                actions[pd.Timestamp(idx).normalize()] = _normalize_action(
                    row.get("action")
                )
    elif isinstance(signals, pd.Series):
        for idx, value in signals.items():
            actions[pd.Timestamp(idx).normalize()] = _normalize_action(value)
    elif isinstance(signals, dict):
        for key, value in signals.items():
            actions[pd.Timestamp(key).normalize()] = _normalize_action(value)
    else:
        raise TypeError("signals must be dict, Series or DataFrame")

    targets: List[float] = []
    current = 0.0
    for day in dates:
        action = actions.get(day)
        if action in BUY:
            current = 1.0
        elif action in SELL:
            current = 0.0
        # hold / missing -> keep current
        targets.append(current)
    return pd.Series(targets, index=dates, name="target")


def run_backtest(
    prices: pd.DataFrame,
    signals: Union[Dict[Any, str], pd.Series, pd.DataFrame],
    config: Optional[Dict[str, Any]] = None,
    benchmark: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """Run a long/flat backtest. Returns ``{metrics, trades, equity_curve}``."""
    if prices is None or len(prices) < 2:
        raise ValueError("backtest requires at least 2 price rows (real data only)")

    frame = prices.sort_values("date").reset_index(drop=True).copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    cfg = _config_backtest(config)
    ratio = max(0.0, min(1.0, cfg["max_position_ratio"]))

    target = signals_to_target(frame, signals).reset_index(drop=True) * ratio
    pos = target.shift(1).fillna(0.0)  # execute next day
    ret = frame["close"].pct_change().fillna(0.0)
    dpos = pos.diff().fillna(pos)

    cost = (
        dpos.abs() * (cfg["commission_rate"] + cfg["slippage_rate"])
        + (-dpos).clip(lower=0) * cfg["stamp_duty_rate"]
    )
    strat_ret = pos * ret - cost
    equity = (1 + strat_ret).cumprod() * cfg["initial_capital"]

    metrics = _metrics(frame["close"], strat_ret, equity, pos, cfg["initial_capital"])
    trades = _extract_trades(frame, target, cfg)
    metrics.update(_trade_stats(trades))

    if benchmark is not None and len(benchmark) >= 2:
        bench = _benchmark_metrics(frame, benchmark, cfg["initial_capital"], metrics["total_return"])
        metrics.update(bench)

    curve = [
        {"date": str(d.date()), "equity": round(float(e), 2)}
        for d, e in zip(frame["date"], equity)
    ]
    return {"metrics": metrics, "trades": trades, "equity_curve": curve}


def _metrics(
    close: pd.Series, strat_ret: pd.Series, equity: pd.Series, pos: pd.Series, initial: float
) -> Dict[str, Any]:
    total = float(equity.iloc[-1] / initial - 1)
    n = len(strat_ret)
    years = n / TRADING_DAYS if n else 0
    cagr = float((1 + total) ** (1 / years) - 1) if years > 0 and (1 + total) > 0 else -1.0

    mean = float(strat_ret.mean())
    std = float(strat_ret.std(ddof=0))
    sharpe = float(mean / std * math.sqrt(TRADING_DAYS)) if std > 0 else 0.0
    downside = strat_ret[strat_ret < 0]
    dstd = float(downside.std(ddof=0)) if len(downside) > 1 else 0.0
    sortino = float(mean / dstd * math.sqrt(TRADING_DAYS)) if dstd > 0 else 0.0

    running_peak = equity.cummax()
    drawdown = equity / running_peak - 1
    max_dd = float(drawdown.min())
    calmar = float(cagr / abs(max_dd)) if max_dd < 0 else 0.0

    return {
        "bars": int(n),
        "total_return": round(total, 4),
        "cagr": round(cagr, 4),
        "sharpe": round(sharpe, 3),
        "sortino": round(sortino, 3),
        "max_drawdown": round(max_dd, 4),
        "calmar": round(calmar, 3),
        "exposure": round(float((pos > 0).mean()), 3),
        "volatility_annual": round(float(strat_ret.std(ddof=0) * math.sqrt(TRADING_DAYS)), 4),
    }


def _extract_trades(frame: pd.DataFrame, target: pd.Series, cfg: Dict[str, float]) -> List[Dict[str, Any]]:
    """Build round-trip trades using next-open execution and open prices."""
    trades: List[Dict[str, Any]] = []
    dates = frame["date"].tolist()
    opens = frame["open"].tolist()
    in_pos = 0.0
    entry_i: Optional[int] = None
    for i, t in enumerate(target.tolist()):
        if t > 0 and in_pos == 0.0:
            # execute at next day open
            exec_i = min(i + 1, len(frame) - 1)
            entry_i = exec_i
            in_pos = t
        elif t == 0 and in_pos > 0.0 and entry_i is not None:
            exec_i = min(i + 1, len(frame) - 1)
            entry_price = opens[entry_i]
            exit_price = opens[exec_i]
            gross = exit_price / entry_price - 1 if entry_price else 0.0
            cost = (
                cfg["commission_rate"] * 2
                + cfg["slippage_rate"] * 2
                + cfg["stamp_duty_rate"]
            )
            trades.append(
                {
                    "entry_date": str(dates[entry_i].date()),
                    "exit_date": str(dates[exec_i].date()),
                    "entry_price": round(float(entry_price), 4),
                    "exit_price": round(float(exit_price), 4),
                    "return": round(gross - cost, 4),
                    "holding_bars": int(exec_i - entry_i),
                }
            )
            in_pos = 0.0
            entry_i = None

    # Force-close any open position at the final bar (mark-to-market) so that a
    # pure buy-and-hold still reports one round-trip trade.
    if in_pos > 0.0 and entry_i is not None and entry_i < len(frame):
        exit_i = len(frame) - 1
        entry_price = opens[entry_i]
        exit_price = opens[exit_i]
        gross = exit_price / entry_price - 1 if entry_price else 0.0
        cost = (
            cfg["commission_rate"] * 2
            + cfg["slippage_rate"] * 2
            + cfg["stamp_duty_rate"]
        )
        trades.append(
            {
                "entry_date": str(dates[entry_i].date()),
                "exit_date": str(dates[exit_i].date()),
                "entry_price": round(float(entry_price), 4),
                "exit_price": round(float(exit_price), 4),
                "return": round(gross - cost, 4),
                "holding_bars": int(exit_i - entry_i),
                "open_at_end": True,
            }
        )
    return trades


def _trade_stats(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not trades:
        return {"trades": 0, "win_rate": 0.0, "profit_factor": 0.0, "avg_holding_bars": 0.0}
    returns = [t["return"] for t in trades]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r < 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    return {
        "trades": len(trades),
        "win_rate": round(len(wins) / len(trades), 3),
        "profit_factor": round(gross_win / gross_loss, 3) if gross_loss > 0 else float(len(wins) > 0),
        "avg_holding_bars": round(float(np.mean([t["holding_bars"] for t in trades])), 2),
    }


def _benchmark_metrics(
    frame: pd.DataFrame, benchmark: pd.DataFrame, initial: float, strat_return: float
) -> Dict[str, Any]:
    bench = benchmark.copy()
    bench["date"] = pd.to_datetime(bench["date"]).dt.normalize()
    merged = frame[["date"]].merge(bench[["date", "close"]], on="date", how="inner")
    if len(merged) < 2:
        return {"benchmark_return": None, "excess_return": None}
    bench_return = float(merged["close"].iloc[-1] / merged["close"].iloc[0] - 1)
    return {
        "benchmark_return": round(bench_return, 4),
        "excess_return": round(strat_return - bench_return, 4),
    }


def walk_forward_ma(
    prices: pd.DataFrame,
    train_days: int = 250,
    test_days: int = 60,
    grid: Optional[List[tuple]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Walk-forward: pick MA(fast,slow) on train, evaluate on next test window.

    Not a full research framework, but demonstrates out-of-sample discipline.
    """
    frame = prices.sort_values("date").reset_index(drop=True).copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    grid = grid or [(5, 20), (10, 50), (20, 60)]
    windows: List[Dict[str, Any]] = []
    start = 0
    while start + train_days + test_days <= len(frame):
        train = frame.iloc[start : start + train_days]
        test = frame.iloc[start + train_days : start + train_days + test_days]
        best = None
        for fast, slow in grid:
            signals = _ma_signals(train, fast, slow)
            try:
                res = run_backtest(train, signals, config)
            except ValueError:
                continue
            score = res["metrics"]["sharpe"]
            if best is None or score > best[0]:
                best = (score, fast, slow)
        if best is None:
            start += test_days
            continue
        _, fast, slow = best
        combined = pd.concat([train, test])
        full_signals = _ma_signals(combined, fast, slow)
        test_dates = pd.to_datetime(test["date"]).dt.normalize().values
        test_signals = full_signals.reindex(test_dates, fill_value="hold")
        res = run_backtest(test, test_signals, config)
        windows.append(
            {
                "window_start": str(test["date"].iloc[0].date()),
                "window_end": str(test["date"].iloc[-1].date()),
                "ma_fast": fast,
                "ma_slow": slow,
                "total_return": res["metrics"]["total_return"],
                "sharpe": res["metrics"]["sharpe"],
                "max_drawdown": res["metrics"]["max_drawdown"],
            }
        )
        start += test_days

    returns = [w["total_return"] for w in windows]
    return {
        "windows": windows,
        "window_count": len(windows),
        "positive_windows": sum(1 for r in returns if r > 0),
        "avg_return": round(float(np.mean(returns)), 4) if returns else 0.0,
    }


def _ma_signals(frame: pd.DataFrame, fast: int, slow: int) -> pd.Series:
    close = frame["close"]
    fast_ma = close.rolling(fast, min_periods=fast).mean()
    slow_ma = close.rolling(slow, min_periods=slow).mean()
    actions = []
    for i in range(len(frame)):
        if pd.isna(fast_ma.iloc[i]) or pd.isna(slow_ma.iloc[i]):
            actions.append("hold")
        elif fast_ma.iloc[i] > slow_ma.iloc[i]:
            actions.append("buy")
        else:
            actions.append("sell")
    dates = pd.to_datetime(frame["date"]).dt.normalize().values
    return pd.Series(actions, index=dates)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="QuanTr 回测引擎（真实数据）")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--start", default=None)
    parser.add_argument("--end", default=None)
    parser.add_argument("--signals", default=None, help="JSON 文件：{date: action}")
    parser.add_argument("--walk-forward", action="store_true")
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    base = Path(args.base_dir) if args.base_dir else None
    prices = load_ohlcv(args.symbol, args.start, args.end, base_dir=base)
    if prices is None or len(prices) < 2:
        print(f"❌ 本地无足够数据: {args.symbol}")
        return 1

    if args.walk_forward:
        result = walk_forward_ma(prices)
    else:
        if not args.signals:
            parser.error("provide --signals JSON or --walk-forward")
        signals = json.loads(Path(args.signals).read_text(encoding="utf-8"))
        result = run_backtest(prices, signals)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        metrics = result.get("metrics", result)
        print(f"{parse_symbol(args.symbol)['canonical']} {metrics}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
