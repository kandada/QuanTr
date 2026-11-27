# src/quantr/market_clock.py
"""简易交易日历工具（无外部依赖）。

用途：
- 判断是否交易日（默认仅按工作日，可选传入节假日集合）
- 取最近交易日作为数据 as_of 日期，避免周末/节假日误把“今天”当行情日

真实节假日可后续用 akshare 交易日历替换，接口保持不变。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable, Optional


def _as_date(value=None) -> date:
    if value is None:
        return date.today()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
    raise TypeError(f"Unsupported date value: {value!r}")


def is_weekend(value=None) -> bool:
    return _as_date(value).weekday() >= 5


def is_trading_day(value=None, holidays: Optional[Iterable[str]] = None) -> bool:
    day = _as_date(value)
    if day.weekday() >= 5:
        return False
    if holidays:
        return day.isoformat() not in set(holidays)
    return True


def last_trading_day(value=None, holidays: Optional[Iterable[str]] = None) -> date:
    """Return the most recent trading day on or before ``value``."""
    day = _as_date(value)
    for _ in range(30):
        if is_trading_day(day, holidays):
            return day
        day -= timedelta(days=1)
    return day


def describe(value=None) -> dict:
    """Convenience summary for prompts/manifests."""
    day = _as_date(value)
    as_of = last_trading_day(day)
    return {
        "today": day.isoformat(),
        "is_trading_day": is_trading_day(day),
        "as_of": as_of.isoformat(),
    }
