# quan_tr/programs/utils/data_store.py
"""本地 PIT 数据仓（Parquet + DuckDB）。

布局：
    <base>/store/ohlcv/<canonical>.parquet      # 追加式多版本（按 ingest_time）
    <base>/store/ohlcv/<canonical>.meta.json    # 最新来源/行数/区间
    <base>/store/fundamentals/<canonical>.parquet  # report_date / announce_date / ingest_time

PIT（point-in-time）语义：
- OHLCV 每行带 ``ingest_time``；``load_ohlcv(..., ingest_as_of=T)`` 只读取 T 之前
  已入库的版本，并按 (symbol, date) 取最新版本 —— 可审计、可复现。
- 财报同时带 ``report_date`` 与 ``announce_date``；``load_fundamentals(as_of=T)``
  只使用 ``announce_date <= T`` 的报告，避免前视偏差。

Parquet 的读写全部走 DuckDB，无需 pyarrow。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import duckdb
import pandas as pd

from ._paths import workspace_root
from .schema import normalize_ohlcv, parse_symbol, validate_ohlcv
from .data_provenance import is_simulated

OHLCV_COLUMNS = ["date", "open", "high", "low", "close", "volume", "amount"]


def store_root(base_dir: Optional[Path] = None) -> Path:
    return workspace_root(base_dir) / "store" / "ohlcv"


def fundamentals_root(base_dir: Optional[Path] = None) -> Path:
    return workspace_root(base_dir) / "store" / "fundamentals"


def _canonical(symbol: str) -> str:
    return parse_symbol(symbol)["canonical"]


def _paths(symbol: str, base_dir: Optional[Path] = None):
    canonical = _canonical(symbol)
    root = store_root(base_dir)
    return (
        root / f"{canonical}.parquet",
        root / f"{canonical}.meta.json",
        root / f"{canonical}.csv",
    )


def _write_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    try:
        con.register("batch", df)
        target = str(path).replace("'", "''")
        con.execute(f"COPY (SELECT * FROM batch) TO '{target}' (FORMAT PARQUET)")
    finally:
        con.close()


def _read_parquet(path: Path) -> pd.DataFrame:
    con = duckdb.connect()
    try:
        return con.execute("SELECT * FROM read_parquet(?)", [str(path)]).df()
    finally:
        con.close()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def save_ohlcv(
    df: pd.DataFrame,
    symbol: str,
    source: str,
    note: str = "",
    base_dir: Optional[Path] = None,
    retrieved_at: Optional[str] = None,
    merge: bool = True,
) -> Dict[str, Any]:
    """Persist an OHLCV batch (append-only; PIT by ``ingest_time``)."""
    canonical = _canonical(symbol)
    normalized = normalize_ohlcv(df)
    ok, errors = validate_ohlcv(normalized)
    if not ok:
        raise ValueError(f"invalid OHLCV for {canonical}: {errors}")

    ingest = retrieved_at or _now()
    batch = normalized.copy()
    if "amount" not in batch.columns:
        batch["amount"] = None
    batch = batch.loc[:, OHLCV_COLUMNS]
    batch["ingest_time"] = pd.to_datetime(ingest)
    batch["source"] = source
    batch["is_simulated"] = bool(is_simulated(note, source))

    parquet_path, meta_path, _ = _paths(canonical, base_dir)
    if merge and parquet_path.exists():
        existing = _read_parquet(parquet_path)
        combined = pd.concat([existing, batch], ignore_index=True)
    else:
        combined = batch

    combined["date"] = pd.to_datetime(combined["date"]).dt.normalize()
    combined["ingest_time"] = pd.to_datetime(combined["ingest_time"])
    combined = (
        combined.drop_duplicates(subset=["date", "ingest_time"], keep="last")
        .sort_values(["date", "ingest_time"])
        .reset_index(drop=True)
    )
    _write_parquet(combined, parquet_path)

    dates = combined["date"]
    meta = {
        "symbol": canonical,
        "source": source,
        "note": note,
        "is_simulated": bool(is_simulated(note, source)),
        "retrieved_at": ingest,
        "rows": int(dates.nunique()),
        "versions": int(len(combined)),
        "first_date": str(dates.min().date()),
        "last_date": str(dates.max().date()),
        "storage": "parquet",
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"parquet": str(parquet_path), "meta": str(meta_path), **meta}


def load_ohlcv(
    symbol: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    base_dir: Optional[Path] = None,
    ingest_as_of: Optional[str] = None,
) -> Optional[pd.DataFrame]:
    """Load latest-known OHLCV as of ``ingest_as_of`` (PIT); default = latest."""
    parquet_path, _, csv_path = _paths(symbol, base_dir)
    if not parquet_path.exists():
        if not csv_path.exists():
            return None
        df = pd.read_csv(csv_path)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    else:
        raw = _read_parquet(parquet_path)
        raw["date"] = pd.to_datetime(raw["date"], errors="coerce")
        raw["ingest_time"] = pd.to_datetime(raw["ingest_time"], errors="coerce")
        if ingest_as_of:
            raw = raw[raw["ingest_time"] <= pd.to_datetime(ingest_as_of)]
        # PIT: for each date keep the latest version known by the cutoff
        df = (
            raw.sort_values("ingest_time")
            .drop_duplicates(subset=["date"], keep="last")
            .reset_index(drop=True)
        )

    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    if start:
        df = df[df["date"] >= pd.to_datetime(start)]
    if end:
        df = df[df["date"] <= pd.to_datetime(end)]
    cols = [c for c in OHLCV_COLUMNS if c in df.columns]
    return df[cols].reset_index(drop=True)


def get_meta(symbol: str, base_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    _, meta_path, _ = _paths(symbol, base_dir)
    if not meta_path.exists():
        return None
    return json.loads(meta_path.read_text(encoding="utf-8"))


def list_symbols(base_dir: Optional[Path] = None) -> List[str]:
    root = store_root(base_dir)
    if not root.exists():
        return []
    suffix = ".meta.json"
    return sorted(p.name[: -len(suffix)] for p in root.glob(f"*{suffix}"))


# ─── PIT fundamentals ───────────────────────────────────────────────────────


def _fundamentals_paths(symbol: str, base_dir: Optional[Path] = None):
    canonical = _canonical(symbol)
    root = fundamentals_root(base_dir)
    return root / f"{canonical}.parquet", root / f"{canonical}.json"


def save_fundamentals(
    symbol: str,
    data: Dict[str, Any],
    report_date: str,
    announce_date: str,
    source: str = "",
    base_dir: Optional[Path] = None,
    retrieved_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Append a PIT fundamental report (report period vs announcement date)."""
    canonical = _canonical(symbol)
    parquet_path, _ = _fundamentals_paths(canonical, base_dir)
    row = pd.DataFrame(
        [
            {
                "symbol": canonical,
                "report_date": pd.to_datetime(report_date),
                "announce_date": pd.to_datetime(announce_date),
                "ingest_time": pd.to_datetime(retrieved_at or _now()),
                "source": source,
                "data_json": json.dumps(data, ensure_ascii=False),
            }
        ]
    )
    if parquet_path.exists():
        existing = _read_parquet(parquet_path)
        for col in ("report_date", "announce_date", "ingest_time"):
            existing[col] = pd.to_datetime(existing[col])
        combined = pd.concat([existing, row], ignore_index=True)
    else:
        combined = row
    combined = (
        combined.drop_duplicates(
            subset=["report_date", "announce_date", "ingest_time"], keep="last"
        )
        .sort_values(["announce_date", "report_date", "ingest_time"])
        .reset_index(drop=True)
    )
    _write_parquet(combined, parquet_path)
    return {
        "symbol": canonical,
        "report_date": report_date,
        "announce_date": announce_date,
        "path": str(parquet_path),
        "rows": int(len(combined)),
    }


def load_fundamentals(
    symbol: str,
    as_of: Optional[str] = None,
    base_dir: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """Return the latest report announced on/before ``as_of`` (PIT)."""
    parquet_path, json_path = _fundamentals_paths(symbol, base_dir)
    if parquet_path.exists():
        raw = _read_parquet(parquet_path)
        raw["announce_date"] = pd.to_datetime(raw["announce_date"], errors="coerce")
        raw["report_date"] = pd.to_datetime(raw["report_date"], errors="coerce")
        raw["ingest_time"] = pd.to_datetime(raw["ingest_time"], errors="coerce")
        if as_of:
            raw = raw[raw["announce_date"] <= pd.to_datetime(as_of)]
        if len(raw) == 0:
            return None
        raw = raw.sort_values(["report_date", "ingest_time"])
        latest = raw.iloc[-1]
        try:
            payload = json.loads(latest["data_json"])
        except Exception:  # noqa: BLE001
            return None
        payload.setdefault("source", latest.get("source"))
        payload["report_date"] = str(pd.Timestamp(latest["report_date"]).date())
        payload["announce_date"] = str(pd.Timestamp(latest["announce_date"]).date())
        return payload
    if json_path.exists():
        try:
            return json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return None
    return None
