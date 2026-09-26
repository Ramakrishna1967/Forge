import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import forge_agents as A
import forge_memory as M
import forge_obs as O
import forge_router as R
import forge_sandbox as S
import forge_skills as K

def test_agents_gates():
    assert A.gate_g1(4) and not A.gate_g1(3)
    assert A.gate_g2(True) and not A.gate_g2(False)
    assert A.spinning(["a", "a"]) and not A.spinning(["a", "b"])
    assert len(A.ROLES) == 7

def test_memory_episodic(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "EPISODIC", tmp_path / "ledger.jsonl")
    rec = M.episodic_append("t", "tried", "cause", "fix", "success")
    assert rec["id"].startswith("e_")
    assert len(M.episodic_read()) == 1

def test_skills_rules():
    assert K.should_promote(2, "normal")
    assert K.should_promote(1, "footgun")
    assert not K.should_promote(1, "normal")
    assert K.needs_archive(0.2) and not K.needs_archive(0.9)

def test_sandbox_farm():
    r = S.execute_farm("print(40+2)")
    assert r.exit == 0 and "42" in r.stdout and not r.timed_out

def test_router_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path)
    R.cache_put("k1", {"content": "hi"})
    assert R.cache_get("k1")["content"] == "hi"
    assert R.cache_key("a", "b", "c") == R.cache_key("a", "b", "c")

def test_obs_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(O, "LEDGER", tmp_path / "ledger.jsonl")
    O.log_attempt("t1", 1, "m", "h", 0, "out", "err", 5)
    assert len(O.read_ledger()) == 1
