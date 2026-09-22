"""Non-interactive CLI command coverage via Typer's CliRunner.

`chat`/`resume` prompt interactively (typer.prompt) and aren't exercised here; every other
command is a single invocation with flags, so CliRunner covers them directly.
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

from supportpilot.cli import app

runner = CliRunner()


def _run(*args: str):
    return runner.invoke(app, list(args))


def test_demo_single_concept(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPPORTPILOT_LEDGER", str(tmp_path / "ledger.json"))
    result = _run("demo", "c01")
    assert result.exit_code == 0
    assert "PASS" in result.output


def test_demo_unknown_concept_exits_nonzero(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPPORTPILOT_LEDGER", str(tmp_path / "ledger.json"))
    result = _run("demo", "c99")
    assert result.exit_code != 0


def test_export_graph(tmp_path, monkeypatch):
    result = _run("export-graph")
    assert result.exit_code == 0
    assert "wrote" in result.output


def test_memory_command_new_user(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPPORTPILOT_LEDGER", str(tmp_path / "ledger.json"))
    result = _run("memory", "--user", "u_cli_test")
    assert result.exit_code == 0
    assert "profile" in result.output


def test_digest_command(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPPORTPILOT_LEDGER", str(tmp_path / "ledger.json"))
    result = _run("digest", "--date", "2026-01-01")
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["sent"] is True


def test_state_and_history_after_chat_via_graph_directly(tmp_path, monkeypatch):
    """state/history need an existing thread; build one directly rather than driving the
    interactive `chat` prompt loop."""
    db = str(tmp_path / "cli_state.db")
    ledger = str(tmp_path / "ledger.json")
    monkeypatch.setenv("SUPPORTPILOT_DB", db)
    monkeypatch.setenv("SUPPORTPILOT_LEDGER", ledger)

    from supportpilot.cli import _compiled
    from supportpilot.context import SupportContext
    from supportpilot.persistence import sqlite_checkpointer

    graph = _compiled(sqlite_checkpointer(db))
    graph.invoke(
        {"messages": [("human", "how do I set up sso")]},
        {"configurable": {"thread_id": "cli-thread-1"}},
        context=SupportContext(user_id="u_cli"),
    )

    result = _run("state", "--thread", "cli-thread-1")
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["values"]["final_answer"]

    result2 = _run("history", "--thread", "cli-thread-1")
    assert result2.exit_code == 0
    assert "checkpoint_id" in result2.output or "step" in result2.output
