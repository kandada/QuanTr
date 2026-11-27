"""UX tests for the CLI: version, doctor, fetch --pool, error hints, output."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quantr import __version__, cli, service  # noqa: E402


def _json(capsys):
    return json.loads(capsys.readouterr().out)


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "quantr" in out and __version__ in out


def test_doctor_json(capsys):
    rc = cli.main(["doctor", "--json"])
    payload = _json(capsys)
    assert rc == 0 and payload["ok"] is True
    result = payload["result"]
    for key in ("version", "workspace", "is_workspace", "templates_source", "dependencies"):
        assert key in result
    assert result["version"] == __version__


def test_doctor_detects_workspace(tmp_path, capsys):
    tdir = tmp_path / "analysis_results" / "templates"
    tdir.mkdir(parents=True)
    (tdir / "stocks_analysis.schema.json").write_text("{}", encoding="utf-8")
    (tmp_path / "stocks_pool.json").write_text('{"stocks": []}', encoding="utf-8")
    (tmp_path / "config.yaml").write_text("", encoding="utf-8")

    rc = cli.main(["doctor", "--base-dir", str(tmp_path), "--json"])
    result = _json(capsys)["result"]
    assert rc == 0
    assert result["is_workspace"] is True
    assert result["templates_source"] == "workspace"


def test_fetch_pool_uses_workspace_symbols(tmp_path, monkeypatch, capsys):
    (tmp_path / "stocks_pool.json").write_text(
        json.dumps({"stocks": [{"symbol": "000001.SZ"}]}), encoding="utf-8"
    )
    captured = {}

    def fake_fetch(symbols, *args, **kwargs):
        captured["symbols"] = symbols
        return {"ok": True, "records": [{"ok": True, "symbol": symbols[0], "rows": 1}]}

    monkeypatch.setattr(service, "fetch", fake_fetch)
    rc = cli.main(["fetch", "--pool", "--base-dir", str(tmp_path), "--json"])
    assert rc == 0
    assert captured["symbols"] == ["000001.SZ"]


def test_fetch_without_symbols_has_hint(tmp_path, capsys):
    rc = cli.main(["fetch", "--base-dir", str(tmp_path), "--json"])
    payload = _json(capsys)
    assert rc == 1
    assert payload["ok"] is False
    assert "no symbols" in payload["error"].lower()
    assert "hint" in payload


def test_human_output_smoke(capsys):
    cli._human(
        "factors",
        {
            "ok": True,
            "command": "factors",
            "result": {
                "symbol": "000001.SZ",
                "overall": 61.7,
                "action": "hold",
                "confidence": "medium",
                "subscores": {"fundamental": None, "technical": 68, "risk": 55, "sentiment": None},
                "risk": {"level": "medium", "score": 45, "factors": ["行业周期"]},
                "notes": ["fundamental 维度数据缺失，未计入总分"],
            },
        },
    )
    out = capsys.readouterr().out
    assert "000001.SZ" in out and "overall=61.7" in out and "note:" in out

    cli._human(
        "pipeline",
        {
            "ok": True,
            "command": "pipeline",
            "result": {
                "date": "2026-11-24",
                "symbols": ["000001.SZ"],
                "data_quality": {"status": "real", "as_of": "2026-11-24"},
                "ranking": [{"rank": 1, "symbol": "000001.SZ", "overall": 61.7, "action": "hold"}],
                "portfolio": {
                    "method": "score_weight",
                    "invested_weight": 0.8,
                    "cash_weight": 0.2,
                    "constituents": [{"symbol": "000001.SZ", "weight": 0.8, "score": 61.7}],
                },
                "benchmark": {"symbol": "000300.SH", "return": 0.03, "as_of": "2026-11-24"},
                "json": "x.json",
                "validation": {"ok": True},
            },
        },
    )
    out = capsys.readouterr().out
    assert "ranking:" in out and "portfolio:" in out and "validation: OK" in out


def test_fail_hint_for_missing_data(capsys):
    rc = cli._fail("factors", ValueError("no local data for X; run quantr fetch"), False)
    out = capsys.readouterr().out
    assert rc == 1
    assert "→" in out
