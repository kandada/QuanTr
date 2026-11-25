# quan_tr/programs/analyzers/portfolio.py
"""Simple, auditable portfolio construction from a cross-sectional ranking.

- Select top-N eligible names (exclude sell/strong_sell).
- ``score_weight`` (default): weight proportional to overall score.
- ``equal_weight``: equal weights among selected.
- Total invested capped by ``max_position_ratio``; the rest is cash.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

DEFAULT_EXCLUDE = ("sell", "strong_sell")


def build_portfolio(
    ranking: Sequence[Dict[str, Any]],
    method: str = "score_weight",
    top_n: int = 5,
    max_position_ratio: float = 0.8,
    exclude_actions: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    exclude = set(exclude_actions or DEFAULT_EXCLUDE)
    eligible = [row for row in ranking if row.get("action") not in exclude]
    eligible = sorted(eligible, key=lambda r: r.get("overall", 0.0), reverse=True)[
        : max(0, int(top_n))
    ]

    invest = max(0.0, min(1.0, float(max_position_ratio)))
    if not eligible:
        return {
            "method": method,
            "top_n": top_n,
            "constituents": [],
            "invested_weight": 0.0,
            "cash_weight": 1.0,
        }

    if method == "equal_weight":
        raw = {row["symbol"]: 1.0 for row in eligible}
    else:
        raw = {row["symbol"]: max(float(row.get("overall", 0.0)), 1.0) for row in eligible}
    total = sum(raw.values()) or 1.0

    constituents = [
        {
            "symbol": row["symbol"],
            "score": row.get("overall"),
            "weight": round(raw[row["symbol"]] / total * invest, 4),
        }
        for row in eligible
    ]
    invested = round(sum(item["weight"] for item in constituents), 4)
    return {
        "method": method,
        "top_n": top_n,
        "constituents": constituents,
        "invested_weight": invested,
        "cash_weight": round(1.0 - invested, 4),
    }
