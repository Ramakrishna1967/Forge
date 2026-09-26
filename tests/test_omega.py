"""Omega eval fortress: offline tests for L0-L9 wiring. No API key needed."""
import os
import sys
from pathlib import Path

os.environ["FORGE_FAST_TEST"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import forge_agents as A
import forge_memory as MEM
import forge_obs as O
import forge_router as R
import forge_sandbox as SB
import forge_skills as K
import forge_consolidate as C
import forge_govern as G
import forge_loop as L


def test_memory_chain(tmp_path, monkeypatch):
    monkeypatch.setattr(MEM, "EPISODIC", tmp_path / "ledger.jsonl")
    r1 = MEM.episodic_append("t1", "tried1", "cause", "fix1", "success")
    r2 = MEM.episodic_append("t2", "tried2", "cause", "fix2", "failed")
    assert r2["prev_hash"] == r1["hash"]
    ok, bad = MEM.episodic_verify_chain()
    assert ok and bad == -1
    assert MEM.merkle_root() != "empty"


def test_memory_tiers(tmp_path, monkeypatch):
    monkeypatch.setattr(MEM, "SEMANTIC_DIR", tmp_path / "reg")
    monkeypatch.setattr(MEM, "PROSPECTIVE", tmp_path / "todo.jsonl")
    monkeypatch.setattr(MEM, "FLASHBULB", tmp_path / "flash.jsonl")
    monkeypatch.setattr(MEM, "GRAPH", tmp_path / "links.jsonl")
    monkeypatch.setattr(MEM, "VECTOR_MIRROR", tmp_path / "mirror.json")
    monkeypatch.setattr(MEM, "LIFE", tmp_path / "life.md")
    p = MEM.semantic_save("s1", {"name": "s1", "version": "1.0.0", "rule": "r"})
    assert p.exists() and MEM.semantic_load("s1")["rule"] == "r"
    MEM.semantic_tombstone("s1", "1.0.0", "stale")
    assert MEM.semantic_load("s1")["deprecated"] is True
    assert MEM.prospective_add("future")["item"] == "future"
    assert len(MEM.prospective_read()) == 1
    MEM.flashbulb_pin("never rm -rf /")
    assert len(MEM.flashbulb_read()) == 1
    MEM.life_append("test line")
    assert "test line" in (tmp_path / "life.md").read_text(encoding="utf-8")
    MEM.graph_link("a", "b")
    assert len(MEM.graph_neighbors("a")) == 1
    MEM.vector_mirror_put("k", "v")
    assert MEM.vector_mirror_get("k") == "v"


def test_procedural(tmp_path, monkeypatch):
    monkeypatch.setattr(MEM, "PROCEDURAL", tmp_path / "tp.yaml")
    MEM.procedural_record("t", True)
    MEM.procedural_record("t", False)
    assert MEM.procedural_rate("t") == 0.5


def test_skills_genome(tmp_path, monkeypatch):
    monkeypatch.setattr(MEM, "SEMANTIC_DIR", tmp_path / "reg")
    monkeypatch.setattr(K, "REGISTRY", tmp_path / "reg")
    s = K.Skill(name="g1", when="w", rule="r", reason="why", confidence=0.8,
                evidence=["e1"], lift=2.0, uses=3, tokens=1, failures=0)
    assert s.fitness() == 2.0 * 3 - 1
    K.skill_save(s)
    assert K.skill_load("g1").rule == "r"
    ok, _ = K.skill_validate({"name": "", "when": "w", "rule": "r", "reason": "x"})
    assert not ok
    merged = K.conflict_resolve({"version": "1.0.0", "evidence": ["e1"], "rule": "old"},
                                {"version": "1.0.0", "evidence": ["e2"], "rule": "new"})
    assert merged["rule"] == "new" and set(merged["evidence"]) == {"e1", "e2"}
    assert merged["version"] == "1.0.1"
    assert K.fuzz_gate([True] * 10) and not K.fuzz_gate([True] * 9)
    assert not K.fuzz_gate([True] * 9 + [False])


def test_consolidate_gates(tmp_path, monkeypatch):
    monkeypatch.setattr(MEM, "SEMANTIC_DIR", tmp_path / "reg")
    monkeypatch.setattr(K, "REGISTRY", tmp_path / "reg")
    recs = [{"id": "e1", "root_cause": "same bug", "fix": "patch x", "tried": "t", "status": "success"},
            {"id": "e2", "root_cause": "same bug", "fix": "patch x", "tried": "t", "status": "success"}]
    assert C.consolidate(recs, sandbox_proof=False, critic_ok=True) == []  # no proof, no promote
    out = C.consolidate(recs, sandbox_proof=True, critic_ok=True)
    assert len(out) == 1
    d = C.dream_counterfactual({"id": "e9", "tried": "rm -rf", "status": "failed"})
    assert d["needs_proof"]


def test_sandbox_mesh(tmp_path, monkeypatch):
    monkeypatch.setattr(SB, "RUNS", tmp_path / "runs")
    r = SB.execute_farm("print(40+2)", task_id="t1", attempt=1)
    assert r.exit == 0 and "42" in r.stdout and r.artifact != ""
    assert (tmp_path / "runs" / "t1" / "attempt_1" / "main.py").exists()
    assert SB.provenance_hash("a") == SB.provenance_hash("a")
    assert SB.govern_check("print(1)") == []
    assert SB.govern_check("x=shell=True") != []
    assert SB.govern_check("import socket; socket.socket()") != []
    assert SB.secret_scan("print(1)") == []
    assert SB.secret_scan("key='hf_abcdefghijklmnop'") != []
    assert SB.docker_run("print(1)")["skipped"] is True
    assert SB.mutation_score("a", ["b", "b"])["pass"]


def test_router_economy(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cache")
    R.cache_put("k", {"content": "hi"})
    assert R.cache_get("k")["content"] == "hi"
    ok, _ = R.budget_check(10, 10, 1.0)
    assert ok
    monkeypatch.setenv("FORGE_BUDGET_TOKENS", "5")
    assert not R.budget_check(3, 3)[0]
    monkeypatch.delenv("FORGE_BUDGET_TOKENS")
    assert R._retryable("429 too many") and not R._retryable("SyntaxError boom")
    assert R.BACKOFF == [0, 5, 15, 45, 120]
    monkeypatch.setenv("FORGE_OFFLINE", "1")
    assert R.offline_bypass()
    monkeypatch.delenv("FORGE_OFFLINE")


def test_swarm_planning(tmp_path, monkeypatch):
    monkeypatch.setattr(A, "DECISION_LEDGER", tmp_path / "d.jsonl")
    assert len(A.SWARM_ROLES) == 15 and len(A.ROLES) == 7
    assert A.byzantine_merge({"critic": "PASS", "tester": "PASS", "security": "PASS", "oracle": "FAIL"})
    assert not A.byzantine_merge({"critic": "PASS", "tester": "FAIL", "security": "FAIL", "oracle": "FAIL"})
    bid = A.auction([{"cost": 5, "self_score": 4}, {"cost": 1, "self_score": 4}])
    assert bid["cost"] == 1
    assert A.auction([{"cost": 1, "self_score": 1}]) is None
    assert A.gate_g0(True) and not A.gate_g0(False)
    assert A.gate_g4(True, True) and not A.gate_g4(True, False)
    assert "GIVEN" in A.decidable_goal("g", "w", "t")
    # stub->real (Phase 2): real UCB1 explores the unvisited arm (0.1 wins via explore bonus)
    assert A.mcts_pick([{"value": 0.1, "visits": 1}, {"value": 0.9, "visits": 10}])["value"] == 0.1
    assert A.tot_branch(["a", "abc", "ab"]) == "abc"
    assert A.needs_code("???") and not A.needs_code("write fib(10) to out.txt and print it")
    assert A.backoff_for(2) == 5
    assert A.system_route(0.95) == "system-1" and A.system_route(0.5) == "system-2"
    assert A.audit_scores(5, 3) and not A.audit_scores(4, 3)
    A.decision_log("t1", "G1", "pass", "why")
    assert (tmp_path / "d.jsonl").exists()


def test_obs_govern(tmp_path, monkeypatch):
    monkeypatch.setattr(O, "LEDGER", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(O, "TRACES", tmp_path / "traces.jsonl")
    monkeypatch.setattr(O, "LINEAGE", tmp_path / "lineage.jsonl")
    O.log_attempt("t1", 1, "m", "h", 0, "out", "err", 5)
    assert len(O.read_ledger()) == 1
    with O.span("t1", "s1"):
        pass
    O.log_lineage("t1", "ph", ["s"], "m")
    assert (tmp_path / "traces.jsonl").exists()
    assert not G.halted()
    assert G.govern("print(1)")[0]
    assert not G.govern("x shell=True")[0]
    assert G.secret_scan("t='hf_abcdefghijklmnop'") != []
    monkeypatch.setenv("HALT", "1")
    try:
        G.check_halt()
        raised = False
    except SystemExit:
        raised = True
    assert raised
    monkeypatch.delenv("HALT")


def test_loop_wiring(tmp_path, monkeypatch):
    monkeypatch.setattr(MEM, "EPISODIC", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(MEM, "LIFE", tmp_path / "life.md")
    monkeypatch.setattr(MEM, "WORKING", tmp_path / "ctx.json")
    monkeypatch.setattr(MEM, "SEMANTIC_DIR", tmp_path / "reg")
    monkeypatch.setattr(SB, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(O, "LEDGER", tmp_path / "o.jsonl")
    monkeypatch.setattr(O, "TRACES", tmp_path / "tr.jsonl")
    monkeypatch.setattr(O, "LINEAGE", tmp_path / "lin.jsonl")
    monkeypatch.setattr(A, "DECISION_LEDGER", tmp_path / "dec.jsonl")
    monkeypatch.setattr(MEM, "PROCEDURAL", tmp_path / "tool_patterns.yaml")
    r = L.run_loop("???")
    assert r["status"] == "needs-code"
    ok = L.run_loop("write hello and print it", task_id="ok1",
                    code_provider=lambda att, hist: "print('hi-omega')")
    assert ok["status"] == "success" and ok["attempts"] == 1
    spin = L.run_loop("write hello and print it", task_id="sp1",
                      code_provider=lambda att, hist: "raise SystemExit(1)", max_attempts=3)
    assert spin["status"] == "failed" and "spinning" in spin.get("reason", "")
    blocked = L.run_loop("write hello and print it", task_id="bl1",
                         code_provider=lambda att, hist: "x shell=True")
    assert blocked["status"] == "blocked"
