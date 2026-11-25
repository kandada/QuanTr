# quan_tr/programs/data_fetchers/market_data.py
"""参数化的真实行情获取器（AKshare / Yahoo Finance）。

设计原则：
- **只获取真实数据**；获取失败直接报错，绝不生成模拟数据。
- 统一输出规范化 OHLCV（见 ``utils/schema.py``）。
- 可选写入本地数据仓（``utils/data_store.py``）。

用法：
    python programs/data_fetchers/market_data.py --symbols 000001.SZ,600000.SH \
        --start 2025-01-01 --end 2025-12-31 --source auto --save
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

_UTILS = Path(__file__).resolve().parents[1] / "utils"
if str(_UTILS) not in sys.path:
    sys.path.insert(0, str(_UTILS))

from ._paths import workspace_root
from .schema import normalize_ohlcv, parse_symbol
from .data_store import save_ohlcv



def _default_end() -> str:
    return date.today().isoformat()


def _default_start(days: int = 400) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


def _akshare_to_canonical(raw: pd.DataFrame) -> pd.DataFrame:
    return normalize_ohlcv(raw)


def _yfinance_to_canonical(raw: pd.DataFrame) -> pd.DataFrame:
    if raw is None or len(raw) == 0:
        raise RuntimeError("yfinance returned empty data")
    work = raw.copy()
    if isinstance(work.columns, pd.MultiIndex):
        work.columns = work.columns.get_level_values(0)
    work = work.reset_index()
    work = work.rename(columns={"index": "date", "Date": "date"})
    return normalize_ohlcv(work)


def fetch_akshare(info: Dict[str, Any], start: str, end: str) -> pd.DataFrame:
    import akshare as ak  # lazy import

    code = info.get("akshare")
    if not code:
        raise RuntimeError(f"akshare does not support symbol {info['canonical']}")
    raw = ak.stock_zh_a_hist(
        symbol=code,
        period="daily",
        start_date=start.replace("-", ""),
        end_date=end.replace("-", ""),
        adjust="qfq",
    )
    if raw is None or len(raw) == 0:
        raise RuntimeError("akshare returned empty data (network or unsupported)")
    df = _akshare_to_canonical(raw)
    if len(df) == 0:
        raise RuntimeError("akshare data could not be normalized")
    return df


def fetch_yfinance(info: Dict[str, Any], start: str, end: str) -> pd.DataFrame:
    import yfinance as yf  # lazy import

    ticker = info.get("yfinance")
    if not ticker:
        raise RuntimeError(f"yfinance does not support symbol {info['canonical']}")
    end_exclusive = (datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    raw = yf.download(
        ticker, start=start, end=end_exclusive, auto_adjust=True, progress=False
    )
    df = _yfinance_to_canonical(raw)
    if len(df) == 0:
        raise RuntimeError("yfinance data could not be normalized")
    return df


_SUPPORTED = {"akshare": fetch_akshare, "yfinance": fetch_yfinance}


def _source_order(info: Dict[str, Any], source: str) -> List[str]:
    if source != "auto":
        if source not in _SUPPORTED:
            raise ValueError(f"unknown source: {source}")
        return [source]
    if info["is_a_share"]:
        return ["akshare", "yfinance"]
    return ["yfinance"]


def fetch_ohlcv(
    symbol: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    source: str = "auto",
) -> Tuple[pd.DataFrame, str]:
    """Fetch real OHLCV. Returns (dataframe, used_source). Raises on failure."""
    info = parse_symbol(symbol)
    start = start or _default_start()
    end = end or _default_end()
    errors: Dict[str, str] = {}
    for src in _source_order(info, source):
        try:
            df = _SUPPORTED[src](info, start, end)
            return df, src
        except Exception as exc:  # noqa: BLE001
            errors[src] = f"{type(exc).__name__}: {exc}"
    raise RuntimeError(
        f"failed to fetch {info['canonical']} from {source}: {errors}. "
        "Refusing to fabricate data."
    )


def update_store(
    symbols: List[str],
    start: Optional[str] = None,
    end: Optional[str] = None,
    source: str = "auto",
    base_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    base = workspace_root(base_dir)
    records: List[Dict[str, Any]] = []
    for symbol in symbols:
        try:
            df, used = fetch_ohlcv(symbol, start, end, source)
            saved = save_ohlcv(
                df,
                symbol,
                source=used,
                note=f"real market data via {used}",
                base_dir=base,
            )
            records.append({"ok": True, **saved})
        except Exception as exc:  # noqa: BLE001
            records.append(
                {"ok": False, "symbol": symbol, "error": f"{type(exc).__name__}: {exc}"}
            )
    return records


def _resolve_symbols(args) -> List[str]:
    if args.symbols:
        return [s.strip() for s in args.symbols.split(",") if s.strip()]
    pool_path = workspace_root(args.base_dir) / "stocks_pool.json"
    if args.pool and pool_path.exists():
        data = json.loads(pool_path.read_text(encoding="utf-8"))
        return [item["symbol"] for item in data.get("stocks", []) if item.get("symbol")]
    return []


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="QuanTr 真实行情获取器（无模拟数据）")
    parser.add_argument("--symbols", help="逗号分隔，例如 000001.SZ,600000.SH")
    parser.add_argument("--pool", action="store_true", help="从 stocks_pool.json 读取股票池")
    parser.add_argument("--start", default=None, help="YYYY-MM-DD")
    parser.add_argument("--end", default=None, help="YYYY-MM-DD")
    parser.add_argument("--source", default="auto", choices=["auto", "akshare", "yfinance"])
    parser.add_argument("--save", action="store_true", help="写入本地数据仓")
    parser.add_argument("--base-dir", default=None, help="quan_tr 根目录")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    symbols = _resolve_symbols(args)
    if not symbols:
        parser.error("no symbols; pass --symbols or --pool")

    if args.save:
        records = update_store(symbols, args.start, args.end, args.source, args.base_dir)
    else:
        records = []
        for symbol in symbols:
            try:
                df, used = fetch_ohlcv(symbol, args.start, args.end, args.source)
                records.append(
                    {
                        "ok": True,
                        "symbol": parse_symbol(symbol)["canonical"],
                        "source": used,
                        "rows": int(len(df)),
                        "first_date": str(df["date"].iloc[0].date()),
                        "last_date": str(df["date"].iloc[-1].date()),
                    }
                )
            except Exception as exc:  # noqa: BLE001
                records.append(
                    {"ok": False, "symbol": symbol, "error": f"{type(exc).__name__}: {exc}"}
                )

    if args.json:
        print(json.dumps(records, ensure_ascii=False, indent=2))
    else:
        for rec in records:
            if rec.get("ok"):
                print(
                    f"✅ {rec['symbol']} {rec.get('source', '')} rows={rec.get('rows')} "
                    f"{rec.get('first_date')}..{rec.get('last_date')}"
                )
            else:
                print(f"❌ {rec.get('symbol')}: {rec.get('error')}")
    return 0 if all(rec.get("ok") for rec in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
