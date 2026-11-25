"""PIT data store, universe membership, ranking/portfolio wiring tests."""

import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
QUANTR = ROOT / "quan_tr"
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quantr import schema, data_store, universe, portfolio, run_pipeline  # noqa: E402

TEMPLATES = (
    "stocks_analysis.schema.json",
    "stocks_analysis.example.json",
    "stocks_analysis_template.json",
)


def prices(n=320, start=10.0, end=18.0, seed=0):
    x = np.arange(n)
    close = pd.Series(np.linspace(start, end, n) + np.sin(x / 9 + seed) * 0.2)
    return schema.normalize_ohlcv(
        pd.DataFrame(
            {
                "date": pd.bdate_range("2024-01-01", periods=n),
                "open": close * 0.998,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": np.full(n, 1_000_000),
            }
        )
    )


def seed_templates(base: Path):
    tdir = base / "analysis_results" / "templates"
    tdir.mkdir(parents=True, exist_ok=True)
    for name in TEMPLATES:
        shutil.copy(QUANTR / "analysis_results" / "templates" / name, tdir / name)


# ─── PIT OHLCV ──────────────────────────────────────────────────────────────


def test_ohlcv_pit_multiversion(tmp_path):
    df = prices(n=20)
    data_store.save_ohlcv(
        df, "000001.SZ", "akshare", "real", base_dir=tmp_path,
        retrieved_at="2024-02-01T00:00:00", merge=False,
    )
    revised = df.copy()
    revised["close"] = revised["close"] + 100
    data_store.save_ohlcv(
        revised, "000001.SZ", "akshare", "real", base_dir=tmp_path,
        retrieved_at="2024-03-01T00:00:00", merge=True,
    )

    latest = data_store.load_ohlcv("000001.SZ", base_dir=tmp_path)
    old = data_store.load_ohlcv("000001.SZ", base_dir=tmp_path, ingest_as_of="2024-02-15T00:00:00")
    assert len(latest) == 20 and len(old) == 20
    assert latest["close"].iloc[0] == pytest.approx(old["close"].iloc[0] + 100)
    meta = data_store.get_meta("000001.SZ", base_dir=tmp_path)
    assert meta["storage"] == "parquet"
    assert meta["versions"] == 40  # 20 dates x 2 ingest versions


def test_fundamentals_pit(tmp_path):
    data_store.save_fundamentals(
        "000001.SZ", {"pe": 10, "roe": 8}, "2023-12-31", "2024-03-15",
        source="akshare", base_dir=tmp_path,
    )
    data_store.save_fundamentals(
        "000001.SZ", {"pe": 20, "roe": 9}, "2024-03-31", "2024-04-30",
        source="akshare", base_dir=tmp_path,
    )
    before = data_store.load_fundamentals("000001.SZ", as_of="2024-04-01", base_dir=tmp_path)
    after = data_store.load_fundamentals("000001.SZ", as_of="2024-05-01", base_dir=tmp_path)
    assert before["pe"] == 10
    assert after["pe"] == 20
    assert before["announce_date"] == "2024-03-15"


# ─── universe ───────────────────────────────────────────────────────────────


def test_load_universe_pit(tmp_path):
    universe.save_universe(
        [
            {"symbol": "000001.SZ", "start_date": "2020-01-01", "end_date": ""},
            {"symbol": "600000.SH", "start_date": "2020-01-01", "end_date": "2023-12-31"},
        ],
        "test_index",
        base_dir=tmp_path,
    )
    assert universe.load_universe("test_index", "2022-06-01", tmp_path) == ["000001.SZ", "600000.SH"]
    assert universe.load_universe("test_index", "2024-06-01", tmp_path) == ["000001.SZ"]
    assert universe.load_universe("missing", "2024-06-01", tmp_path) is None


# ─── portfolio ──────────────────────────────────────────────────────────────


def test_build_portfolio_score_and_equal():
    ranking = [
        {"symbol": "A", "overall": 80, "action": "buy"},
        {"symbol": "B", "overall": 70, "action": "hold"},
        {"symbol": "C", "overall": 30, "action": "sell"},
    ]
    sw = portfolio.build_portfolio(ranking, method="score_weight", top_n=5, max_position_ratio=0.8)
    assert [c["symbol"] for c in sw["constituents"]] == ["A", "B"]  # C excluded (sell)
    assert sw["invested_weight"] == pytest.approx(0.8, abs=1e-3)
    assert sw["cash_weight"] == pytest.approx(0.2, abs=1e-3)
    assert sw["constituents"][0]["weight"] > sw["constituents"][1]["weight"]

    ew = portfolio.build_portfolio(ranking, method="equal_weight", top_n=2, max_position_ratio=0.6)
    assert [c["weight"] for c in ew["constituents"]] == [0.3, 0.3]
    assert ew["invested_weight"] == pytest.approx(0.6)


# ─── pipeline wiring: ranking + portfolio + benchmark + universe ────────────


def _seed_market(base: Path):
    seed_templates(base)
    data_store.save_ohlcv(prices(start=10, end=20), "000001.SZ", "akshare", "real",
                          base_dir=base, merge=False)
    data_store.save_ohlcv(prices(start=20, end=12, seed=3), "600000.SH", "akshare", "real",
                          base_dir=base, merge=False)
    # benchmark (CSI300) so pipeline can attach it offline
    data_store.save_ohlcv(prices(start=100, end=110, seed=5), "000300.SH", "akshare", "real",
                          base_dir=base, merge=False)


def test_pipeline_ranking_portfolio_benchmark(tmp_path):
    _seed_market(tmp_path)
    out = run_pipeline.run_pipeline(
        date_str="2026-11-24",
        symbols=["000001.SZ", "600000.SH"],
        base_dir=tmp_path,
        offline=True,
    )
    payload = json.loads(Path(out["json"]).read_text(encoding="utf-8"))
    assert payload["schema_version"] == "2.1.0"
    assert out["validation"]["ok"] is True, out["validation"]["errors"]

    ranking = payload["ranking"]
    assert len(ranking) == 2
    assert [r["rank"] for r in ranking] == [1, 2]
    assert ranking[0]["overall"] >= ranking[1]["overall"]

    pf = payload["portfolio"]
    assert pf["constituents"]
    assert pf["invested_weight"] <= 0.8001
    assert pf["constituents"][0]["symbol"] == ranking[0]["symbol"]

    assert payload["benchmark"]["symbol"] == "000300.SH"
    assert payload["benchmark"]["return"] is not None


def test_pipeline_universe_filter(tmp_path):
    _seed_market(tmp_path)
    universe.save_universe(
        [
            {"symbol": "000001.SZ", "start_date": "2020-01-01", "end_date": ""},
        ],
        "csi300_subset",
        base_dir=tmp_path,
    )
    out = run_pipeline.run_pipeline(
        date_str="2026-11-24",
        symbols=["000001.SZ", "600000.SH"],
        base_dir=tmp_path,
        offline=True,
        universe="csi300_subset",
    )
    payload = json.loads(Path(out["json"]).read_text(encoding="utf-8"))
    assert [s["basic_info"]["code"] for s in payload["stocks"]] == ["000001.SZ"]
    assert out["validation"]["ok"] is True
