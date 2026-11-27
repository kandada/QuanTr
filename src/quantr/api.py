# src/quantr/api.py
"""Library facade for QuanTr's deterministic engine.

    import sys; sys.path.insert(0, "src")
    from api import Quantr

    q = Quantr()
    q.fetch(["000001.SZ"], start="2024-01-01", end="2024-12-31", save=True)
    q.factors("000001.SZ")

All methods return JSON-serializable dicts and never fabricate data.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import service

__all__ = [
    "Quantr",
    "fetch",
    "store",
    "indicators",
    "factors",
    "backtest",
    "validate",
    "pipeline",
    "load_config",
]

fetch = service.fetch
store = service.store
indicators = service.indicators
factors = service.factors
backtest = service.backtest
validate = service.validate
pipeline = service.pipeline
load_config = service.load_config


class Quantr:
    """Thin object wrapper around the service functions."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir

    def fetch(self, symbols: List[str], **kwargs: Any) -> Dict[str, Any]:
        return service.fetch(symbols, base_dir=self.base_dir, **kwargs)

    def store(self) -> Dict[str, Any]:
        return service.store(self.base_dir)

    def indicators(self, symbol: str) -> Dict[str, Any]:
        return service.indicators(symbol, self.base_dir)

    def factors(self, symbol: str, **kwargs: Any) -> Dict[str, Any]:
        return service.factors(symbol, self.base_dir, **kwargs)

    def backtest(self, symbol: str, **kwargs: Any) -> Dict[str, Any]:
        return service.backtest(symbol, base_dir=self.base_dir, **kwargs)

    def validate(self, date: str, strict: bool = False) -> Dict[str, Any]:
        return service.validate(date, self.base_dir, strict=strict)

    def pipeline(self, **kwargs: Any) -> Dict[str, Any]:
        return service.pipeline(base_dir=self.base_dir, **kwargs)
