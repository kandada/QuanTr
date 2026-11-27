# Changelog

All notable changes to this project are documented here.
Format follows Keep a Changelog; versions follow Semantic Versioning.

## 0.2.0 — 2026-11-27

### Added
- `quantr --version`.
- `quantr doctor`: environment / workspace diagnostics (versions, deps, templates source,
  store symbols, optional `aacode`/`mcp`, actionable hints).
- `quantr fetch --pool`: read symbols from `stocks_pool.json`.
- Friendlier human-readable output for `indicators/factors/backtest/pipeline/validate/init/skill`.
- Error `hint` in the JSON envelope and on the CLI for common failures
  (no data, no symbols, offline with empty store, legacy v1 reports).
- `CHANGELOG.md`; packaged in sdist.

### Changed
- Repository restructured to a library-first layout:
  - `src/quantr/` (PyPI package), `agent/` (optional aacode entry),
    `examples/workspace/` (reference workspace), `docs/` (legacy aacode docs),
    `scripts/`.
  - Removed vendored aacode 1.7.7 copies (`core/ tools/ utils/ server/ sandbox/ i18n/ skills/`).
- `agent/main_quan_tr.py` defaults to `examples/workspace`, pins `AACODE_CONFIG_FILE`,
  loads `.env` from repo root/agent dir, and uses `quantr.market_clock`.
- Package header/help text updated (no more `quan_tr/...` source paths).
- `.gitignore` updated for the new workspace path.

### Fixed
- Legacy example programs import `config` / `programs.*` instead of the removed `quan_tr.*`.
- Tests made self-contained (no dependency on local sample data).
- CLI `--version` works with required subcommands.

## 0.1.0 — 2026-11-25

### Added
- First PyPI release (`quantr-engine`): deterministic engine, DuckDB/Parquet PIT store,
  indicators/factors, cost-aware backtest + walk-forward, contract v2 (schema + invariants +
  data-integrity gate), CLI (`quantr`), MCP server, library facade, skill, `quantr init`.
