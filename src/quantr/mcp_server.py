# quan_tr/programs/mcp_server.py
"""MCP server exposing QuanTr's deterministic quant capabilities as tools.

Design: ``list_tools()`` + ``call_tool()`` carry the logic and are testable
without the MCP SDK. ``build_app()`` lazily wraps them with FastMCP for stdio.

Run:
    python programs/mcp_server.py            # stdio MCP server
    python programs/mcp_server.py --list     # print tool schemas (debug)

Tools only return JSON text; they never fabricate data and never call an LLM.
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List, Optional

from . import service

_STR = {"type": "string"}
_BOOL = {"type": "boolean"}
_BASE = {"type": "string", "description": "quan_tr project root (optional)"}

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "fetch_ohlcv",
        "description": "Fetch REAL OHLCV from AKshare/Yahoo and optionally save to the local store. Fails instead of fabricating data.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbols": {"type": "array", "items": _STR, "description": "e.g. ['000001.SZ']"},
                "start": {"type": "string", "description": "YYYY-MM-DD"},
                "end": {"type": "string", "description": "YYYY-MM-DD"},
                "source": {"type": "string", "enum": ["auto", "akshare", "yfinance"]},
                "save": {"type": "boolean", "default": True},
                "base_dir": _BASE,
            },
            "required": ["symbols"],
        },
    },
    {
        "name": "list_store",
        "description": "List symbols and metadata in the local OHLCV store.",
        "inputSchema": {"type": "object", "properties": {"base_dir": _BASE}},
    },
    {
        "name": "compute_indicators",
        "description": "Compute deterministic technical indicators snapshot for a stored symbol.",
        "inputSchema": {
            "type": "object",
            "properties": {"symbol": _STR, "base_dir": _BASE},
            "required": ["symbol"],
        },
    },
    {
        "name": "compute_factors",
        "description": "Deterministic factor scores (technical/risk from indicators; fundamental only if provided) + recommendation. Buy is capped unless real data + fundamentals.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": _STR,
                "fundamentals": {"type": "object", "description": "e.g. {pe, pb, roe, debt_ratio, revenue_growth, profit_growth}"},
                "allow_buy": _BOOL,
                "base_dir": _BASE,
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "run_backtest",
        "description": "Backtest with costs/slippage/stamp duty. Default walk-forward (MA grid); or pass explicit signals {date: action}.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": _STR,
                "start": _STR,
                "end": _STR,
                "signals": {"type": "object", "description": "{'YYYY-MM-DD': 'buy'|'sell'|'hold'}"},
                "walk_forward": _BOOL,
                "base_dir": _BASE,
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "validate_report",
        "description": "Validate a date's outputs: template field completeness, simulated-data detection, buy-without-real-data gate.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date": _STR,
                "strict": _BOOL,
                "allow_v1": _BOOL,
                "base_dir": _BASE,
            },
            "required": ["date"],
        },
    },
    {
        "name": "run_pipeline",
        "description": "End-to-end reproducible pipeline: fetch -> indicators/factors -> template JSON + MD + manifest -> validate.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date": _STR,
                "symbols": {"type": "array", "items": _STR},
                "offline": _BOOL,
                "source": {"type": "string", "enum": ["auto", "akshare", "yfinance"]},
                "mode": {"type": "string", "enum": ["all", "fetch", "analyze", "backtest"]},
                "run_backtest": _BOOL,
                "universe": {"type": "string", "description": "PIT universe index name"},
                "portfolio_top_n": {"type": "integer", "minimum": 0},
                "portfolio_method": {"type": "string", "enum": ["score_weight", "equal_weight"]},
                "base_dir": _BASE,
            },
        },
    },
]


def list_tools() -> List[Dict[str, Any]]:
    return TOOLS


def call_tool(name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    args = arguments or {}
    try:
        if name == "fetch_ohlcv":
            result = service.fetch(
                args.get("symbols") or [],
                args.get("start"),
                args.get("end"),
                args.get("source", "auto"),
                args.get("save", True),
                args.get("base_dir"),
            )
        elif name == "list_store":
            result = service.store(args.get("base_dir"))
        elif name == "compute_indicators":
            result = service.indicators(args["symbol"], args.get("base_dir"))
        elif name == "compute_factors":
            result = service.factors(
                args["symbol"],
                args.get("base_dir"),
                args.get("fundamentals"),
                args.get("allow_buy"),
            )
        elif name == "run_backtest":
            result = service.backtest(
                args["symbol"],
                args.get("start"),
                args.get("end"),
                args.get("signals"),
                bool(args.get("walk_forward", not args.get("signals"))),
                args.get("base_dir"),
            )
        elif name == "validate_report":
            result = service.validate(
                args["date"],
                args.get("base_dir"),
                bool(args.get("strict", False)),
                bool(args.get("allow_v1", False)),
            )
        elif name == "run_pipeline":
            result = service.pipeline(
                date=args.get("date"),
                symbols=args.get("symbols"),
                base_dir=args.get("base_dir"),
                offline=bool(args.get("offline", False)),
                source=args.get("source", "auto"),
                mode=args.get("mode", "all"),
                run_backtest=bool(args.get("run_backtest", True)),
                universe=args.get("universe"),
                portfolio_top_n=int(args.get("portfolio_top_n", 5)),
                portfolio_method=args.get("portfolio_method", "score_weight"),
            )
        else:
            return {"ok": False, "error": f"unknown tool: {name}"}
        return {"ok": True, "tool": name, "result": result}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "tool": name, "error": f"{type(exc).__name__}: {exc}"}


def build_app():
    """Build a FastMCP app with thin wrappers over ``call_tool``."""
    from mcp.server.fastmcp import FastMCP

    app = FastMCP("quantr")

    def _text(payload: Dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False, default=str)

    @app.tool()
    def fetch_ohlcv(
        symbols: List[str],
        start: Optional[str] = None,
        end: Optional[str] = None,
        source: str = "auto",
        save: bool = True,
        base_dir: Optional[str] = None,
    ) -> str:
        """Fetch REAL OHLCV (no fabricated data) and optionally save to store."""
        return _text(
            call_tool(
                "fetch_ohlcv",
                {"symbols": symbols, "start": start, "end": end,
                 "source": source, "save": save, "base_dir": base_dir},
            )
        )

    @app.tool()
    def list_store(base_dir: Optional[str] = None) -> str:
        """List symbols in the local OHLCV store."""
        return _text(call_tool("list_store", {"base_dir": base_dir}))

    @app.tool()
    def compute_indicators(symbol: str, base_dir: Optional[str] = None) -> str:
        """Deterministic technical indicators snapshot."""
        return _text(call_tool("compute_indicators", {"symbol": symbol, "base_dir": base_dir}))

    @app.tool()
    def compute_factors(
        symbol: str,
        fundamentals: Optional[Dict[str, Any]] = None,
        allow_buy: Optional[bool] = None,
        base_dir: Optional[str] = None,
    ) -> str:
        """Deterministic factor scores and recommendation."""
        return _text(
            call_tool(
                "compute_factors",
                {"symbol": symbol, "fundamentals": fundamentals,
                 "allow_buy": allow_buy, "base_dir": base_dir},
            )
        )

    @app.tool()
    def run_backtest(
        symbol: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        signals: Optional[Dict[str, Any]] = None,
        walk_forward: bool = False,
        base_dir: Optional[str] = None,
    ) -> str:
        """Backtest with costs; walk-forward by default."""
        return _text(
            call_tool(
                "run_backtest",
                {"symbol": symbol, "start": start, "end": end, "signals": signals,
                 "walk_forward": walk_forward, "base_dir": base_dir},
            )
        )

    @app.tool()
    def validate_report(
        date: str,
        strict: bool = False,
        allow_v1: bool = False,
        base_dir: Optional[str] = None,
    ) -> str:
        """Validate a date's outputs (contract v2) and data-quality/buy gate."""
        return _text(
            call_tool(
                "validate_report",
                {"date": date, "strict": strict, "allow_v1": allow_v1, "base_dir": base_dir},
            )
        )

    @app.tool()
    def run_pipeline(
        date: Optional[str] = None,
        symbols: Optional[List[str]] = None,
        offline: bool = False,
        source: str = "auto",
        mode: str = "all",
        run_backtest: bool = True,
        universe: Optional[str] = None,
        portfolio_top_n: int = 5,
        portfolio_method: str = "score_weight",
        base_dir: Optional[str] = None,
    ) -> str:
        """End-to-end reproducible pipeline: fetch -> factors -> ranking/portfolio -> validate."""
        return _text(
            call_tool(
                "run_pipeline",
                {"date": date, "symbols": symbols, "offline": offline, "source": source,
                 "mode": mode, "run_backtest": run_backtest, "universe": universe,
                 "portfolio_top_n": portfolio_top_n, "portfolio_method": portfolio_method,
                 "base_dir": base_dir},
            )
        )

    return app


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="QuanTr MCP server (stdio)")
    parser.add_argument("--list", action="store_true", help="print tool schemas and exit")
    args = parser.parse_args(argv)
    if args.list:
        print(json.dumps(TOOLS, ensure_ascii=False, indent=2))
        return 0
    app = build_app()
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
