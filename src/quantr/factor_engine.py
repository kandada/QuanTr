# src/quantr/factor_engine.py
"""确定性因子/评分引擎（替代让 LLM “估”数值）。

- 技术面/风险分由指标纯计算得到，可复现、可单测。
- 基本面/情绪分仅在提供真实数据时计算，否则为 ``None`` 并从总分中剔除，
  绝不伪造一个中间分。
- 综合分按配置权重对**可用维度**重新归一。
- ``buy``/``strong_buy`` 可被 ``allow_buy=False`` 强制降级（用于数据不达标时）。

用法：
    python programs/analyzers/factor_engine.py --symbol 000001.SZ --json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

_UTILS = Path(__file__).resolve().parents[1] / "utils"
if str(_UTILS) not in sys.path:
    sys.path.insert(0, str(_UTILS))

from .indicators import compute_snapshot  # noqa: E402
from ._paths import workspace_root  # noqa: E402
from .data_store import load_ohlcv  # noqa: E402
from .schema import parse_symbol  # noqa: E402

DEFAULT_WEIGHTS = {"fundamental": 0.4, "technical": 0.3, "risk": 0.2, "sentiment": 0.1}
DEFAULT_THRESHOLDS = {"strong_buy": 80, "buy": 60, "hold": 40, "sell": 20, "strong_sell": 0}
DEFAULT_RISK_LEVELS = {"high_risk": 70, "medium_risk": 40, "low_risk": 20}
BUY_ACTIONS = {"buy", "strong_buy"}


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _weights(config: Optional[Dict[str, Any]]) -> Dict[str, float]:
    analysis = (config or {}).get("analysis", {}) if config else {}
    nested = analysis.get("scoring_weights") if isinstance(analysis, dict) else None
    if isinstance(nested, dict) and nested:
        return {k: float(nested.get(k, v)) for k, v in DEFAULT_WEIGHTS.items()}
    flat = {
        "fundamental": analysis.get("fundamental_weight", DEFAULT_WEIGHTS["fundamental"]),
        "technical": analysis.get("technical_weight", DEFAULT_WEIGHTS["technical"]),
        "risk": analysis.get("risk_weight", DEFAULT_WEIGHTS["risk"]),
        "sentiment": analysis.get("sentiment_weight", DEFAULT_WEIGHTS["sentiment"]),
    }
    return {k: float(v) for k, v in flat.items()}


def _thresholds(config: Optional[Dict[str, Any]]) -> Dict[str, float]:
    analysis = (config or {}).get("analysis", {}) if config else {}
    t = analysis.get("recommendation_thresholds") or {}
    return {k: float(t.get(k, v)) for k, v in DEFAULT_THRESHOLDS.items()}


def _risk_levels(config: Optional[Dict[str, Any]]) -> Dict[str, float]:
    analysis = (config or {}).get("analysis", {}) if config else {}
    t = analysis.get("risk_thresholds") or {}
    return {k: float(t.get(k, v)) for k, v in DEFAULT_RISK_LEVELS.items()}


def _score_trend(trend: Optional[str]) -> float:
    return {"up": 90.0, "sideways": 55.0, "down": 20.0}.get(str(trend), 50.0)


def _score_momentum(snapshot: Dict[str, Any]) -> float:
    mom = snapshot.get("momentum_60")
    if mom is None:
        mom = snapshot.get("momentum_20")
    if mom is None:
        return 50.0
    return _clamp(50 + 50 * math.tanh(float(mom) / 0.25))


def _score_rsi(rsi: Optional[float]) -> float:
    if rsi is None:
        return 50.0
    return _clamp(100 - abs(float(rsi) - 58.0) * 2.0)


def technical_score(snapshot: Dict[str, Any]) -> float:
    trend = _score_trend(snapshot.get("trend"))
    momentum = _score_momentum(snapshot)
    rsi = _score_rsi(snapshot.get("rsi"))
    return round(_clamp(0.40 * trend + 0.35 * momentum + 0.25 * rsi), 2)


def risk_safety_score(snapshot: Dict[str, Any]) -> Tuple[float, List[str]]:
    factors: List[str] = []
    vol = snapshot.get("volatility_annual")
    if vol is None:
        vol_score = 50.0
    else:
        vol_score = _clamp(100 * (1 - float(vol) / 0.6))
        if float(vol) >= 0.45:
            factors.append(f"高波动({float(vol):.0%})")
    dd = abs(float(snapshot.get("max_drawdown") or 0.0))
    dd_score = _clamp(100 * (1 - dd / 0.5))
    if dd >= 0.25:
        factors.append(f"历史最大回撤{dd:.0%}")
    if snapshot.get("trend") == "down":
        factors.append("趋势向下")
    return round(_clamp(0.5 * vol_score + 0.5 * dd_score), 2), factors


def fundamental_score(fundamentals: Optional[Dict[str, Any]]) -> Optional[float]:
    if not fundamentals:
        return None
    parts: List[float] = []
    pe = fundamentals.get("pe") or fundamentals.get("pe_ratio")
    if pe:
        pe = float(pe)
        if pe > 0:
            parts.append(_clamp(100 - pe * 2.0))
    pb = fundamentals.get("pb") or fundamentals.get("pb_ratio")
    if pb:
        parts.append(_clamp(100 - float(pb) * 15.0))
    roe = fundamentals.get("roe")
    if roe is not None:
        parts.append(_clamp(float(roe) * 5.0))
    debt = fundamentals.get("debt_ratio")
    if debt is not None:
        parts.append(_clamp(100 - float(debt)))
    for key in ("revenue_growth", "profit_growth"):
        growth = fundamentals.get(key)
        if growth is not None:
            parts.append(_clamp(50 + float(growth) * 2.0))
    if not parts:
        return None
    return round(sum(parts) / len(parts), 2)


def sentiment_score(sentiment: Optional[Dict[str, Any]]) -> Optional[float]:
    if not sentiment:
        return None
    score = sentiment.get("score")
    if score is None:
        return None
    try:
        return round(_clamp(float(score)), 2)
    except (TypeError, ValueError):
        return None


def _action_from_score(score: float, thresholds: Dict[str, float]) -> str:
    if score >= thresholds["strong_buy"]:
        return "strong_buy"
    if score >= thresholds["buy"]:
        return "buy"
    if score >= thresholds["hold"]:
        return "hold"
    if score >= thresholds["sell"]:
        return "sell"
    return "strong_sell"


def _confidence(score: float, thresholds: Dict[str, float]) -> str:
    if score >= 75 or score <= 25:
        return "high"
    if score >= thresholds["buy"] or score <= thresholds["sell"]:
        return "medium"
    return "low"


def compute_scores(
    df: pd.DataFrame,
    fundamentals: Optional[Dict[str, Any]] = None,
    sentiment: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
    allow_buy: bool = True,
) -> Dict[str, Any]:
    """Compute deterministic subscores/overall/recommendation for one symbol."""
    snapshot = compute_snapshot(df, config)
    technical = technical_score(snapshot)
    risk_safety, risk_factors = risk_safety_score(snapshot)
    fundamental = fundamental_score(fundamentals)
    sentiment_s = sentiment_score(sentiment)

    subscores: Dict[str, Optional[float]] = {
        "fundamental": fundamental,
        "technical": technical,
        "risk": risk_safety,
        "sentiment": sentiment_s,
    }
    weights = _weights(config)
    available = {k: v for k, v in subscores.items() if v is not None}
    if available:
        total_w = sum(weights[k] for k in available) or 1.0
        overall = sum(available[k] * weights[k] for k in available) / total_w
    else:
        overall = 50.0
    overall = round(_clamp(overall), 2)

    thresholds = _thresholds(config)
    action = _action_from_score(overall, thresholds)
    notes: List[str] = []
    if action in BUY_ACTIONS and (not allow_buy):
        action = "hold"
        notes.append("数据未达真实标准，买入结论已降级为 hold")

    riskiness = round(100 - risk_safety, 2)
    levels = _risk_levels(config)
    if riskiness >= levels["high_risk"]:
        risk_level = "high"
    elif riskiness >= levels["medium_risk"]:
        risk_level = "medium"
    else:
        risk_level = "low"

    for missing in [k for k, v in subscores.items() if v is None]:
        notes.append(f"{missing} 维度数据缺失，未计入总分")

    return {
        "snapshot": snapshot,
        "subscores": subscores,
        "overall": overall,
        "action": action,
        "confidence": _confidence(overall, thresholds),
        "risk": {
            "safety": risk_safety,
            "score": riskiness,
            "level": risk_level,
            "factors": risk_factors,
        },
        "notes": notes,
    }


def rank_scores(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Rank already-scored rows by ``overall`` desc (cross-sectional)."""
    ranked = sorted(rows, key=lambda r: r.get("overall", 0.0), reverse=True)
    count = len(ranked)
    for index, row in enumerate(ranked):
        row["rank"] = index + 1
        row["percentile"] = (
            round(100 * (1 - index / (count - 1)), 2) if count > 1 else 100.0
        )
    return ranked


def rank_universe(
    items: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
    allow_buy: bool = True,
) -> List[Dict[str, Any]]:
    """Cross-sectional ranking.

    ``items`` maps symbol -> either a DataFrame or a dict with ``df`` and
    optional ``fundamentals``/``sentiment``.
    """
    rows: List[Dict[str, Any]] = []
    for symbol, payload in items.items():
        if isinstance(payload, pd.DataFrame):
            df, fundamentals, sentiment = payload, None, None
        else:
            df = payload.get("df")
            fundamentals = payload.get("fundamentals")
            sentiment = payload.get("sentiment")
        result = compute_scores(
            df, fundamentals, sentiment, config, allow_buy=allow_buy
        )
        rows.append(
            {
                "symbol": parse_symbol(symbol)["canonical"],
                "overall": result["overall"],
                "action": result["action"],
                "technical": result["subscores"]["technical"],
                "risk_level": result["risk"]["level"],
            }
        )
    return rank_scores(rows)


def _load_config(base_dir: Optional[Path]) -> Optional[Dict[str, Any]]:
    import importlib.util

    root = workspace_root(base_dir)
    path = root / "config.py"
    if not path.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location("quantr_config", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.config.config
    except Exception:  # noqa: BLE001
        return None


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="QuanTr 确定性因子引擎")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    base = Path(args.base_dir) if args.base_dir else None
    df = load_ohlcv(args.symbol, base_dir=base)
    if df is None or len(df) == 0:
        print(f"❌ 本地无数据: {args.symbol}（请先运行 market_data.py --save）")
        return 1

    cfg = _load_config(base)
    result = compute_scores(df, config=cfg)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{parse_symbol(args.symbol)['canonical']} overall={result['overall']} "
              f"action={result['action']} risk={result['risk']['level']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
