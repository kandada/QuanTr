"""Domain tests for the deterministic quant engine.

These use synthetic price series **as test fixtures only** (production code never
fabricates data). They verify indicators, schema, store, factors, backtest
metrics, and the offline pipeline end-to-end.
"""

import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

QUANTR = Path(__file__).resolve().parent.parent / "examples" / "workspace"
SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quantr import schema, indicators, data_store, factor_engine, engine, run_pipeline  # noqa: E402


# ─── fixtures ───────────────────────────────────────────────────────────────


def make_prices(start=10.0, end=17.0, n=300, wave=0.15, seed=0):
    dates = pd.bdate_range("2024-01-01", periods=n)
    x = np.arange(n)
    close = pd.Series(np.linspace(start, end, n) + np.sin(x / 9 + seed) * wave)
    return schema.normalize_ohlcv(
        pd.DataFrame(
            {
                "date": dates,
                "open": close * 0.998,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": np.full(n, 1_000_000),
            }
        )
    )


# ─── schema ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("000001.SZ", "000001.SZ"),
        ("000001_SZ", "000001.SZ"),
        ("600000", "600000.SH"),
        ("sh600000", "600000.SH"),
        ("300750", "300750.SZ"),
        ("0700.HK", "0700.HK"),
        ("AAPL", "AAPL"),
    ],
)
def test_parse_symbol(raw, expected):
    info = schema.parse_symbol(raw)
    assert info["canonical"] == expected
    assert info["market"] in {"SH", "SZ", "BJ", "HK", "US"}


def test_normalize_and_validate():
    df = make_prices()
    ok, errors = schema.validate_ohlcv(df)
    assert ok, errors
    assert list(df.columns[:6]) == ["date", "open", "high", "low", "close", "volume"]
    assert df["date"].is_monotonic_increasing
    assert not df["date"].duplicated().any()


def test_normalize_rejects_missing_columns():
    with pytest.raises(ValueError):
        schema.normalize_ohlcv(pd.DataFrame({"foo": [1], "bar": [2]}))


def test_validate_flags_high_below_low():
    df = make_prices().copy()
    df.loc[0, "high"] = df.loc[0, "low"] - 1
    ok, errors = schema.validate_ohlcv(df)
    assert not ok
    assert any("high < low" in e for e in errors)


# ─── indicators ─────────────────────────────────────────────────────────────


def test_sma_matches_rolling_mean():
    df = make_prices()
    sma20 = indicators.sma(df["close"], 20)
    expected = df["close"].rolling(20).mean()
    pd.testing.assert_series_equal(sma20, expected, check_names=False)


def test_rsi_bounds_and_direction():
    up = pd.Series(np.linspace(1, 2, 100))
    down = pd.Series(np.linspace(2, 1, 100))
    up_rsi = indicators.rsi(up).dropna().iloc[-1]
    down_rsi = indicators.rsi(down).dropna().iloc[-1]
    assert 0 <= down_rsi <= 100 and 0 <= up_rsi <= 100
    assert up_rsi > 70
    assert down_rsi < 30


def test_snapshot_fields():
    snap = indicators.compute_snapshot(make_prices())
    for key in (
        "ma20", "ma50", "ma200", "rsi", "macd", "volume_ratio",
        "support", "resistance", "trend", "atr", "max_drawdown",
    ):
        assert key in snap
    assert snap["trend"] == "up"
    assert snap["support"] <= snap["resistance"]


# ─── data store ─────────────────────────────────────────────────────────────


def test_store_roundtrip_and_merge(tmp_path):
    df = make_prices(n=100)
    rec = data_store.save_ohlcv(
        df, "000001.SZ", source="akshare", note="real fixture", base_dir=tmp_path, merge=False
    )
    assert rec["rows"] == 100
    loaded = data_store.load_ohlcv("000001.SZ", base_dir=tmp_path)
    assert loaded is not None and len(loaded) == 100
    meta = data_store.get_meta("000001.SZ", base_dir=tmp_path)
    assert meta["is_simulated"] is False
    assert "000001.SZ" in data_store.list_symbols(base_dir=tmp_path)

    # merge newer rows, dedupe by date
    df2 = make_prices(n=105)
    data_store.save_ohlcv(df2, "000001.SZ", source="akshare", note="real", base_dir=tmp_path, merge=True)
    merged = data_store.load_ohlcv("000001.SZ", base_dir=tmp_path)
    assert len(merged) == 105


def test_store_marks_simulated(tmp_path):
    data_store.save_ohlcv(
        make_prices(n=60), "000001.SZ", source="internal", note="模拟数据", base_dir=tmp_path, merge=False
    )
    meta = data_store.get_meta("000001.SZ", base_dir=tmp_path)
    assert meta["is_simulated"] is True


# ─── source adapters (pure mapping, no network) ─────────────────────────────


def test_akshare_adapter_maps_chinese_columns():
    from quantr import market_data

    raw = pd.DataFrame(
        {
            "日期": pd.bdate_range("2024-01-01", periods=5),
            "开盘": [10, 10.1, 10.2, 10.3, 10.4],
            "收盘": [10.1, 10.2, 10.3, 10.4, 10.5],
            "最高": [10.2, 10.3, 10.4, 10.5, 10.6],
            "最低": [9.9, 10.0, 10.1, 10.2, 10.3],
            "成交量": [1000, 1100, 1200, 1300, 1400],
            "成交额": [10000, 11000, 12000, 13000, 14000],
        }
    )
    df = market_data._akshare_to_canonical(raw)
    assert list(df.columns[:6]) == ["date", "open", "high", "low", "close", "volume"]
    assert len(df) == 5


def test_yfinance_adapter_handles_multiindex():
    from quantr import market_data

    dates = pd.bdate_range("2024-01-01", periods=5)
    cols = pd.MultiIndex.from_product(
        [["Open", "High", "Low", "Close", "Volume"], ["AAPL"]]
    )
    raw = pd.DataFrame([[10, 10.2, 9.9, 10.1, 1000]] * 5, index=dates, columns=cols)
    df = market_data._yfinance_to_canonical(raw)
    assert list(df.columns[:6]) == ["date", "open", "high", "low", "close", "volume"]
    assert len(df) == 5


# ─── factor engine ──────────────────────────────────────────────────────────


def test_factor_scores_and_allow_buy():
    up = make_prices(start=10, end=20, seed=0)
    down = make_prices(start=20, end=10, seed=3)
    up_res = factor_engine.compute_scores(up, config=None, allow_buy=True)
    down_res = factor_engine.compute_scores(down, config=None, allow_buy=True)
    assert up_res["subscores"]["technical"] > down_res["subscores"]["technical"]
    assert 0 <= up_res["overall"] <= 100
    assert up_res["risk"]["score"] + up_res["risk"]["safety"] == pytest.approx(100, abs=0.05)

    capped = factor_engine.compute_scores(up, config=None, allow_buy=False)
    assert capped["action"] not in {"buy", "strong_buy"}


def test_rank_universe_order():
    items = {
        "000001.SZ": {"df": make_prices(start=10, end=20)},
        "600000.SH": {"df": make_prices(start=20, end=10, seed=3)},
    }
    ranked = factor_engine.rank_universe(items, config=None, allow_buy=True)
    assert ranked[0]["rank"] == 1
    assert ranked[0]["overall"] >= ranked[1]["overall"]


# ─── backtest engine ────────────────────────────────────────────────────────


def test_backtest_buy_and_hold_positive():
    df = make_prices()
    signals = {str(df["date"].iloc[0].date()): "buy"}
    result = engine.run_backtest(df, signals)
    metrics = result["metrics"]
    assert metrics["total_return"] > 0
    assert metrics["trades"] >= 1
    assert metrics["max_drawdown"] <= 0
    assert len(result["equity_curve"]) == len(df)


def test_backtest_costs_reduce_return():
    df = make_prices()
    signals = {str(df["date"].iloc[0].date()): "buy"}
    free = engine.run_backtest(df, signals, {"backtest": {"commission_rate": 0, "slippage_rate": 0, "stamp_duty_rate": 0}})
    costly = engine.run_backtest(df, signals, {"backtest": {"commission_rate": 0.01, "slippage_rate": 0.005, "stamp_duty_rate": 0.01}})
    assert free["metrics"]["total_return"] > costly["metrics"]["total_return"]


def test_walk_forward_runs():
    df = make_prices(n=300)
    result = engine.walk_forward_ma(df, train_days=120, test_days=60)
    assert result["window_count"] >= 1
    assert result["positive_windows"] <= result["window_count"]


def test_backtest_requires_data():
    with pytest.raises(ValueError):
        engine.run_backtest(pd.DataFrame(), {"x": "buy"})


# ─── pipeline (offline, real fixture) ───────────────────────────────────────


def _seed_base(tmp_path):
    tdir = tmp_path / "analysis_results" / "templates"
    tdir.mkdir(parents=True)
    for name in (
        "stocks_analysis.schema.json",
        "stocks_analysis.example.json",
        "stocks_analysis_template.json",
    ):
        shutil.copy(QUANTR / "analysis_results" / "templates" / name, tdir / name)


def test_pipeline_offline_real(tmp_path):
    _seed_base(tmp_path)
    data_store.save_ohlcv(
        make_prices(n=320), "000001.SZ", source="akshare", note="real fixture",
        base_dir=tmp_path, merge=False,
    )
    out = run_pipeline.run_pipeline(
        date_str="2026-11-24", symbols=["000001.SZ"], base_dir=tmp_path, offline=True
    )
    assert out["data_quality"]["status"] == "real"
    assert out["validation"]["ok"] is True, out["validation"]["errors"]
    payload = json.loads(Path(out["json"]).read_text(encoding="utf-8"))
    assert payload["schema_version"] == "2.1.0"
    assert payload["stocks"][0]["basic_info"]["code"] == "000001.SZ"
    assert payload["stocks"][0]["basic_info"]["market"] == "SZ"
    assert payload["data_quality"]["status"] == "real"
    md = Path(out["markdown"][0]).read_text(encoding="utf-8")
    for section in ("基本信息", "价格", "基本面", "技术面", "风险", "投资建议"):
        assert section in md
    assert (tmp_path / "data_files" / "2026-11-24" / "manifest.json").exists()


def test_pipeline_simulated_caps_buy(tmp_path):
    _seed_base(tmp_path)
    data_store.save_ohlcv(
        make_prices(start=10, end=20), "000001.SZ", source="internal",
        note="模拟数据", base_dir=tmp_path, merge=False,
    )
    out = run_pipeline.run_pipeline(
        date_str="2026-11-24", symbols=["000001.SZ"], base_dir=tmp_path, offline=True
    )
    assert out["data_quality"]["status"] == "simulated"
    payload = json.loads(Path(out["json"]).read_text(encoding="utf-8"))
    actions = {s["recommendation"]["action"] for s in payload["stocks"]}
    assert not (actions & {"buy", "strong_buy"})


# ─── sanitation: production code must not fabricate data ────────────────────


def test_production_modules_have_no_random_generation():
    modules = [
        SRC / "quantr" / "market_data.py",
        SRC / "quantr" / "factor_engine.py",
        SRC / "quantr" / "engine.py",
        SRC / "quantr" / "data_store.py",
        SRC / "quantr" / "indicators.py",
    ]
    for path in modules:
        text = path.read_text(encoding="utf-8")
        assert "import random" not in text, path
        assert "np.random" not in text, path
        assert "random." not in text, path
