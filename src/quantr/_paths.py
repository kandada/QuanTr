"""Path resolution: packaged assets vs. the user's workspace."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = PACKAGE_DIR / "templates"
SKILL_DIR = PACKAGE_DIR / "skill"
WORKSPACE_TEMPLATE_DIR = PACKAGE_DIR / "workspace_template"


def workspace_root(base_dir: Optional[Path | str] = None) -> Path:
    """Explicit base_dir wins; otherwise $QUANTR_HOME or the current directory."""
    if base_dir is not None:
        return Path(base_dir)
    env = os.environ.get("QUANTR_HOME")
    return Path(env).expanduser() if env else Path.cwd()


def templates_dir(base_dir: Optional[Path | str] = None) -> Path:
    """Workspace templates override; fall back to packaged templates."""
    candidate = workspace_root(base_dir) / "analysis_results" / "templates"
    if (candidate / "stocks_analysis.schema.json").exists():
        return candidate
    return TEMPLATES_DIR
