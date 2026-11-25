"""Tests for the optimized quant layer: provenance, market clock, validation."""

import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
QUANTR = ROOT / "quan_tr"

SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quantr import data_provenance, market_clock, validate_report  # noqa: E402


def _load_quantr_config():
    spec = importlib.util.spec_from_file_location("quantr_config", QUANTR / "config.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ─── market clock ───────────────────────────────────────────────────────────


def test_market_clock_weekend_rolls_back():
    assert market_clock.is_trading_day(date(2026, 11, 21)) is False  # Saturday
    assert market_clock.last_trading_day(date(2026, 11, 21)) == date(2026, 11, 20)
    info = market_clock.describe(date(2026, 11, 21))
    assert info["is_trading_day"] is False
    assert info["as_of"] == "2026-11-20"


def test_market_clock_holidays():
    holidays = {"2026-11-23"}
    assert market_clock.is_trading_day(date(2026, 11, 23), holidays=holidays) is False
    assert market_clock.last_trading_day(date(2026, 11, 23), holidays=holidays) == date(
        2026, 11, 20
    )


# ─── data provenance ────────────────────────────────────────────────────────


def test_is_simulated_detection():
    for note in ("基于前日数据模拟生成", "fake data", "synthetic", "随机生成"):
        assert data_provenance.is_simulated(note) is True
    assert data_provenance.is_simulated("AKshare 实时行情") is False


def test_write_manifest(tmp_path):
    base = tmp_path
    date_dir = base / "data_files" / "2026-01-01" / "akshare_data"
    date_dir.mkdir(parents=True)
    (date_dir / "real.json").write_text(
        json.dumps({"name": "x", "note": "AKshare 真实数据"}), encoding="utf-8"
    )
    (date_dir / "fake.json").write_text(
        json.dumps({"name": "y", "note": "模拟数据"}), encoding="utf-8"
    )
    out = data_provenance.write_manifest("2026-01-01", base_dir=base)
    manifest = json.loads(out.read_text(encoding="utf-8"))
    assert manifest["dataset_count"] == 2
    assert manifest["simulated_count"] == 1
    assert manifest["has_simulated"] is True
    assert manifest["data_quality_status"] == "partial"


def test_audit_detects_simulated_data(tmp_path):
    probe = tmp_path / "data_files" / "2026-05-19" / "akshare_data"
    probe.mkdir(parents=True)
    (probe / "basic_info.json").write_text(
        json.dumps({"name": "x", "note": "基于前日数据模拟生成"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (probe / "daily_data.json").write_text(json.dumps([{"close": 1.0}]), encoding="utf-8")
    audit = data_provenance.audit_date_dir("2026-05-19", base_dir=tmp_path)
    assert audit["has_simulated"] is True
    assert data_provenance.data_quality_status(audit) in {"partial", "simulated"}


# ─── analysis JSON validation ───────────────────────────────────────────────


def _template_payload():
    # v2 example is the canonical, invariant-valid payload
    return json.loads(json.dumps(validate_report.load_example(QUANTR)))


_TEMPLATE_FILES = (
    "stocks_analysis.schema.json",
    "stocks_analysis.example.json",
    "stocks_analysis_template.json",
)


def test_validate_analysis_json_accepts_template_shape(tmp_path):
    path = tmp_path / "ok.json"
    path.write_text(json.dumps(_template_payload()), encoding="utf-8")
    result = validate_report.validate_analysis_json(path, base_dir=QUANTR)
    assert result["ok"] is True, result["errors"]


def test_validate_analysis_json_flags_missing_field(tmp_path):
    payload = _template_payload()
    del payload["stocks"][0]["price"]["pe"]
    del payload["stocks"][0]["technical"]["macd"]
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = validate_report.validate_analysis_json(path, base_dir=QUANTR)
    assert result["ok"] is False
    issues = {err["path"] for err in result["errors"]}
    assert "stocks[0].price.pe" in issues
    assert "stocks[0].technical.macd" in issues


# ─── date-level gate: simulated data cannot produce buy ─────────────────────


def test_validate_date_blocks_buy_on_simulated_data(tmp_path):
    import shutil

    base = tmp_path
    templates = base / "analysis_results" / "templates"
    templates.mkdir(parents=True)
    for name in _TEMPLATE_FILES:
        shutil.copy(QUANTR / "analysis_results" / "templates" / name, templates / name)

    date_str = "2026-01-02"
    payload = _template_payload()
    payload["metadata"]["analysis_date"] = date_str
    payload["data_quality"]["status"] = "simulated"
    payload["data_quality"]["as_of"] = "2026-01-02"
    payload["stocks"][0]["recommendation"]["action"] = "buy"
    payload["summary"]["recommendations"] = {
        "strong_buy": 0, "buy": 1, "hold": 0, "sell": 0, "strong_sell": 0
    }
    (base / "analysis_results" / date_str).mkdir(parents=True)
    (base / "analysis_results" / date_str / f"stocks_analysis_{date_str}.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    data_dir = base / "data_files" / date_str / "akshare_data"
    data_dir.mkdir(parents=True)
    (data_dir / "fake.json").write_text(
        json.dumps({"note": "模拟数据"}), encoding="utf-8"
    )

    result = validate_report.validate_date(date_str, base_dir=base)
    assert result["ok"] is False
    issue_names = {err["issue"] for err in result["errors"]}
    assert "buy_without_real_data" in issue_names
    assert any(w["issue"] == "missing_manifest" for w in result["warnings"])
    assert any(w["issue"] == "contains_simulated_data" for w in result["warnings"])


# ─── config coherence + task prompts ───────────────────────────────────────


def test_scoring_weights_coherent():
    module = _load_quantr_config()
    weights = module.config.get_scoring_weights()
    assert set(weights) == {"fundamental", "technical", "risk", "sentiment"}
    assert abs(sum(weights.values()) - 1.0) < 1e-6


def test_task_generators_include_guardrails():
    import main_quan_tr as m

    for text in (m.generate_stock_analysis_task(rewrite=True), m.generate_backtest_task("weekly")):
        assert "quantr validate" in text
        assert "data_quality" in text
        assert "禁止" in text
        assert "数据 as_of" in text
