"""Hardening tests: traversal, AST govern, budget gate, sandbox flags. All offline."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import forge_agents as A
import forge_govern as G
import forge_loop as L
import forge_memory as MEM
import forge_obs as O
import forge_sandbox as SB


def test_traversal_task_id_blocked(tmp_path):
    with pytest.raises(ValueError):
        SB.artifact_write("../../evil", 1, "print(1)",
                           SB.SandboxResult(0, "", "", False, str(tmp_path)))


def test_traversal_skill_name_blocked():
    with pytest.raises(ValueError):
        MEM.semantic_save("../evil", {"version": "1.0.0"})
    with pytest.raises(ValueError):
        MEM.semantic_load("../evil")


def test_ast_denies_eval_and_import():
    assert G.ast_denies("print(1)") == []
    assert G.ast_denies("eval('1+1')") != []
    assert G.ast_denies("import os; os.system('x')") != []
    assert G.ast_denies("__import__('subprocess')") != []


def test_govern_additive_no_regression():
    ok, _ = G.govern("print(1)")
    assert ok
    ok, reasons = G.govern("x = eval('1')")
    assert not ok and reasons


def test_budget_veto_in_loop(monkeypatch, tmp_path):
    monkeypatch.setenv("FORGE_BUDGET_TOKENS", "1")
    monkeypatch.setattr(SB, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(MEM, "EPISODIC", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(MEM, "LIFE", tmp_path / "life.md")
    monkeypatch.setattr(MEM, "WORKING", tmp_path / "ctx.json")
    monkeypatch.setattr(MEM, "PROCEDURAL", tmp_path / "tool_patterns.yaml")
    monkeypatch.setattr(MEM, "SEMANTIC_DIR", tmp_path / "reg")
    monkeypatch.setattr(O, "LEDGER", tmp_path / "o.jsonl")
    monkeypatch.setattr(O, "TRACES", tmp_path / "tr.jsonl")
    monkeypatch.setattr(O, "LINEAGE", tmp_path / "lin.jsonl")
    monkeypatch.setattr(A, "DECISION_LEDGER", tmp_path / "dec.jsonl")
    out = L.run_loop("write a sufficiently long concrete task with done criteria set",
                     task_id="t-budget", max_attempts=2,
                     code_provider=lambda att, hist: "print(1)")
    assert out["status"] == "blocked"


def test_sandbox_scrub_drops_pythonpath():
    env = dict(os.environ)
    env["PYTHONPATH"] = "/tmp/evil"
    real = os.environ
    try:
        os.environ.clear()
        os.environ.update(env)
        scrubbed = SB._scrub_env()
    finally:
        os.environ.clear()
        os.environ.update(real)
    assert "PYTHONPATH" not in scrubbed
    assert scrubbed.get("PYTHONSAFEPATH") == "1"


def test_execute_farm_uses_isolated_flags():
    r = SB.execute_farm("print(40+2)")
    assert r.exit == 0 and "42" in r.stdout
