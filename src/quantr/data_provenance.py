# src/quantr/data_provenance.py
"""数据来源与真实性标记（Data provenance）。

目的：让“真实数据 / 模拟数据 / 缺失”在数据层显式可见，避免把随机生成的
模拟数据当作真实行情参与分析和回测。

用法：
    from programs.utils.data_provenance import provenance_block, write_manifest

    # 写数据文件时附带来源信息
    payload = {..., "_provenance": provenance_block("akshare", note="日线数据")}

    # 任务结束时生成当日清单（供 validate_report 审计）
    write_manifest("2026-05-19", records)

本模块只依赖标准库。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ._paths import workspace_root

# 出现以下任意标记即视为“非真实数据”
SIMULATION_TOKENS = (
    "模拟",
    "仿真",
    "合成",
    "伪造",
    "假冒",
    "随机生成",
    "fake",
    "mock",
    "simulat",
    "synthetic",
    "random",
)



def is_simulated(note: Optional[str], source: Optional[str] = None) -> bool:
    """Return True if the note/source clearly indicates fabricated data."""
    text = f"{note or ''} {source or ''}".lower()
    return any(token.lower() in text for token in SIMULATION_TOKENS)


def provenance_block(
    source: str,
    note: str = "",
    retrieved_at: Optional[str] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """Build a provenance block to embed inside a dataset payload."""
    block = {
        "source": source,
        "note": note,
        "is_simulated": is_simulated(note, source),
        "retrieved_at": retrieved_at or datetime.now().isoformat(timespec="seconds"),
    }
    block.update(extra)
    return block


def _extract_note(obj: Any) -> Optional[str]:
    if isinstance(obj, dict):
        for key in ("note", "data_note", "source_note", "description"):
            value = obj.get(key)
            if isinstance(value, str) and value.strip():
                return value
        provenance = obj.get("_provenance")
        if isinstance(provenance, dict) and isinstance(provenance.get("note"), str):
            return provenance["note"]
    return None


def classify_file(path: Path) -> Dict[str, Any]:
    """Classify one dataset file as real / simulated based on its metadata."""
    note: Optional[str] = None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        note = _extract_note(data)
        if note is None and isinstance(data, list):
            for item in data[:5]:
                note = _extract_note(item)
                if note:
                    break
    except Exception:
        note = None
    simulated = is_simulated(note) or is_simulated(path.name)
    return {
        "path": str(path),
        "note": note or "",
        "is_simulated": simulated,
    }


def audit_date_dir(
    date: str, base_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """Audit all JSON datasets under ``data_files/<date>`` for provenance."""
    base = workspace_root(base_dir)
    root = base / "data_files" / date
    files = (
        sorted(p for p in root.rglob("*.json") if p.name != "manifest.json")
        if root.exists()
        else []
    )
    datasets = [classify_file(path) for path in files]
    simulated = [item for item in datasets if item["is_simulated"]]
    return {
        "date": date,
        "root": str(root),
        "dataset_count": len(datasets),
        "simulated_count": len(simulated),
        "has_simulated": bool(simulated),
        "datasets": datasets,
    }


def data_quality_status(audit: Dict[str, Any]) -> str:
    """Derive an overall data-quality status from an audit result."""
    if audit.get("dataset_count", 0) == 0:
        return "missing"
    if audit.get("simulated_count", 0) == 0:
        return "real"
    if audit["simulated_count"] >= audit["dataset_count"]:
        return "simulated"
    return "partial"


def write_manifest(
    date: str,
    records: Optional[List[Dict[str, Any]]] = None,
    base_dir: Optional[Path] = None,
    as_of: Optional[str] = None,
) -> Path:
    """Write ``data_files/<date>/manifest.json`` summarizing data provenance."""
    base = workspace_root(base_dir)
    if records is not None:
        datasets = list(records)
        dataset_count = len(datasets)
        simulated_count = sum(1 for item in datasets if item.get("is_simulated"))
        if dataset_count == 0:
            status = "missing"
        elif simulated_count == 0:
            status = "real"
        elif simulated_count >= dataset_count:
            status = "simulated"
        else:
            status = "partial"
        audit = {
            "dataset_count": dataset_count,
            "simulated_count": simulated_count,
            "has_simulated": simulated_count > 0,
        }
    else:
        audit = audit_date_dir(date, base)
        datasets = audit["datasets"]
        status = data_quality_status(audit)

    manifest = {
        "date": date,
        "as_of": as_of or date,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "data_quality_status": status,
        "has_simulated": audit["has_simulated"],
        "dataset_count": audit["dataset_count"],
        "simulated_count": audit["simulated_count"],
        "datasets": datasets,
    }
    out_dir = base / "data_files" / date
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "manifest.json"
    out_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out_path
