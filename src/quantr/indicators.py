# src/quantr/indicators.py
"""Deterministic technical indicators (pandas/numpy only).

这些指标是纯代码计算，结果可复现、可单测；LLM 不应自行“估”数值。

提供常用指标以及 ``compute_snapshot``（一次算出报告所需的全部技术面数值）。
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def _last(series: pd.Series, digits: int = 4) -> Optional[float]:
    if series is None or len(series) == 0:
        return None
    value = series.iloc[-1]
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return round(float(value), digits)


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(100.0).where(avg_gain.notna(), np.nan)


def macd(
    series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> Dict[str, pd.Series]:
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return {
        "macd": macd_line,
        "signal": signal_line,
        "hist": macd_line - signal_line,
    }


def bollinger(series: pd.Series, period: int = 20, k: float = 2.0) -> Dict[str, pd.Series]:
    mid = sma(series, period)
    std = series.rolling(window=period, min_periods=period).std()
    return {"mid": mid, "upper": mid + k * std, "lower": mid - k * std}


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def obv(df: pd.DataFrame) -> pd.Series:
    direction = np.sign(df["close"].diff()).fillna(0.0)
    return (direction * df["volume"]).cumsum()


def volume_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
    base = volume.rolling(window=period, min_periods=1).mean()
    return volume / base.replace(0, np.nan)


def daily_returns(close: pd.Series) -> pd.Series:
    return close.pct_change().fillna(0.0)


def annualized_volatility(returns: pd.Series, periods: int = TRADING_DAYS) -> pd.Series:
    return returns.rolling(window=periods, min_periods=20).std() * math.sqrt(periods)


def momentum(close: pd.Series, period: int) -> pd.Series:
    return close / close.shift(period) - 1.0


def drawdown_series(close: pd.Series) -> pd.Series:
    peak = close.cummax()
    return close / peak - 1.0


def max_drawdown(close: pd.Series) -> float:
    if close is None or len(close) == 0:
        return 0.0
    return float(drawdown_series(close).min())


def support_resistance(df: pd.DataFrame, period: int = 20) -> Dict[str, float]:
    window = min(period, len(df))
    if window < 1:
        return {"support": None, "resistance": None}
    support = float(df["low"].tail(window).min())
    resistance = float(df["high"].tail(window).max())
    return {"support": round(support, 4), "resistance": round(resistance, 4)}


def classify_trend(close: pd.Series, ma20: pd.Series, ma50: pd.Series) -> str:
    price = _last(close)
    short = _last(ma20)
    long = _last(ma50)
    if price is None or short is None or long is None:
        return "sideways"
    if price > short > long:
        return "up"
    if price < short < long:
        return "down"
    return "sideways"


def compute_snapshot(df: pd.DataFrame, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Compute the latest technical snapshot used to fill analysis reports.

    ``df`` must be a canonical OHLCV frame (see ``schema.normalize_ohlcv``).
    """
    cfg = (config or {}).get("technical_analysis", {}) if config else {}
    ma_periods = cfg.get("ma_periods", [20, 50, 200])
    rsi_period = int(cfg.get("rsi_period", 14))
    macd_fast = int(cfg.get("macd_fast", 12))
    macd_slow = int(cfg.get("macd_slow", 26))
    macd_signal = int(cfg.get("macd_signal", 9))

    close = df["close"]
    ma = {n: sma(close, int(n)) for n in ma_periods}
    macd_parts = macd(close, macd_fast, macd_slow, macd_signal)
    atr_series = atr(df, 14)
    returns = daily_returns(close)
    vol_series = annualized_volatility(returns)
    sr = support_resistance(df, 20)

    snapshot: Dict[str, Any] = {
        "close": _last(close, 3),
        "ma20": _last(ma.get(20, sma(close, 20)), 3),
        "ma50": _last(ma.get(50, sma(close, 50)), 3),
        "ma200": _last(ma.get(200, sma(close, 200)), 3),
        "rsi": _last(rsi(close, rsi_period), 2),
        "macd": _last(macd_parts["macd"], 4),
        "macd_signal": _last(macd_parts["signal"], 4),
        "macd_hist": _last(macd_parts["hist"], 4),
        "volume_ratio": _last(volume_ratio(df["volume"], 20), 3),
        "support": sr["support"],
        "resistance": sr["resistance"],
        "trend": classify_trend(close, ma.get(20), ma.get(50)),
        "atr": _last(atr_series, 3),
        "volatility_annual": _last(vol_series, 4),
        "max_drawdown": round(max_drawdown(close), 4),
        "momentum_20": _last(momentum(close, 20), 4),
        "momentum_60": _last(momentum(close, 60), 4),
        "last_date": str(df["date"].iloc[-1].date()) if len(df) else None,
        "bars": int(len(df)),
    }
    return snapshot
