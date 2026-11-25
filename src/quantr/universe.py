# quan_tr/programs/utils/universe.py
"""Point-in-time universe membership.

File format (``<base>/store/universe/<index>.csv``):
    symbol,start_date,end_date
    000001.SZ,2020-01-01,
    600000.SH,2018-06-01,2023-12-31

``end_date`` empty means still active. ``load_universe`` returns the symbols
that were members on ``as_of`` — used to avoid survivorship bias and look-ahead
in backtests.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from ._paths import workspace_root

import pandas as pd

try:
    from .schema import parse_symbol
except ImportError:  # direct execution
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from .schema import parse_symbol  # type: ignore



def universe_path(index: str, base_dir: Optional[Path] = None) -> Path:
    base = workspace_root(base_dir)
    return base / "store" / "universe" / f"{index}.csv"


def load_universe(
    index: str, as_of: str, base_dir: Optional[Path] = None
) -> Optional[List[str]]:
    """Return canonical symbols active on ``as_of``, or None if file missing."""
    path = universe_path(index, base_dir)
    if not path.exists():
        return None
    df = pd.read_csv(path)
    for col in ("symbol", "start_date", "end_date"):
        if col not in df.columns:
            raise ValueError(f"universe file missing column: {col}")
    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
    df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")
    cutoff = pd.to_datetime(as_of)
    active = df[
        (df["start_date"].isna() | (df["start_date"] <= cutoff))
        & (df["end_date"].isna() | (df["end_date"] >= cutoff))
    ]
    symbols: List[str] = []
    for raw in active["symbol"].tolist():
        try:
            symbols.append(parse_symbol(raw)["canonical"])
        except ValueError:
            continue
    return sorted(dict.fromkeys(symbols))


def save_universe(rows: List[dict], index: str, base_dir: Optional[Path] = None) -> Path:
    """Persist membership rows (``symbol,start_date,end_date``) as CSV."""
    path = universe_path(index, base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=["symbol", "start_date", "end_date"]).to_csv(
        path, index=False
    )
    return path
