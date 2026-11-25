# quan_tr/programs/utils/validate_report.py
"""Analysis output validator (contract v2).

Two layers:
1. **Schema** (``stocks_analysis.schema.json``) — types, enums, ranges, required.
2. **Invariants** — things JSON Schema can't express:
   - ``metadata.total_stocks`` == len(stocks); ``summary.recommendations`` counts;
   - ``scores.overall`` consistent with subscores/weights;
   - recommendation polarity vs thresholds; target/stop sanity;
   - ``data_quality.as_of <= analysis_date`` and is a trading day;
   - duplicate stock codes.

Data-integrity gate: the effective status is the WORSE of the report's declared
status and the audited manifest/data quality, so a report cannot claim "real" to
bypass the buy gate. ``buy``/``strong_buy`` with non-real data is an error.

Legacy v1 reports are rejected unless ``--allow-v1`` is passed (warning only).

Exit code: 0 = pass, 1 = fail (``--strict`` also fails on warnings).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from datetime import date as _date
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    from .data_provenance import audit_date_dir, data_quality_status
    from .market_clock import is_trading_day
except ImportError:  # direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from .data_provenance import audit_date_dir, data_quality_status  # type: ignore
    from .market_clock import is_trading_day  # type: ignore

from ._paths import templates_dir, workspace_root

try:
    from jsonschema import Draft202012Validator
except Exception:  # pragma: no cover - jsonschema is available in this env
    Draft202012Validator = None  # type: ignore

SCHEMA_FILE = "stocks_analysis.schema.json"
EXAMPLE_FILE = "stocks_analysis.example.json"
TEMPLATE_FILE = "stocks_analysis_template.json"
SCHEMA_VERSION = "2.0.0"

MD_REQUIRED_SNIPPETS = ("基本信息", "价格", "基本面", "技术面", "风险", "投资建议")
BUY_ACTIONS = {"buy", "strong_buy"}
SELL_ACTIONS = {"sell", "strong_sell"}
STATUS_RANK = {"real": 0, "partial": 1, "simulated": 2, "missing": 3}
STATUS_BY_RANK = {v: k for k, v in STATUS_RANK.items()}

DEFAULT_WEIGHTS = {"fundamental": 0.4, "technical": 0.3, "risk": 0.2, "sentiment": 0.1}
DEFAULT_THRESHOLDS = {"strong_buy": 80, "buy": 60, "hold": 40, "sell": 20, "strong_sell": 0}
TOP_LEVEL_REQUIRED = ("metadata", "summary", "stocks")


# ─── loaders ────────────────────────────────────────────────────────────────


def _templates_dir(base_dir: Optional[Path] = None) -> Path:
    return templates_dir(base_dir)


def load_schema(base_dir: Optional[Path] = None) -> Dict[str, Any]:
    return json.loads((_templates_dir(base_dir) / SCHEMA_FILE).read_text(encoding="utf-8"))


def load_example(base_dir: Optional[Path] = None) -> Dict[str, Any]:
    return json.loads((_templates_dir(base_dir) / EXAMPLE_FILE).read_text(encoding="utf-8"))


def load_template(base_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Legacy v1 template (kept for ``--allow-v1``)."""
    return json.loads((_templates_dir(base_dir) / TEMPLATE_FILE).read_text(encoding="utf-8"))


def _load_config(base_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    base = workspace_root(base_dir)
    path = base / "config.py"
    if not path.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location("quantr_config", path)
        module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        return module.config.config
    except Exception:  # noqa: BLE001
        return None


# ─── helpers ────────────────────────────────────────────────────────────────


def _err(path: str, issue: str, detail: str = "") -> Dict[str, str]:
    item = {"path": path, "issue": issue}
    if detail:
        item["detail"] = detail
    return item


def _fmt_path(parts: Sequence[Any]) -> str:
    out = ""
    for part in parts:
        if isinstance(part, int):
            out += f"[{part}]"
        else:
            out += ("." + str(part)) if out else str(part)
    return out or "$"


def _weights(config: Optional[Dict[str, Any]]) -> Dict[str, float]:
    nested = ((config or {}).get("analysis") or {}).get("scoring_weights")
    if isinstance(nested, dict) and nested:
        return {k: float(nested.get(k, v)) for k, v in DEFAULT_WEIGHTS.items()}
    return dict(DEFAULT_WEIGHTS)


def _thresholds(config: Optional[Dict[str, Any]]) -> Dict[str, float]:
    t = ((config or {}).get("analysis") or {}).get("recommendation_thresholds") or {}
    return {k: float(t.get(k, v)) for k, v in DEFAULT_THRESHOLDS.items()}


# ─── v2: schema + invariants ────────────────────────────────────────────────


def _schema_errors(payload: Dict[str, Any], base_dir: Optional[Path]) -> List[Dict[str, str]]:
    errors: List[Dict[str, str]] = []
    if Draft202012Validator is None:
        errors.append(_err("$", "jsonschema_missing", "install jsonschema to validate v2"))
        return errors
    schema = load_schema(base_dir)
    validator = Draft202012Validator(schema)
    for error in sorted(validator.iter_errors(payload), key=lambda e: list(e.absolute_path)):
        parts = list(error.absolute_path)
        if error.validator == "required":
            match = re.search(r"'(.+?)' is a required property", error.message)
            if match:
                parts = parts + [match.group(1)]
        errors.append(_err(_fmt_path(parts), "schema", error.message))
    return errors


def _expected_overall(scores: Dict[str, Any], weights: Dict[str, float]) -> Optional[float]:
    subs = {
        "fundamental": scores.get("fundamental"),
        "technical": scores.get("technical"),
        "risk": scores.get("risk_safety"),
        "sentiment": scores.get("sentiment"),
    }
    available = {k: v for k, v in subs.items() if v is not None}
    if not available:
        return None
    total = sum(weights[k] for k in available) or 1.0
    return sum(available[k] * weights[k] for k in available) / total


def check_invariants(
    payload: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
    allow_empty: bool = False,
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    errors: List[Dict[str, str]] = []
    warnings: List[Dict[str, str]] = []
    weights = _weights(config)
    thresholds = _thresholds(config)

    stocks = payload.get("stocks") or []
    if not isinstance(stocks, list):
        return [_err("stocks", "not_a_list")], warnings
    if not stocks and not allow_empty:
        errors.append(_err("stocks", "empty", "use --allow-empty to permit"))

    metadata = payload.get("metadata") or {}
    if metadata.get("total_stocks") != len(stocks):
        errors.append(
            _err("metadata.total_stocks", "derived_mismatch",
                 f"{metadata.get('total_stocks')} != {len(stocks)}")
        )

    # recommendation counts
    actual = {k: 0 for k in ("strong_buy", "buy", "hold", "sell", "strong_sell")}
    for stock in stocks:
        action = ((stock or {}).get("recommendation") or {}).get("action")
        if action in actual:
            actual[action] += 1
    declared = ((payload.get("summary") or {}).get("recommendations")) or {}
    for key, value in actual.items():
        if declared.get(key) != value:
            errors.append(
                _err(f"summary.recommendations.{key}", "derived_mismatch",
                     f"declared={declared.get(key)} actual={value}")
            )

    # dates
    ad = metadata.get("analysis_date")
    as_of = (payload.get("data_quality") or {}).get("as_of")
    ad_date = _parse_date(ad)
    as_of_date = _parse_date(as_of)
    if ad and ad_date is None:
        errors.append(_err("metadata.analysis_date", "invalid_date", str(ad)))
    if as_of and as_of_date is None:
        errors.append(_err("data_quality.as_of", "invalid_date", str(as_of)))
    if ad_date and as_of_date:
        if as_of_date > ad_date:
            errors.append(_err("data_quality.as_of", "future_as_of", f"{as_of} > {ad}"))
        elif not is_trading_day(as_of_date):
            warnings.append(_err("data_quality.as_of", "non_trading_day", str(as_of)))

    # per-stock invariants
    seen_codes: Dict[str, int] = {}
    stock_codes: set = set()
    for index, stock in enumerate(stocks):
        if not isinstance(stock, dict):
            continue
        code = ((stock.get("basic_info") or {}).get("code"))
        if code:
            stock_codes.add(code)
            if code in seen_codes:
                errors.append(_err(f"stocks[{index}].basic_info.code", "duplicate_code",
                                   f"{code} also at stocks[{seen_codes[code]}]"))
            else:
                seen_codes[code] = index

        scores = stock.get("scores") or {}
        overall = scores.get("overall")
        expected = _expected_overall(scores, weights)
        if overall is not None and expected is not None and abs(float(overall) - expected) > 2.0:
            errors.append(
                _err(f"stocks[{index}].scores.overall", "score_inconsistent",
                     f"overall={overall} expected~{round(expected, 2)}")
            )

        action = ((stock.get("recommendation") or {}).get("action"))
        if overall is not None:
            overall = float(overall)
            if action == "strong_buy" and overall < thresholds["strong_buy"]:
                errors.append(_err(f"stocks[{index}].recommendation.action", "action_inconsistent",
                                   f"strong_buy but overall={overall}"))
            elif action == "buy" and overall < thresholds["buy"]:
                errors.append(_err(f"stocks[{index}].recommendation.action", "action_inconsistent",
                                   f"buy but overall={overall}"))
            elif action == "sell" and not (thresholds["sell"] <= overall < thresholds["hold"]):
                errors.append(_err(f"stocks[{index}].recommendation.action", "action_inconsistent",
                                   f"sell but overall={overall}"))
            elif action == "strong_sell" and overall >= thresholds["sell"]:
                errors.append(_err(f"stocks[{index}].recommendation.action", "action_inconsistent",
                                   f"strong_sell but overall={overall}"))

        price = (stock.get("price") or {}).get("current")
        rec = stock.get("recommendation") or {}
        target = rec.get("target_price")
        stop = rec.get("stop_loss")
        if price is not None:
            if isinstance(target, (int, float)) and target > 0 and target <= price:
                errors.append(_err(f"stocks[{index}].recommendation.target_price",
                                   "target_not_above_current", f"{target} <= {price}"))
            if isinstance(stop, (int, float)) and stop > 0 and stop >= price:
                errors.append(_err(f"stocks[{index}].recommendation.stop_loss",
                                   "stop_not_below_current", f"{stop} >= {price}"))

    # cross-sectional ranking
    ranking = payload.get("ranking")
    if isinstance(ranking, list) and ranking:
        ranks = []
        for i, row in enumerate(ranking):
            if not isinstance(row, dict):
                continue
            ranks.append(row.get("rank"))
            sym = row.get("symbol")
            if sym and stock_codes and sym not in stock_codes:
                errors.append(_err(f"ranking[{i}].symbol", "unknown_symbol", str(sym)))
        int_ranks = sorted(r for r in ranks if isinstance(r, int))
        if int_ranks != list(range(1, len(ranking) + 1)):
            errors.append(_err("ranking", "rank_sequence_invalid", str(ranks)))
        overalls = [r.get("overall") for r in ranking if isinstance(r, dict)]
        if overalls and all(isinstance(o, (int, float)) for o in overalls):
            if any(overalls[i] < overalls[i + 1] for i in range(len(overalls) - 1)):
                errors.append(_err("ranking", "not_sorted_by_overall"))

    # portfolio weights
    portfolio = payload.get("portfolio")
    if isinstance(portfolio, dict):
        constituents = portfolio.get("constituents") or []
        total_weight = 0.0
        for i, item in enumerate(constituents):
            if not isinstance(item, dict):
                continue
            weight = item.get("weight")
            if isinstance(weight, (int, float)):
                if weight < 0 or weight > 1:
                    errors.append(_err(f"portfolio.constituents[{i}].weight",
                                       "weight_out_of_range", str(weight)))
                total_weight += float(weight)
            sym = item.get("symbol")
            if sym and stock_codes and sym not in stock_codes:
                errors.append(_err(f"portfolio.constituents[{i}].symbol", "unknown_symbol", str(sym)))
        if total_weight > 1.0001:
            errors.append(_err("portfolio", "weights_exceed_one", str(round(total_weight, 4))))

    # benchmark date sanity
    benchmark = payload.get("benchmark")
    if isinstance(benchmark, dict) and benchmark.get("as_of"):
        bench_date = _parse_date(benchmark.get("as_of"))
        if bench_date and ad_date and bench_date > ad_date:
            errors.append(_err("benchmark.as_of", "future_as_of",
                               f"{benchmark.get('as_of')} > {ad}"))

    return errors, warnings


def _parse_date(value: Any) -> Optional[_date]:
    if not isinstance(value, str):
        return None
    try:
        return _date.fromisoformat(value[:10])
    except ValueError:
        return None


def validate_analysis_json(
    path: Path,
    base_dir: Optional[Path] = None,
    allow_empty: bool = False,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Validate a single v2 summary JSON (schema + invariants)."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"file": str(path), "ok": False,
                "errors": [_err("$", "parse_error", str(exc))], "warnings": []}
    if not isinstance(payload, dict):
        return {"file": str(path), "ok": False,
                "errors": [_err("$", "not_an_object")], "warnings": []}

    errors = _schema_errors(payload, base_dir)
    inv_errors, warnings = check_invariants(
        payload, config if config is not None else _load_config(base_dir), allow_empty
    )
    errors.extend(inv_errors)
    return {
        "file": str(path),
        "ok": not errors,
        "schema_version": payload.get("schema_version"),
        "errors": errors,
        "warnings": warnings,
    }


# ─── legacy v1 structural check ─────────────────────────────────────────────


def _section_requirements(template_stock: Dict[str, Any]) -> Dict[str, Optional[List[str]]]:
    requirements: Dict[str, Optional[List[str]]] = {}
    for section, value in template_stock.items():
        requirements[section] = list(value.keys()) if isinstance(value, dict) else None
    return requirements


def validate_legacy_analysis_json(
    path: Path, base_dir: Optional[Path] = None, allow_empty: bool = False
) -> Dict[str, Any]:
    errors: List[Dict[str, str]] = []
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        template = load_template(base_dir)
    except Exception as exc:  # noqa: BLE001
        return {"file": str(path), "ok": False, "errors": [_err("$", "parse_error", str(exc))],
                "warnings": []}

    for key in TOP_LEVEL_REQUIRED:
        if key not in data:
            errors.append(_err(key, "missing_section"))
    if "data_quality" in template and "data_quality" not in data:
        errors.append(_err("data_quality", "missing_section"))

    template_stocks = template.get("stocks") or []
    template_stock = template_stocks[0] if template_stocks and isinstance(template_stocks[0], dict) else {}
    requirements = _section_requirements(template_stock)

    stocks = data.get("stocks")
    if not isinstance(stocks, list):
        errors.append(_err("stocks", "not_a_list"))
        stocks = []
    elif not stocks and not allow_empty:
        errors.append(_err("stocks", "empty"))

    for index, stock in enumerate(stocks):
        if not isinstance(stock, dict):
            errors.append(_err(f"stocks[{index}]", "not_an_object"))
            continue
        for section, children in requirements.items():
            prefix = f"stocks[{index}].{section}"
            if section not in stock:
                errors.append(_err(prefix, "missing_section"))
                continue
            if children is None:
                continue
            value = stock[section]
            if not isinstance(value, dict):
                errors.append(_err(prefix, "not_an_object"))
                continue
            for child in children:
                if child not in value:
                    errors.append(_err(f"{prefix}.{child}", "missing_field"))
    return {"file": str(path), "ok": not errors, "errors": errors, "warnings": []}


# ─── date-level validation ──────────────────────────────────────────────────


def find_summary_json(date: str, base_dir: Optional[Path] = None) -> Optional[Path]:
    base = workspace_root(base_dir)
    date_dir = base / "analysis_results" / date
    if not date_dir.exists():
        return None
    exact = date_dir / f"stocks_analysis_{date}.json"
    if exact.exists():
        return exact
    candidates = sorted(date_dir.glob("stocks_analysis_*.json"))
    return candidates[0] if candidates else None


def _audit_for_date(date: str, base: Path) -> Dict[str, Any]:
    manifest = base / "data_files" / date / "manifest.json"
    if manifest.exists():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            datasets = data.get("datasets") or []
            simulated = sum(1 for item in datasets if item.get("is_simulated"))
            return {
                "source": "manifest",
                "dataset_count": len(datasets),
                "simulated_count": simulated,
                "has_simulated": simulated > 0,
            }
        except Exception:  # noqa: BLE001
            pass
    return audit_date_dir(date, base)


def _check_stock_markdown(date: str, stock_count: int, base: Path) -> List[Dict[str, str]]:
    warnings: List[Dict[str, str]] = []
    date_dir = base / "analysis_results" / date
    md_files = sorted(date_dir.glob(f"stock_*_analysis_{date}.md")) if date_dir.exists() else []
    if stock_count and not md_files:
        warnings.append(_err("analysis_results", "no_stock_markdown"))
        return warnings
    if stock_count and len(md_files) < stock_count:
        warnings.append(_err("analysis_results", "markdown_count_less_than_stocks",
                             f"{len(md_files)}<{stock_count}"))
    if md_files:
        sample = md_files[0].read_text(encoding="utf-8", errors="ignore")
        missing = [s for s in MD_REQUIRED_SNIPPETS if s not in sample]
        if missing:
            warnings.append(_err(f"analysis_results/{md_files[0].name}", "missing_md_modules",
                                 ",".join(missing)))
    return warnings


def validate_date(
    date: str,
    base_dir: Optional[Path] = None,
    strict: bool = False,
    allow_empty: bool = False,
    allow_v1: bool = False,
) -> Dict[str, Any]:
    base = workspace_root(base_dir)
    errors: List[Dict[str, str]] = []
    warnings: List[Dict[str, str]] = []

    summary = find_summary_json(date, base)
    payload: Dict[str, Any] = {}
    report_status: Optional[str] = None
    if summary is None:
        errors.append(_err("analysis_results", "missing_summary_json", f"date={date}"))
    else:
        try:
            payload = json.loads(summary.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            errors.append(_err("$", "parse_error", str(exc)))
            payload = {}
        version = str(payload.get("schema_version") or "")
        if version.startswith("2."):
            result = validate_analysis_json(summary, base, allow_empty=allow_empty)
            errors.extend(result["errors"])
            warnings.extend(result["warnings"])
        elif allow_v1:
            result = validate_legacy_analysis_json(summary, base, allow_empty)
            errors.extend(result["errors"])
            warnings.append(_err("schema_version", "legacy_v1", "validated with --allow-v1"))
        else:
            errors.append(
                _err("schema_version", "legacy_or_unsupported",
                     f"got={version!r}; re-generate with run_pipeline or pass --allow-v1")
            )
        report_status = (payload.get("data_quality") or {}).get("status")

    # data audit (manifest preferred; falls back to data_files scan)
    audit = _audit_for_date(date, base)
    audit_status = data_quality_status(audit)
    if audit.get("has_simulated"):
        warnings.append(_err("data_files", "contains_simulated_data",
                             f"{audit['simulated_count']} simulated dataset(s)"))
    if not (base / "data_files" / date / "manifest.json").exists():
        warnings.append(_err("data_files", "missing_manifest", str(base / "data_files" / date / "manifest.json")))

    # effective status = worse of declared report status and audit status
    report_rank = STATUS_RANK.get(str(report_status).lower(), -1)
    audit_rank = STATUS_RANK.get(audit_status, STATUS_RANK["missing"])
    if report_rank < 0:
        report_rank = audit_rank
    elif report_rank < audit_rank:
        errors.append(_err("data_quality.status", "status_understated",
                           f"report={report_status} audit={audit_status}"))
    effective_rank = max(report_rank, audit_rank)
    effective_status = STATUS_BY_RANK.get(effective_rank, audit_status)

    # buy gate uses the WORSE status (cannot be bypassed by claiming "real")
    if effective_rank > STATUS_RANK["real"]:
        offenders = []
        for stock in payload.get("stocks", []) or []:
            action = ((stock or {}).get("recommendation") or {}).get("action")
            if action in BUY_ACTIONS:
                offenders.append(str((stock.get("basic_info") or {}).get("code") or "?"))
        if offenders:
            errors.append(_err("recommendation", "buy_without_real_data",
                               f"effective_status={effective_status}; stocks={','.join(offenders)}"))

    stock_count = len(payload.get("stocks") or []) if payload else 0
    warnings.extend(_check_stock_markdown(date, stock_count, base))

    ok = not errors and not (strict and warnings)
    return {
        "date": date,
        "ok": ok,
        "strict": strict,
        "schema_version": payload.get("schema_version"),
        "data_quality_status": effective_status,
        "declared_status": report_status,
        "audit": audit,
        "summary_json": str(summary) if summary else None,
        "errors": errors,
        "warnings": warnings,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="QuanTr 分析产出校验器 (contract v2)")
    parser.add_argument("--date", required=True, help="分析日期 YYYY-MM-DD")
    parser.add_argument("--base-dir", default=None, help="quan_tr 项目根目录")
    parser.add_argument("--strict", action="store_true", help="警告也视为失败")
    parser.add_argument("--allow-empty", action="store_true", help="允许空股票列表")
    parser.add_argument("--allow-v1", action="store_true", help="兼容校验旧版 v1 报告")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出完整结果")
    args = parser.parse_args(argv)

    result = validate_date(
        args.date,
        base_dir=Path(args.base_dir) if args.base_dir else None,
        strict=args.strict,
        allow_empty=args.allow_empty,
        allow_v1=args.allow_v1,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        icon = "✅" if result["ok"] else "❌"
        print(f"{icon} 校验 {result['date']}  schema={result.get('schema_version')} "
              f"data_status={result['data_quality_status']}")
        for error in result["errors"]:
            print(f"  ❌ {error['path']}: {error['issue']} {error.get('detail', '')}".rstrip())
        for warning in result["warnings"]:
            print(f"  ⚠️  {warning['path']}: {warning['issue']} {warning.get('detail', '')}".rstrip())
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
