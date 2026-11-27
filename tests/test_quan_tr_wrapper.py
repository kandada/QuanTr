"""Smoke tests for the Plan-A thin-wrapper wiring.

QuanTr must talk to the upgraded aacode package (>=1.8.17), not the archived
1.7.7 vendored copy. These tests assert the import/API contract and the
end-to-end ``QuanTrCoder.run`` wiring without touching the network.
"""

import asyncio
import inspect
from pathlib import Path

import pytest


def _make_coder(tmp_path: Path):
    import agent.main_quan_tr as m

    work = tmp_path / "work"
    target = tmp_path / "target"
    work.mkdir()
    target.mkdir()
    (target / "init.md").write_text("# quant init\n- rule A\n", encoding="utf-8")
    (target / "stocks_pool.json").write_text('{"stocks": []}', encoding="utf-8")
    coder = m.QuanTrCoder(
        str(work), model_config=m._build_model_config(), target_project=str(target)
    )
    return m, coder, target


def test_framework_imports_resolve_to_aacode_package():
    import agent.main_quan_tr as m

    assert m.MainAgent.__module__.startswith("aacode.")
    assert m.ContextManager.__module__.startswith("aacode.")
    assert m.SafetyGuard.__module__.startswith("aacode.")


def test_execute_signature_matches_aacode_1_8():
    from aacode.core.main_agent import MainAgent

    params = set(inspect.signature(MainAgent.execute).parameters)
    assert "event_callback" in params
    assert "todo_manager" in params
    # Removed in aacode 1.8.x; passing them would raise TypeError.
    assert "init_instructions" not in params
    assert "project_analysis" not in params


def test_build_model_config_uses_name_key(tmp_path):
    import agent.main_quan_tr as m

    cfg = m._build_model_config()
    assert isinstance(cfg, dict)
    assert cfg.get("name"), "aacode expects the profile keyed by 'name'"
    assert "model" not in cfg
    assert cfg.get("gateway")
    assert cfg.get("context_window")


def test_event_logger_toggle(monkeypatch):
    import agent.main_quan_tr as m

    monkeypatch.setenv("QUANTR_EVENT_LOG", "0")
    assert m._make_event_logger() is None
    monkeypatch.setenv("QUANTR_EVENT_LOG", "1")
    logger = m._make_event_logger()
    assert callable(logger)
    # Must swallow arbitrary/nested event payloads without raising.
    logger({"type": "usage", "usage": {"prompt_total": 10, "output": 5}})
    logger({"type": "unknown", "x": object()})


def test_run_wiring_passes_new_execute_kwargs(tmp_path):
    m, coder, target = _make_coder(tmp_path)
    captured = {}

    async def fake_execute(**kwargs):
        captured.update(kwargs)
        return {
            "status": "success",
            "iterations": 1,
            "execution_time": 0.0,
            "session_id": "test_session",
        }

    coder.main_agent.execute = fake_execute

    result = asyncio.run(coder.run("测试任务：分析股票", max_iterations=3))

    assert result["status"] == "success"
    assert set(captured) == {
        "task",
        "task_dir",
        "max_iterations",
        "todo_manager",
        "event_callback",
    }
    assert captured["event_callback"] is not None
    assert captured["todo_manager"] is coder.todo_manager
    assert captured["max_iterations"] == 3
    # project analysis artifact is referenced in the task, not passed as a param
    assert "project_structure.md" in captured["task"]
    assert (target / "project_structure.md").exists()


def test_config_yaml_has_new_schema():
    import yaml

    root = Path(__file__).resolve().parent.parent
    data = yaml.safe_load((root / "agent" / "aacode_config.yaml").read_text(encoding="utf-8"))
    assert data["context"]["max_context_length"] == 1000000
    assert data["diff_hook"]["enabled"] is True
    assert data["tools"]["tool_profile"] in {"auto", "core", "web", "full"}
    assert data["timeouts"]["shell_command"] >= 60
    assert data["safety"]["restrict_to_project"] is False
