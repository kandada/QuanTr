"""Packaging integrity: version sync, assets present, no data leaks, no drift."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "src" / "quantr"
QUANTR = ROOT / "quan_tr"


def _pyproject():
    tomllib = pytest.importorskip("tomllib")
    with (ROOT / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)


def test_version_is_single_source():
    import quantr

    cfg = _pyproject()
    assert cfg["project"]["version"] == quantr.__version__


def test_core_dependencies_declared():
    cfg = _pyproject()
    deps = " ".join(cfg["project"]["dependencies"]).lower()
    for package in ("pandas", "numpy", "duckdb", "pyyaml"):
        assert package in deps


def test_console_script_declared():
    cfg = _pyproject()
    assert cfg["project"]["scripts"]["quantr"].startswith("quantr.")


def test_package_assets_present():
    assert (PKG / "templates" / "stocks_analysis.schema.json").exists()
    assert (PKG / "templates" / "stocks_analysis.example.json").exists()
    assert (PKG / "templates" / "stocks_analysis_template.md").exists()
    assert (PKG / "skill" / "SKILL.md").exists()
    for name in ("init.md", "config.yaml", "stocks_pool.json", "gitignore.txt"):
        assert (PKG / "workspace_template" / name).exists()


def test_no_market_data_in_package():
    for forbidden in ("store", "analysis_results", "data_files", "backtest_reports"):
        assert not (PKG / forbidden).exists(), f"package must not contain {forbidden}/"


def test_packaged_templates_not_drifted_from_workspace():
    # The repo workspace keeps copies for local runs; keep them byte-identical.
    for name in (
        "stocks_analysis.schema.json",
        "stocks_analysis.example.json",
        "stocks_analysis_template.json",
    ):
        workspace = (QUANTR / "analysis_results" / "templates" / name).read_bytes()
        packaged = (PKG / "templates" / name).read_bytes()
        assert workspace == packaged, f"template drift: {name}"


def test_skill_not_drifted():
    workspace = (QUANTR / "skills" / "quan_tr" / "SKILL.md").read_bytes()
    packaged = (PKG / "skill" / "SKILL.md").read_bytes()
    assert workspace == packaged, "SKILL.md drift between workspace and package"
