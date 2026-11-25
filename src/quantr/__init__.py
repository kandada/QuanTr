"""quantr — deterministic, auditable quantitative research engine.

Numbers are computed by code (indicators/factors/backtests); this package never
fabricates market data and ships a versioned JSON contract for reports.

Quick start::

    pip install quantr
    quantr init my-research && cd my-research
    quantr fetch --symbols 000001.SZ --save --json
    quantr factors --symbol 000001.SZ --json
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
