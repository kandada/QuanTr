"""Indicator golden tests vs independent reference implementations.

TA-Lib is not installed in this environment, so we compare against a separate
pandas/numpy reference implementation (independent code path) with tight
tolerances. If TA-Lib is later installed, it can be added as another oracle.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quantr import indicators  # noqa: E402


def make_ohlcv(n=240, seed=7):
    rng = np.random.default_rng(seed)
    x = np.arange(n)
    close = pd.Series(10 + np.sin(x / 7.0) * 1.5 + np.cumsum(rng.normal(0, 0.05, n)))
    return pd.DataFrame(
        {
            "date": pd.bdate_range("2023-01-02", periods=n),
            "open": close - 0.05,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "volume": rng.integers(100_000, 1_000_000, n).astype(float),
        }
    )


# ─── independent references ─────────────────────────────────────────────────


def ref_sma(s, n):
    return s.rolling(n, min_periods=n).mean()


def ref_ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def ref_rsi(s, n=14):
    delta = s.diff()
    up = delta.clip(lower=0)
    down = (-delta).clip(lower=0)
    au = up.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    ad = down.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = au / ad.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.where(ad != 0, 100.0).where(au.notna(), np.nan)


def ref_macd(s, fast=12, slow=26, signal=9):
    line = ref_ema(s, fast) - ref_ema(s, slow)
    sig = line.ewm(span=signal, adjust=False).mean()
    return line, sig, line - sig


def ref_bollinger(s, n=20, k=2.0):
    mid = ref_sma(s, n)
    std = s.rolling(n, min_periods=n).std(ddof=1)
    return mid, mid + k * std, mid - k * std


def ref_atr(df, n=14):
    high, low, close = df["high"], df["low"], df["close"]
    prev = close.shift(1)
    tr = pd.concat([high - low, (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def _assert_close(a, b, tol=1e-8):
    a, b = a.dropna(), b.dropna()
    idx = a.index.intersection(b.index)
    assert len(idx) > 20
    assert np.allclose(a.loc[idx].to_numpy(), b.loc[idx].to_numpy(), rtol=tol, atol=tol)


# ─── comparisons ────────────────────────────────────────────────────────────


def test_sma_parity():
    df = make_ohlcv()
    _assert_close(indicators.sma(df["close"], 20), ref_sma(df["close"], 20))


def test_ema_parity():
    df = make_ohlcv()
    _assert_close(indicators.ema(df["close"], 12), ref_ema(df["close"], 12))
    _assert_close(indicators.ema(df["close"], 26), ref_ema(df["close"], 26))


def test_rsi_parity():
    df = make_ohlcv()
    _assert_close(indicators.rsi(df["close"], 14), ref_rsi(df["close"], 14))


def test_macd_parity():
    df = make_ohlcv()
    ours = indicators.macd(df["close"])
    line, sig, hist = ref_macd(df["close"])
    _assert_close(ours["macd"], line)
    _assert_close(ours["signal"], sig)
    _assert_close(ours["hist"], hist)


def test_bollinger_parity():
    df = make_ohlcv()
    ours = indicators.bollinger(df["close"])
    mid, upper, lower = ref_bollinger(df["close"])
    _assert_close(ours["mid"], mid)
    _assert_close(ours["upper"], upper)
    _assert_close(ours["lower"], lower)


def test_atr_parity():
    df = make_ohlcv()
    _assert_close(indicators.atr(df, 14), ref_atr(df, 14))


def test_known_values_and_properties():
    df = make_ohlcv()
    close = df["close"]
    assert abs(indicators.sma(close, 3).iloc[-1] - close.iloc[-3:].mean()) < 1e-12

    up = pd.Series(np.linspace(1, 2, 100))
    assert indicators.rsi(up).dropna().iloc[-1] > 99.9  # pure uptrend -> ~100

    boll = pd.DataFrame(indicators.bollinger(close)).dropna()
    assert (boll["upper"] >= boll["mid"]).all()
    assert (boll["mid"] >= boll["lower"]).all()

    snap = indicators.compute_snapshot(df)
    assert snap["ma20"] == pytest.approx(round(indicators.sma(close, 20).iloc[-1], 3))
    assert 0 <= snap["rsi"] <= 100


def test_talib_if_available():
    try:
        import talib  # type: ignore
    except Exception:
        pytest.skip("TA-Lib not installed")
    df = make_ohlcv()
    _assert_close(indicators.sma(df["close"], 20), pd.Series(talib.SMA(df["close"], 20), index=df.index))
    _assert_close(indicators.rsi(df["close"], 14), pd.Series(talib.RSI(df["close"], 14), index=df.index), tol=1e-6)
