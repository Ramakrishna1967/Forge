"""Forge agents: 7-role compat core + 15-role Omega swarm (L3), planning engine
(L4: HTN+MCTS+ToT+GIVEN/WHEN/THEN, G0-G4 gates, 5 attempts, backoff, needs-code
queue), cognition (L5: System-1/2, dual self-score, reflection, decision ledger).

Backward-compat: Envelope(task_id, frm, to, artifact, verdict, evidence,
self_score), self_score_ok, gate_g1/g2/g3, spinning, reflect, ROLES(7) kept.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import hashlib
import json
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
DECISION_LEDGER = BASE / "runs" / "decisions.jsonl"
from forge_const import BACKOFF  # noqa: E402 single source
from forge_const import MAX_ATTEMPTS  # noqa: E402,F401 re-exported (run_loop reads A.MAX_ATTEMPTS)

@dataclass
class Envelope:
    task_id: str
    frm: str
    to: str
    artifact: str
    verdict: str  # PASS/FAIL/NEEDS-CODE
    evidence: list = field(default_factory=list)
    self_score: int = 3
    dag_node: str = ""
    tokens: int = 0

def self_score_ok(coder_score: int, reflector_score: int) -> bool:
    return abs(coder_score - reflector_score) <= 1

def gate_g1(plan_score: int) -> bool:
    return plan_score >= 4

def gate_g2(tests_pass: bool) -> bool:
    return tests_pass

def gate_g3(sec_pass: bool) -> bool:
    return sec_pass

def spinning(diff_hashes: list[str]) -> bool:
    """Spin detector: identical last two OR A-B-A oscillation in last three."""
    if len(diff_hashes) >= 2 and diff_hashes[-1] == diff_hashes[-2]:
        return True
    if len(diff_hashes) >= 3 and diff_hashes[-1] == diff_hashes[-3] != diff_hashes[-2]:
        return True
    return False

def reflect(what_failed: str, hypothesis: str, change: str) -> str:
    return f"failed: {what_failed}\nhypothesis: {hypothesis}\nchange: {change}\n"

ROLES = ["planner", "coder", "critic", "tester", "security", "reflector", "meta"]

# ---- Omega L3: 15-role swarm ----
SWARM_ROLES = ["orchestrator", "planner", "librarian", "historian", "coder",
               "critic", "tester", "security", "red-teamer", "oracle",
               "economist", "auditor", "archivist", "dreamer", "meta"]
BYZANTINE_VOTERS = ["critic", "tester", "security", "oracle"]


def byzantine_merge(votes: dict[str, str]) -> bool:
    """2/3 of critic/tester/security/oracle must PASS to merge."""
    passes = sum(1 for v in BYZANTINE_VOTERS if votes.get(v) == "PASS")
    return passes >= 3  # 3/4 > 2/3, integer-safe quorum


def auction(bids: list[dict]) -> dict | None:
    """Coder auction: lowest cost among bids with self_score>=3 wins."""
    eligible = [b for b in bids if int(b.get("self_score", 0)) >= 3]
    if not eligible:
        return None
    return min(eligible, key=lambda b: (float(b.get("cost", 0)), -int(b.get("self_score", 0))))


def _debate_quality(claim: str) -> float:
    words = (claim or "").split()
    distinct = len({w.lower() for w in words})
    digits = sum(c.isdigit() for c in claim or "")
    code_terms = sum(claim.count(t) for t in ("def ", "assert", "return", "exit", "test"))
    return len(words) + distinct + 2 * digits + 3 * code_terms


def debate_round(coder_claim: str, redteam_claim: str, round_no: int = 1) -> dict:
    """Coder vs red-teamer debate, 2 rounds; round>=2 needs oracle tie-break."""
    cq, rq = _debate_quality(coder_claim), _debate_quality(redteam_claim)
    verdict = "coder" if cq >= rq else "redteam"
    return {"round": round_no, "coder": (coder_claim or "")[:200],
            "redteam": (redteam_claim or "")[:200],
            "coder_score": cq, "redteam_score": rq, "verdict": verdict,
            "needs_oracle": round_no >= 2}


def oracle_break_tie(votes: dict[str, str]) -> bool:
    """Oracle tie-break reuses the byzantine quorum (3/4 PASS to merge)."""
    return byzantine_merge(votes)


# ---- Omega L4: planning engine ----
def gate_g0(identity_ok: bool) -> bool:
    return bool(identity_ok)


def gate_g4(budget_ok: bool, provenance_ok: bool) -> bool:
    return bool(budget_ok and provenance_ok)


def decidable_goal(given: str, when: str, then: str) -> str:
    return f"GIVEN {given} WHEN {when} THEN {then}"


def mcts_pick(options: list[dict], rollouts: int = 4, c: float = 1.414) -> dict | None:
    """Real UCB1: value + c*sqrt(ln(N)/n). Deterministic offline (ties -> first)."""
    import math
    if not options:
        return None
    total = sum(max(1, int(o.get("visits", 1))) for o in options)
    best, best_key = None, None
    for o in options:
        v = float(o.get("value", 0.5))
        n = max(1, int(o.get("visits", 1)))
        score = v + c * math.sqrt(math.log(total) / n)
        key = (score, -options.index(o))
        if best_key is None or key > best_key:
            best, best_key = o, key
    return best


def _tot_signal(idea: str) -> float:
    words = (idea or "").split()
    distinct = len({w.lower() for w in words})
    digits = sum(ch.isdigit() for ch in idea or "")
    return len(idea or "") + distinct + 2 * digits


def tot_branch(ideas: list[str]) -> str | None:
    """Tree-of-Thought: branch N, prune to 1 by signal density (ties -> first)."""
    if not ideas:
        return None
    ranked = sorted((( _tot_signal(i), -ideas.index(i), i) for i in ideas), reverse=True)
    return ranked[0][2][:500]


def needs_code(task: str) -> bool:
    t = task.lower()
    vague = ["maybe", "something", "figure it out", "you decide", "tbd", "???"]
    return any(w in t for w in vague) or len(t.strip()) < 12


def backoff_for(attempt: int) -> int:
    return BACKOFF[min(max(attempt - 1, 0), len(BACKOFF) - 1)]


# ---- Omega L5: cognition ----
def system_route(skill_confidence: float) -> str:
    return "system-1" if skill_confidence > 0.9 else "system-2"


def audit_scores(a: int, b: int) -> bool:
    """Dual self-score: delta>1 triggers audit (returns True if audit needed)."""
    return abs(a - b) > 1


def reflection_record(failed: str, hypothesis: str, change: str, predicted: str) -> dict:
    return {"failed": failed, "hypothesis": hypothesis, "change": change,
            "predicted": predicted, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}


def decision_log(task_id: str, node: str, decision: str, why: str) -> None:
    DECISION_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "task_id": task_id,
           "node": node, "decision": decision, "why": why,
           "hash": hashlib.blake2b((task_id + node + decision).encode(), digest_size=8).hexdigest()}
    with DECISION_LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
