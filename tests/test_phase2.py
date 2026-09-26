"""Phase 2 tests: mesh fail-closed, planning determinism, vector fallback,
consolidate gates, replay/rewind foundations. All offline, no API key."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["FORGE_FAST_TEST"] = "1"
import forge_agents as A
import forge_memory as MEM
import forge_obs as O
import forge_consolidate as C
import forge_loop as L
import forge_sandbox as SB


def test_mesh_docker_fail_closed():
    os.environ.pop("FORGE_DOCKER", None)
    assert SB.docker_run("print(1)")["skipped"] is True


def test_mesh_chaos_allow_list():
    assert SB.chaos_inject("kill")["simulated"] is True
    with pytest.raises(ValueError):
        SB.chaos_inject("rm-rf-everything")


def test_mesh_wasm_replay_contract():
    r = SB.wasm_replay("print(40+2)")
    assert r["replayed"] is True and r["simulated"] is True
    assert r["deterministic"] is True and r["exit"] == 0


def test_mesh_mutation_gate_blocks_gaming():
    assert SB.mutation_score("out", ["out", "out"])["pass"] is False
    assert SB.mutation_score("out", ["zzz", "yyy"])["pass"] is True


def test_mesh_replay_rewind(tmp_path, monkeypatch):
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
    r = SB.execute_farm("print(40+2)", task_id="t-re", attempt=1)
    assert r.exit == 0
    rep = SB.replay_attempt("t-re", 1)
    assert rep["replayed"] is True and rep["match"] is True and rep["exit"] == 0
    assert SB.replay_attempt("t-re", 99)["replayed"] is False
    with pytest.raises(ValueError):
        SB.replay_attempt("../../evil", 1)


def test_mcts_ucb1_deterministic():
    opts = [{"value": 0.1, "visits": 1}, {"value": 0.9, "visits": 10}]
    assert A.mcts_pick(opts)["value"] == 0.1  # explore bonus wins
    assert A.mcts_pick([]) is None
    assert A.mcts_pick(opts) == A.mcts_pick(opts)


def test_tot_scored_not_longest():
    assert A.tot_branch([]) is None
    assert A.tot_branch(["a", "abc", "ab"]) == "abc"
    assert A.tot_branch(["xx", "error 404 fix"]) == "error 404 fix"


def test_debate_oracle_tiebreak():
    r1 = A.debate_round("def fix assert return 42", "meh", round_no=1)
    assert r1["verdict"] == "coder" and r1["needs_oracle"] is False
    r2 = A.debate_round("a", "b", round_no=2)
    assert r2["needs_oracle"] is True
    assert A.oracle_break_tie({v: "PASS" for v in A.BYZANTINE_VOTERS}) is True


def test_spinning_three_window():
    assert A.spinning(["a", "a"])
    assert A.spinning(["a", "b", "a"])  # oscillation
    assert not A.spinning(["a", "b"])
    assert not A.spinning(["a", "b", "c"])


def test_vector_file_fallback(monkeypatch, tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".forge" / "vector"))
    import adapter as V
    import forge_memory as MEM
    monkeypatch.setattr(MEM, "VECTOR_MIRROR", tmp_path / "mirror.json")
    va = V.VectorAdapter()
    assert va.backend == "file"
    va.upsert("k1", "hello world")
    assert va.query("k1") == [{"id": "k1", "text": "hello world"}]
    assert va.query("missing") == []


def test_consolidate_gates_and_dream_artifact(tmp_path, monkeypatch):
    import forge_memory as MEM
    monkeypatch.setattr(MEM, "EPISODIC", tmp_path / "ledger.jsonl")
    recs = [{"id": "e1", "root_cause": "p2 bug", "fix": "patch", "tried": "t", "status": "success"},
            {"id": "e2", "root_cause": "p2 bug", "fix": "patch", "tried": "t", "status": "success"}]
    assert C.consolidate(recs, sandbox_proof=False, critic_ok=True) == []
    d = C.dream_counterfactual({"id": "e-p2", "tried": "x", "status": "failed"})
    assert d["needs_proof"] is True and d.get("artifact") is True


def test_loop_mutation_gate_and_replay(tmp_path, monkeypatch):
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
    out = L.run_loop("print hello world task with concrete done criteria defined",
                     task_id="t-p2", max_attempts=1,
                     code_provider=lambda att, hist: "print('hi-p2')")
    assert out["status"] == "success"
    assert (tmp_path / "runs" / "t-p2" / "attempt_1" / "main.py").exists()


def test_loop_void_output_fails_gate(tmp_path, monkeypatch):
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
    out = L.run_loop("print hello world task with concrete done criteria defined",
                     task_id="t-void", max_attempts=1,
                     code_provider=lambda att, hist: "pass")
    assert out["status"] == "failed" and "mutation gate" in out.get("reason", "")


def test_loop_provider_exception_is_needs_code(tmp_path, monkeypatch):
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

    def _boom(att, hist):
        raise TimeoutError("upstream slow")
    out = L.run_loop("print hello world task with concrete done criteria defined",
                     task_id="t-exc", max_attempts=2, code_provider=_boom)
    assert out["status"] == "needs-code" and "TimeoutError" in out.get("response", "")


def test_legacy_loop_govern_and_containment():
    import forge as F
    with pytest.raises(ValueError):
        F._contain_work_file("../../evil.py")
    ok = F._contain_work_file("sandbox_task.py")
    assert ok.name == "sandbox_task.py"


def test_traversal_residuals_blocked(tmp_path, monkeypatch):
    import forge_consolidate as C2
    import forge_obs as O2
    import forge_skills as K2
    d = C2.dream_counterfactual({"id": "../../evil", "tried": "x", "status": "failed"})
    assert d.get("artifact") is True
    _BASE = Path(__file__).resolve().parents[1]
    assert not (_BASE / ".forge" / "dreams" / "dream-../../evil.json").exists()
    assert list((_BASE / ".forge" / "dreams").glob("*evil*")) == []
    assert O2.audit_export("../../evil") is None
    s = K2.Skill(name="../evil", version="1.0.0", when="w", rule="r", reason="x")
    with pytest.raises(ValueError):
        K2.stage_for_market(s)
    with pytest.raises(ValueError):
        SB.artifact_write("t1", "../x", "print(1)",
                          SB.SandboxResult(0, "", "", False, str(tmp_path)))


def test_govern_substring_covers_unparseable():
    import forge_govern as G2
    assert G2.ast_denies("def broken(:") == []  # unparseable: no AST verdict
    ok, _ = G2.govern("x = __import__('os')")  # substring layer still blocks
    assert not ok
