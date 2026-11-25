# quan_tr/programs/utils/schema.py
"""统一证券代码与行情数据 schema。

- ``parse_symbol``: 把各种写法（000001.SZ / 000001_SZ / sh600000 / 0700.HK / AAPL）
  规范成统一结构，供数据源适配与存储使用。
- ``normalize_ohlcv``: 把不同数据源的中英文列名/索引统一成标准列。
- ``validate_ohlcv``: 基本健康检查（非空、价格为正、high>=low 等）。

本模块只做纯函数转换，不访问网络，便于测试。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

import pandas as pd

CANONICAL_COLUMNS = ["date", "open", "high", "low", "close", "volume"]
OPTIONAL_COLUMNS = ["amount", "change_pct", "turnover"]

_COLUMN_ALIASES = {
    "date": ["date", "日期", "trade_date", "datetime", "时间", "交易日"],
    "open": ["open", "开盘", "开盘价"],
    "high": ["high", "最高", "最高价"],
    "low": ["low", "最低", "最低价"],
    "close": ["close", "收盘", "收盘价", "adj close", "adj_close"],
    "volume": ["volume", "成交量", "vol"],
    "amount": ["amount", "成交额", "turnover_value"],
    "change_pct": ["change_pct", "涨跌幅", "pct_chg", "pct_change"],
    "turnover": ["turnover", "换手率"],
}

_MARKETS = {"SH", "SZ", "BJ", "HK", "US"}


def parse_symbol(raw: str) -> Dict[str, Any]:
    """Normalize a symbol string into a canonical descriptor.

    Returns a dict with keys: raw, code, market, canonical, akshare, yfinance,
    is_a_share.
    """
    if not raw or not str(raw).strip():
        raise ValueError("empty symbol")
    original = str(raw).strip()
    text = original.upper().replace(" ", "")

    market: str | None = None
    code: str | None = None

    # suffix forms: 000001.SZ / 000001_SZ / 0700.HK
    match = re.match(r"^(?P<code>[A-Z0-9.\-]+?)[._](?P<suffix>[A-Z]{2})$", text)
    if match:
        code = match.group("code")
        suffix = match.group("suffix")
        if suffix in {"SS", "SH"}:
            market = "SH"
        elif suffix in {"SZ"}:
            market = "SZ"
        elif suffix in {"BJ"}:
            market = "BJ"
        elif suffix in {"HK"}:
            market = "HK"
        else:
            market = "US"
    else:
        # prefix forms: SH600000 / SZ000001
        pre = re.match(r"^(SH|SZ|BJ|HK)(?P<code>\d{4,6})$", text)
        if pre:
            market = pre.group(1)
            code = pre.group("code")
        else:
            code = text

    assert code is not None
    code = code.replace("-", ".")  # keep BRK-B style handled below

    if market is None:
        if re.fullmatch(r"\d{6}", code):
            if code[0] in {"5", "6", "9"}:
                market = "SH"
            elif code[0] in {"0", "1", "2", "3"}:
                market = "SZ"
            elif code[0] in {"4", "8"}:
                market = "BJ"
            else:
                market = "SZ"
        else:
            market = "US"

    code = code.replace(".", "-") if market == "US" else code

    if market == "HK":
        digits = re.sub(r"\D", "", code)
        code = digits.zfill(4)
        canonical = f"{code}.HK"
        yf = f"{code}.HK"
        ak = None
    elif market in {"SH", "SZ", "BJ"}:
        digits = re.sub(r"\D", "", code)
        if len(digits) != 6:
            raise ValueError(f"invalid A-share code: {raw}")
        code = digits
        canonical = f"{code}.{market}"
        yf_suffix = {"SH": "SS", "SZ": "SZ", "BJ": "BJ"}[market]
        yf = f"{code}.{yf_suffix}"
        ak = digits
    else:  # US
        canonical = code
        yf = code
        ak = None

    return {
        "raw": original,
        "code": code,
        "market": market,
        "canonical": canonical,
        "akshare": ak,
        "yfinance": yf,
        "is_a_share": market in {"SH", "SZ", "BJ"},
    }


def normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Return a canonical OHLCV DataFrame.

    Columns: date(datetime64), open, high, low, close, volume, [amount...].
    Rows with invalid/missing prices are dropped; sorted and de-duplicated by date.
    """
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=CANONICAL_COLUMNS)

    work = df.copy()
    if isinstance(work.index, pd.DatetimeIndex):
        work = work.reset_index()
        work = work.rename(columns={work.columns[0]: "date"})

    lower = {str(col).strip().lower(): col for col in work.columns}
    rename: Dict[Any, str] = {}
    for canonical, aliases in _COLUMN_ALIASES.items():
        for alias in aliases:
            key = alias.lower()
            if key in lower:
                rename[lower[key]] = canonical
                break
    work = work.rename(columns=rename)

    missing = [col for col in CANONICAL_COLUMNS if col not in work.columns]
    if missing:
        raise ValueError(f"OHLCV missing required columns: {missing}; got {list(work.columns)}")

    work = work[[*CANONICAL_COLUMNS, *[c for c in OPTIONAL_COLUMNS if c in work.columns]]]

    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    for col in ["open", "high", "low", "close", "volume", *OPTIONAL_COLUMNS]:
        if col in work.columns:
            work[col] = pd.to_numeric(work[col], errors="coerce")

    work = work.dropna(subset=["date", "open", "high", "low", "close"])
    work = work[work["open"] > 0]
    work = work.sort_values("date").drop_duplicates(subset="date", keep="last")
    work["volume"] = work["volume"].fillna(0)
    return work.reset_index(drop=True)


def validate_ohlcv(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """Lightweight health check. Returns (ok, errors)."""
    errors: List[str] = []
    if df is None or len(df) == 0:
        return False, ["empty dataframe"]
    missing = [col for col in CANONICAL_COLUMNS if col not in df.columns]
    if missing:
        errors.append(f"missing columns: {missing}")
        return False, errors
    if (df["high"] < df["low"]).any():
        errors.append("high < low in some rows")
    if (df[["open", "high", "low", "close"]] <= 0).any().any():
        errors.append("non-positive prices")
    if (df["volume"] < 0).any():
        errors.append("negative volume")
    if df["date"].duplicated().any():
        errors.append("duplicate dates")
    return not errors, errors
