# agent/ — optional autonomous analyst (aacode)

This folder is the **optional** LLM-driven layer. The deterministic engine lives
in `../src/quantr/` and does not depend on aacode. Use the agent when you want it
to plan, fetch data, write/adjust programs, and narrate reports.

## Install

```bash
pip install -e ".[agent,mcp]"      # aacode + mcp extras
cp ../.env.example ../.env         # then fill LLM_API_KEY / LLM_API_URL / LLM_MODEL_NAME
```

## Run

```bash
# from the repository root
python3 agent/main_quan_tr.py                 # default workspace: examples/workspace
python3 agent/main_quan_tr.py --normal
python3 agent/main_quan_tr.py --rewrite
python3 agent/main_quan_tr.py --backtest
python3 agent/main_quan_tr.py -p examples/workspace -t examples/workspace
```

- `aacode_config.yaml` (this folder) is pinned via `AACODE_CONFIG_FILE`, so the
  current working directory does not matter.
- The workspace defaults to `examples/workspace`; create your own with
  `quantr init my-research` and pass `-p my-research -t my-research`.

## Cron

```bash
bash agent/cron_run_quan_tr.sh -t 10:00     # prints crontab line / runs once
```

Logs go to `<workspace>/cron_run_quan_tr.log` (gitignored).

## Notes

- Numbers must come from `quantr` (indicators/factors/backtests); the agent only
  explains. Never fabricate market data.
- Before finishing a report task the agent runs `quantr validate --date ... --strict`.
