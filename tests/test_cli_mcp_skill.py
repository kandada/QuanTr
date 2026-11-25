"""Tests for the packaged interfaces: unified CLI, MCP server, library, skill."""

import json
import os
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
QUANTR = ROOT / "quan_tr"
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quantr import schema, data_store, service, cli, mcp_server  # noqa: E402
from quantr import api as quantr_api  # noqa: E402


def make_prices(n=320, start=10.0, end=18.0):
    dates = pd.bdate_range("2024-01-01", periods=n)
    x = np.arange(n)
    close = pd.Series(np.linspace(start, end, n) + np.sin(x / 9) * 0.15)
    return schema.normalize_ohlcv(
        pd.DataFrame(
            {
                "date": dates,
                "open": close * 0.998,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": np.full(n, 1_000_000),
            }
        )
    )


def seed_base(tmp_path, note="real fixture", source="akshare", n=320):
    tdir = tmp_path / "analysis_results" / "templates"
    tdir.mkdir(parents=True)
    for name in (
        "stocks_analysis.schema.json",
        "stocks_analysis.example.json",
        "stocks_analysis_template.json",
    ):
        shutil.copy(QUANTR / "analysis_results" / "templates" / name, tdir / name)
    data_store.save_ohlcv(
        make_prices(n=n), "000001.SZ", source=source, note=note,
        base_dir=tmp_path, merge=False,
    )


# ─── service/library ────────────────────────────────────────────────────────


def test_service_facade(tmp_path):
    seed_base(tmp_path)
    store = service.store(tmp_path)
    assert store["ok"] and store["count"] == 1

    ind = service.indicators("000001.SZ", tmp_path)
    assert ind["ok"] and "snapshot" in ind

    fac = service.factors("000001.SZ", tmp_path)
    assert fac["ok"] and 0 <= fac["overall"] <= 100

    bt = service.backtest("000001.SZ", base_dir=tmp_path, walk_forward=True)
    assert bt["ok"] and bt["mode"] == "walk_forward"

    q = quantr_api.Quantr(base_dir=str(tmp_path))
    assert q.indicators("000001.SZ")["ok"] is True


# ─── CLI ────────────────────────────────────────────────────────────────────


def _parse_stdout(capsys):
    out = capsys.readouterr().out.strip()
    return json.loads(out)


def test_cli_factors_json(tmp_path, capsys):
    seed_base(tmp_path)
    rc = cli.main(["factors", "--symbol", "000001.SZ", "--base-dir", str(tmp_path), "--json"])
    payload = _parse_stdout(capsys)
    assert rc == 0
    assert payload["ok"] is True and payload["command"] == "factors"
    assert payload["result"]["symbol"] == "000001.SZ"


def test_cli_missing_data_is_error(tmp_path, capsys):
    seed_base(tmp_path)
    rc = cli.main(["indicators", "--symbol", "600000.SH", "--base-dir", str(tmp_path), "--json"])
    payload = _parse_stdout(capsys)
    assert rc == 1
    assert payload["ok"] is False
    assert "no local data" in payload["error"]


def test_cli_pipeline_then_validate(tmp_path, capsys):
    seed_base(tmp_path)
    rc = cli.main(
        ["pipeline", "--symbols", "000001.SZ", "--date", "2026-11-24",
         "--offline", "--base-dir", str(tmp_path), "--json"]
    )
    payload = _parse_stdout(capsys)
    assert rc == 0, payload
    assert payload["ok"] is True
    assert payload["result"]["data_quality"]["status"] == "real"
    assert payload["result"]["validation"]["ok"] is True

    rc2 = cli.main(
        ["validate", "--date", "2026-11-24", "--strict", "--base-dir", str(tmp_path), "--json"]
    )
    payload2 = _parse_stdout(capsys)
    assert rc2 == 0
    assert payload2["result"]["ok"] is True


def test_cli_store(tmp_path, capsys):
    seed_base(tmp_path)
    rc = cli.main(["store", "--base-dir", str(tmp_path), "--json"])
    payload = _parse_stdout(capsys)
    assert rc == 0 and payload["result"]["count"] == 1


# ─── MCP ────────────────────────────────────────────────────────────────────


def test_mcp_list_and_call(tmp_path):
    names = {tool["name"] for tool in mcp_server.list_tools()}
    assert {"fetch_ohlcv", "compute_factors", "run_backtest", "validate_report", "run_pipeline"} <= names

    seed_base(tmp_path)
    res = mcp_server.call_tool(
        "compute_factors", {"symbol": "000001.SZ", "base_dir": str(tmp_path)}
    )
    assert res["ok"] is True and res["result"]["ok"] is True

    bad = mcp_server.call_tool("does_not_exist", {})
    assert bad["ok"] is False

    missing = mcp_server.call_tool(
        "compute_indicators", {"symbol": "600000.SH", "base_dir": str(tmp_path)}
    )
    assert missing["ok"] is False


def test_mcp_build_app_if_sdk_present():
    try:
        import mcp.server.fastmcp  # noqa: F401
    except Exception:
        pytest.skip("mcp SDK not installed")
    app = mcp_server.build_app()
    assert app is not None


# ─── skill + shim ───────────────────────────────────────────────────────────


def test_skill_document_exists():
    skill = QUANTR / "skills" / "quan_tr" / "SKILL.md"
    assert skill.exists()
    text = skill.read_text(encoding="utf-8")
    assert "quantr" in text
    assert "validate" in text and "--strict" in text
    assert "REAL" in text or "真实" in text


def test_skill_install(tmp_path):
    target = service.skill_path(dest_dir=tmp_path)
    assert target == tmp_path / "quan_tr"
    res = service.install_skill(dest_dir=tmp_path)
    assert res["ok"] is True
    assert (Path(res["target"]) / "SKILL.md").exists()


def test_cli_skill_install(tmp_path, capsys):
    rc = cli.main(["skill", "install", "--dest", str(tmp_path), "--json"])
    payload = _parse_stdout(capsys)
    assert rc == 0 and payload["ok"] is True
    assert (Path(payload["result"]["target"]) / "SKILL.md").exists()

    rc2 = cli.main(["skill", "path", "--dest", str(tmp_path), "--json"])
    payload2 = _parse_stdout(capsys)
    assert rc2 == 0 and payload2["result"]["target"] == str(tmp_path / "quan_tr")


def test_quantr_shim_executable():
    shim = ROOT / "quantr"
    assert shim.exists()
    assert os.access(shim, os.X_OK)
    assert "quantr" in shim.read_text(encoding="utf-8")
