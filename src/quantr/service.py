# src/quantr/service.py
"""Stable service layer shared by CLI, MCP server and library facade.

Every function returns a JSON-serializable dict and never fabricates data.
This is the single place that wires the deterministic engine together, so the
CLI/MCP/library stay in sync.
"""

from __future__ import annotations

import importlib.util
import json
import platform
from pathlib import Path
from typing import Any, Dict, List, Optional

from .schema import parse_symbol  # noqa: E402
from ._paths import workspace_root  # noqa: E402
from .data_store import get_meta, list_symbols, load_ohlcv  # noqa: E402
from .indicators import compute_snapshot  # noqa: E402
from .factor_engine import compute_scores  # noqa: E402
from .engine import run_backtest, walk_forward_ma  # noqa: E402
from .validate_report import validate_date  # noqa: E402



def _base(base_dir: Optional[Path | str]) -> Path:
    return workspace_root(base_dir)


def load_config(base_dir: Optional[Path | str] = None) -> Optional[Dict[str, Any]]:
    """Load workspace config.py -> merged config dict (best effort)."""
    root = _base(base_dir)
    path = root / "config.py"
    if not path.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location("quantr_config", path)
        module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        return module.config.config
    except Exception:  # noqa: BLE001
        return None


# ─── data ───────────────────────────────────────────────────────────────────


def fetch(
    symbols: List[str],
    start: Optional[str] = None,
    end: Optional[str] = None,
    source: str = "auto",
    save: bool = True,
    base_dir: Optional[Path | str] = None,
) -> Dict[str, Any]:
    from .market_data import fetch_ohlcv, update_store  # lazy import

    base = _base(base_dir)
    if save:
        records = update_store(symbols, start, end, source, base)
    else:
        records = []
        for symbol in symbols:
            try:
                df, used = fetch_ohlcv(symbol, start, end, source)
                records.append(
                    {
                        "ok": True,
                        "symbol": parse_symbol(symbol)["canonical"],
                        "source": used,
                        "rows": int(len(df)),
                        "first_date": str(df["date"].iloc[0].date()),
                        "last_date": str(df["date"].iloc[-1].date()),
                    }
                )
            except Exception as exc:  # noqa: BLE001
                records.append(
                    {"ok": False, "symbol": symbol, "error": f"{type(exc).__name__}: {exc}"}
                )
    ok = bool(records) and all(r.get("ok") for r in records)
    return {"ok": ok, "records": records}


def store(base_dir: Optional[Path | str] = None) -> Dict[str, Any]:
    base = _base(base_dir)
    items = []
    for symbol in list_symbols(base):
        meta = get_meta(symbol, base) or {}
        items.append({"symbol": symbol, **meta})
    return {"ok": True, "count": len(items), "symbols": items}


def workspace_symbols(base_dir: Optional[Path | str] = None) -> List[str]:
    """Read symbols from ``<workspace>/stocks_pool.json`` (raw forms ok)."""
    path = _base(base_dir) / "stocks_pool.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    return [str(item["symbol"]) for item in data.get("stocks", []) if item.get("symbol")]


def _pkg_version(name: str) -> Optional[str]:
    try:
        from importlib import metadata

        return metadata.version(name)
    except Exception:  # noqa: BLE001
        return None


def doctor(base_dir: Optional[Path | str] = None) -> Dict[str, Any]:
    """Environment / workspace diagnostics for `quantr doctor`."""
    from . import __version__
    from ._paths import PACKAGE_DIR, TEMPLATES_DIR, templates_dir

    base = _base(base_dir)
    markers = {
        "stocks_pool.json": (base / "stocks_pool.json").exists(),
        "config.yaml": (base / "config.yaml").exists(),
        "analysis_results/templates": (base / "analysis_results" / "templates").is_dir(),
    }
    is_workspace = all(markers.values())
    tdir = templates_dir(base)
    symbols = list_symbols(base)
    deps = {name: _pkg_version(name) for name in ("pandas", "numpy", "duckdb", "PyYAML")}

    hints: List[str] = []
    if not is_workspace:
        hints.append("当前目录不是工作区：运行 `quantr init <dir>`，或用 --base-dir 指定。")
    if not symbols:
        hints.append("数据仓为空：先 `quantr fetch --symbols 000001.SZ --save`（或 `--pool`）。")
    if _pkg_version("aacode") is None:
        hints.append('未安装 aacode（可选）：`pip install "quantr-engine[agent]"`。')
    if _pkg_version("mcp") is None:
        hints.append('未安装 mcp（可选）：`pip install "quantr-engine[mcp]"`。')

    return {
        "ok": True,
        "version": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "package_dir": str(PACKAGE_DIR),
        "workspace": str(base),
        "is_workspace": is_workspace,
        "workspace_markers": markers,
        "templates_source": "workspace" if tdir != TEMPLATES_DIR else "package",
        "templates_dir": str(tdir),
        "store_symbols": len(symbols),
        "dependencies": deps,
        "aacode": _pkg_version("aacode"),
        "mcp": _pkg_version("mcp"),
        "hints": hints,
    }


# ─── analysis ───────────────────────────────────────────────────────────────


def indicators(
    symbol: str, base_dir: Optional[Path | str] = None
) -> Dict[str, Any]:
    base = _base(base_dir)
    df = load_ohlcv(symbol, base_dir=base)
    if df is None or len(df) == 0:
        raise ValueError(f"no local data for {symbol}; run `quantr fetch --save` first")
    config = load_config(base)
    snapshot = compute_snapshot(df, config)
    return {"ok": True, "symbol": parse_symbol(symbol)["canonical"], "snapshot": snapshot}


def factors(
    symbol: str,
    base_dir: Optional[Path | str] = None,
    fundamentals: Optional[Dict[str, Any]] = None,
    allow_buy: Optional[bool] = None,
) -> Dict[str, Any]:
    base = _base(base_dir)
    df = load_ohlcv(symbol, base_dir=base)
    if df is None or len(df) == 0:
        raise ValueError(f"no local data for {symbol}; run `quantr fetch --save` first")
    config = load_config(base)
    meta = get_meta(symbol, base) or {}
    if allow_buy is None:
        allow_buy = (not meta.get("is_simulated")) and fundamentals is not None
    result = compute_scores(df, fundamentals=fundamentals, config=config, allow_buy=allow_buy)
    return {"ok": True, "symbol": parse_symbol(symbol)["canonical"], **result}


# ─── backtest ───────────────────────────────────────────────────────────────


def backtest(
    symbol: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    signals: Optional[Dict[str, Any]] = None,
    walk_forward: bool = False,
    base_dir: Optional[Path | str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    base = _base(base_dir)
    df = load_ohlcv(symbol, start, end, base_dir=base)
    if df is None or len(df) < 2:
        raise ValueError(f"insufficient local data for {symbol}; run `quantr fetch --save` first")
    cfg = config if config is not None else load_config(base)
    if walk_forward or not signals:
        result = walk_forward_ma(df, config=cfg)
        result["mode"] = "walk_forward"
    else:
        result = run_backtest(df, signals, cfg)
        result["mode"] = "signals"
    return {"ok": True, "symbol": parse_symbol(symbol)["canonical"], **result}


# ─── validation + pipeline ─────────────────────────────────────────────────


def validate(
    date: str,
    base_dir: Optional[Path | str] = None,
    strict: bool = False,
    allow_v1: bool = False,
) -> Dict[str, Any]:
    return validate_date(
        date, base_dir=_base(base_dir), strict=strict, allow_v1=allow_v1
    )


def pipeline(
    date: Optional[str] = None,
    symbols: Optional[List[str]] = None,
    base_dir: Optional[Path | str] = None,
    offline: bool = False,
    source: str = "auto",
    mode: str = "all",
    run_backtest: bool = True,
    universe: Optional[str] = None,
    portfolio_top_n: int = 5,
    portfolio_method: str = "score_weight",
) -> Dict[str, Any]:
    from . import run_pipeline  # lazy import (heavier dependency graph)

    base = _base(base_dir)
    return run_pipeline.run_pipeline(
        date_str=date,
        symbols=symbols,
        base_dir=base,
        offline=offline,
        source=source,
        mode=mode,
        config=load_config(base),
        run_backtest=run_backtest,
        universe=universe,
        portfolio_top_n=portfolio_top_n,
        portfolio_method=portfolio_method,
    )


# ─── skill install ──────────────────────────────────────────────────────────


def skill_path(dest_dir: Optional[Path | str] = None) -> Path:
    """Where the QuanTr skill should be installed for aacode discovery."""
    if dest_dir:
        return Path(dest_dir) / "quan_tr"
    try:
        import platformdirs

        root = Path(platformdirs.user_config_dir("com.aacode", roaming=True)) / "skills"
    except Exception:  # pragma: no cover
        root = Path.home() / ".aacode" / "skills"
    return root / "quan_tr"


def install_skill(dest_dir: Optional[Path | str] = None) -> Dict[str, Any]:
    """Install the packaged SKILL.md into aacode's user skills directory."""
    import shutil

    from ._paths import SKILL_DIR

    src = SKILL_DIR / "SKILL.md"
    if not src.exists():
        raise ValueError(f"packaged skill not found: {src}")
    target = skill_path(dest_dir)
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, target / "SKILL.md")
    return {"ok": True, "source": str(src), "target": str(target)}


def init_workspace(target: Optional[Path | str] = None, force: bool = False) -> Dict[str, Any]:
    """Scaffold a Quantr workspace (dirs, templates, skill, config, init.md)."""
    import shutil

    from ._paths import SKILL_DIR, TEMPLATES_DIR, WORKSPACE_TEMPLATE_DIR

    root = Path(target or ".").expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    dirs = [
        "analysis_results/templates",
        "backtest_reports",
        "data_files",
        "store/ohlcv",
        "store/fundamentals",
        "store/universe",
        "programs",
        "skills/quan_tr",
    ]
    for rel in dirs:
        (root / rel).mkdir(parents=True, exist_ok=True)

    created = []

    def _copy(src: Path, dest: Path):
        if dest.exists() and not force:
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        created.append(str(dest))

    for name in TEMPLATES_DIR.glob("*"):
        _copy(name, root / "analysis_results" / "templates" / name.name)
    _copy(SKILL_DIR / "SKILL.md", root / "skills" / "quan_tr" / "SKILL.md")

    scaffold = {
        "init.md": "init.md",
        "config.yaml": "config.yaml",
        "stocks_pool.json": "stocks_pool.json",
        "gitignore.txt": ".gitignore",
    }
    for src_name, dest_name in scaffold.items():
        src = WORKSPACE_TEMPLATE_DIR / src_name
        if src.exists():
            _copy(src, root / dest_name)

    return {"ok": True, "root": str(root), "created": created, "force": force}
