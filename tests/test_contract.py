"""Contract v2 tests: schema, invariants, buy-gate loophole, legacy handling."""

import copy
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
QUANTR = ROOT / "examples" / "workspace"
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quantr import validate_report  # noqa: E402

TEMPLATE_FILES = (
    "stocks_analysis.schema.json",
    "stocks_analysis.example.json",
    "stocks_analysis_template.json",
)
DATE = "2026-11-24"


def _example():
    return copy.deepcopy(validate_report.load_example(QUANTR))


def _seed_templates(base: Path):
    tdir = base / "analysis_results" / "templates"
    tdir.mkdir(parents=True, exist_ok=True)
    for name in TEMPLATE_FILES:
        shutil.copy(QUANTR / "analysis_results" / "templates" / name, tdir / name)


def _write_report(base: Path, payload: dict, date: str = DATE):
    d = base / "analysis_results" / date
    d.mkdir(parents=True, exist_ok=True)
    (d / f"stocks_analysis_{date}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def _write_md(base: Path, date: str = DATE):
    d = base / "analysis_results" / date
    (d / f"stock_x_000001_SZ_analysis_{date}.md").write_text(
        "# x\n## 基本信息\n## 价格\n## 基本面\n## 技术面\n## 风险\n## 投资建议\n",
        encoding="utf-8",
    )


# ─── schema basics ──────────────────────────────────────────────────────────


def test_example_is_valid():
    result = validate_report.validate_analysis_json(
        _write_to_tmp(_example()), base_dir=QUANTR
    )
    assert result["ok"] is True, result["errors"]


def _write_to_tmp(payload, tmp_path_factory=None):
    import tempfile

    path = Path(tempfile.mkdtemp(prefix="contract_")) / "payload.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_schema_rejects_bad_enum_and_range(tmp_path):
    payload = _example()
    payload["stocks"][0]["technical"]["trend"] = "横盘"
    payload["stocks"][0]["scores"]["overall"] = 999
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = validate_report.validate_analysis_json(path, base_dir=QUANTR)
    assert result["ok"] is False
    issues = {e["issue"] for e in result["errors"]}
    assert "schema" in issues


def test_schema_rejects_wrong_market(tmp_path):
    payload = _example()
    payload["stocks"][0]["basic_info"]["market"] = "A股"  # legacy value, not allowed in v2
    path = tmp_path / "bad_market.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = validate_report.validate_analysis_json(path, base_dir=QUANTR)
    assert result["ok"] is False


# ─── invariants ─────────────────────────────────────────────────────────────


def test_total_stocks_mismatch_detected(tmp_path):
    payload = _example()
    payload["metadata"]["total_stocks"] = 5
    path = tmp_path / "p.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = validate_report.validate_analysis_json(path, base_dir=QUANTR)
    assert any(e["issue"] == "derived_mismatch" for e in result["errors"])


def test_recommendation_counts_mismatch(tmp_path):
    payload = _example()
    payload["summary"]["recommendations"]["hold"] = 0
    path = tmp_path / "p.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = validate_report.validate_analysis_json(path, base_dir=QUANTR)
    assert any(e["issue"] == "derived_mismatch" for e in result["errors"])


def test_target_stop_sanity(tmp_path):
    payload = _example()
    price = payload["stocks"][0]["price"]["current"]
    payload["stocks"][0]["recommendation"]["target_price"] = price - 1
    payload["stocks"][0]["recommendation"]["stop_loss"] = price + 1
    path = tmp_path / "p.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = validate_report.validate_analysis_json(path, base_dir=QUANTR)
    issues = {e["issue"] for e in result["errors"]}
    assert "target_not_above_current" in issues
    assert "stop_not_below_current" in issues


def test_action_overall_inconsistent(tmp_path):
    payload = _example()
    payload["stocks"][0]["scores"]["overall"] = 30  # buy needs >= 60
    payload["stocks"][0]["recommendation"]["action"] = "buy"
    payload["summary"]["recommendations"] = {
        "strong_buy": 0, "buy": 1, "hold": 0, "sell": 0, "strong_sell": 0
    }
    path = tmp_path / "p.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = validate_report.validate_analysis_json(path, base_dir=QUANTR)
    # score inconsistent with subscores AND action inconsistent
    issues = {e["issue"] for e in result["errors"]}
    assert "action_inconsistent" in issues


# ─── data-integrity gate: cannot bypass by claiming "real" ──────────────────


def test_buy_gate_cannot_be_bypassed_by_claiming_real(tmp_path):
    _seed_templates(tmp_path)
    payload = _example()
    payload["metadata"]["analysis_date"] = DATE
    payload["data_quality"]["as_of"] = DATE
    payload["data_quality"]["status"] = "real"  # lie
    payload["stocks"][0]["recommendation"]["action"] = "buy"
    payload["stocks"][0]["scores"]["overall"] = 70.0
    payload["stocks"][0]["scores"]["technical"] = 70.0
    payload["summary"]["recommendations"] = {
        "strong_buy": 0, "buy": 1, "hold": 0, "sell": 0, "strong_sell": 0
    }
    _write_report(tmp_path, payload)
    _write_md(tmp_path)
    # manifest says the data was simulated
    mdir = tmp_path / "data_files" / DATE
    mdir.mkdir(parents=True)
    (mdir / "manifest.json").write_text(
        json.dumps({"date": DATE, "datasets": [{"symbol": "000001.SZ", "is_simulated": True}]}),
        encoding="utf-8",
    )

    result = validate_report.validate_date(DATE, base_dir=tmp_path)
    issues = {e["issue"] for e in result["errors"]}
    assert result["ok"] is False
    assert "status_understated" in issues
    assert "buy_without_real_data" in issues


# ─── legacy handling ────────────────────────────────────────────────────────


def test_legacy_v1_rejected_without_allow(tmp_path):
    _seed_templates(tmp_path)
    v1 = validate_report.load_template(QUANTR)
    v1["metadata"]["analysis_date"] = DATE
    _write_report(tmp_path, v1)
    result = validate_report.validate_date(DATE, base_dir=tmp_path)
    assert any(e["issue"] == "legacy_or_unsupported" for e in result["errors"])


def test_legacy_v1_accepted_with_allow(tmp_path):
    _seed_templates(tmp_path)
    v1 = validate_report.load_template(QUANTR)
    v1["metadata"]["analysis_date"] = DATE
    _write_report(tmp_path, v1)
    result = validate_report.validate_date(DATE, base_dir=tmp_path, allow_v1=True)
    assert any(w["issue"] == "legacy_v1" for w in result["warnings"])
    assert not any(e["issue"] == "legacy_or_unsupported" for e in result["errors"])
