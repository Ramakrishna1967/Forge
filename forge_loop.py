"""Forge loop (Omega L0+L4 wiring): Recall -> Plan -> Write -> Run -> Observe
-> Fix-or-Finish (max 5) -> Learn. Ties memory/skills/router/sandbox/agents/
obs/govern together. Offline-first: FORGE_OFFLINE=1 or missing NEBIUS_API_KEY
runs sandbox/verification without LLM calls. forge.py stays as compat shim.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
import forge_agents as A  # noqa: E402 path bootstrap
import forge_memory as MEM  # noqa: E402 path bootstrap
import forge_obs as OBS  # noqa: E402 path bootstrap
import forge_router as ROUTER  # noqa: E402 path bootstrap
import forge_sandbox as SB  # noqa: E402 path bootstrap
import forge_govern as GOV  # noqa: E402 path bootstrap

AGENT_JSON = BASE / ".forge" / "agent.json"
TICK = BASE / ".forge" / "working" / "tick.json"
from forge_const import (  # noqa: E402 single source (same pattern as forge.py)
    HISTORY_TAIL,
    MAX_CODE_BYTES,
    extract_python_blocks as _extract_blocks,
)


# ---- L0 identity + time ----
def identity() -> dict:
    AGENT_JSON.parent.mkdir(parents=True, exist_ok=True)
    if AGENT_JSON.exists():
        try:
            rec = json.loads(AGENT_JSON.read_text(encoding="utf-8"))
            return rec
        except Exception:
            bak = AGENT_JSON.with_suffix(".corrupt.bak")
            try:
                AGENT_JSON.rename(bak)
            except OSError:
                pass
            print(f"[warn] corrupt agent.json backed up to {bak}", file=sys.stderr)
    rec = {"agent_id": f"forge-{uuid.uuid4().hex[:8]}", "incarnation": 1}
    MEM._atomic_write(AGENT_JSON, json.dumps(rec, indent=2))
    return rec


def heartbeat(task_id: str = "") -> dict:
    TICK.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "task_id": task_id}
    try:
        me = identity()
        rec.update(me)
    except Exception:
        pass
    MEM._atomic_write(TICK, json.dumps(rec, indent=2))
    return rec


def extract_python_blocks(text: str) -> list[str]:
    return _extract_blocks(text)  # compat wrapper: canonical impl lives in forge_const


def recall(task: str) -> dict:
    mem = MEM.episodic_read(limit=5)
    skills = [p.name for p in MEM.semantic_list()][:20]
    flash = MEM.flashbulb_read(limit=10)
    return {"episodic_tail": mem, "skills": skills, "flashbulb": flash,
            "life": MEM.LIFE.read_text(encoding="utf-8")[-2000:] if MEM.LIFE.exists() else ""}


def plan(task: str) -> dict:
    """G1: plan score >=4. Offline heuristic: concrete task + decidable goal."""
    if A.needs_code(task):
        return {"score": 2, "gate": False, "goal": "", "ambiguous": True}
    goal = A.decidable_goal(f"task '{task[:60]}' assigned", "sandbox runs main.py", "exit 0 and output verified")
    score = 4 if len(task.strip()) >= 12 else 2
    return {"score": score, "gate": A.gate_g1(score), "goal": goal, "ambiguous": False}


def default_provider(task: str, system: str, history: str, attempt: int) -> str:
    """Default code provider: Token Factory cascade. Raises if offline."""
    if ROUTER.offline_bypass():
        raise RuntimeError("offline: no NEBIUS_API_KEY (use --run-file or code_provider)")
    out = ROUTER.call_cascade(task, system, history, attempt=attempt)
    blocks = extract_python_blocks(out["content"])
    if not blocks:
        raise RuntimeError("LLM returned no python block (needs-code)")
    return blocks[0]


def _fetch_code(provider, attempt: int, history: str, task_id: str):
    """Provider errors (LLM API, timeouts, offline) are needs-code, never crashes."""
    try:
        return provider(attempt, history), None
    except Exception as e:
        return None, {"status": "needs-code", "attempts": attempt, "task_id": task_id,
                      "response": f"provider error ({type(e).__name__}): {e}"}


def _mutation_gate(stdout: str) -> tuple[bool, str]:
    """G2: exit-0 with empty output, or surviving mutants, means gaming/void."""
    if not (stdout or "").strip():
        return False, "empty output (mutation gate: void success)"
    m1 = stdout[::-1]
    if m1 == stdout:
        m1 += "#A"
    m2 = stdout + "#B"  # always differs by construction
    mgate = SB.mutation_score(stdout, [m1, m2])
    if not mgate["pass"]:
        return False, "mutation gate (mutants survived)"
    return True, "ok"


def _finish_success(task: str, task_id: str, attempt: int, prov: str, last_output: str) -> dict:
    MEM.episodic_append(task, f"sandbox attempt {attempt} exit 0", "n/a",
                        f"provenance {prov}", "success")
    MEM.life_append(f"{task_id}: {task[:80]} -> success in {attempt} attempt(s)")
    MEM.working_save({"last_task": task_id, "attempts": attempt, "status": "success"})
    MEM.procedural_record("sandbox_exec", True)
    return {"status": "success", "attempts": attempt, "task_id": task_id, "output": last_output}


def _run_attempt(provider, attempt: int, history: str, task: str, system: str,
                 task_id: str, ctx: dict, t_start: float) -> tuple[str, dict | str]:
    """One fix-loop attempt. Returns (action, payload): done/failed/blocked/result,
    or continue/history. Keeps run_loop itself under the size limit."""
    t0 = time.time()
    history = (history or "")[-HISTORY_TAIL:]  # cap prompt/cost growth per attempt
    ok, msg = ROUTER.budget_check(
        prompt_tokens=(len(task) + len(history)) // 4, wall_s=time.time() - t_start)
    if not ok:
        return "done", {"status": "blocked", "attempts": attempt - 1,
                        "task_id": task_id, "reasons": [msg]}
    code, err = _fetch_code(provider, attempt, history, task_id)
    if err is not None:
        return "done", err
    if len(code.encode()) > MAX_CODE_BYTES:
        return "done", {"status": "blocked", "attempts": attempt,
                        "task_id": task_id,
                        "reasons": [f"code too large ({len(code.encode())}>{MAX_CODE_BYTES} bytes)"]}
    ok, reasons = GOV.govern(code)
    if not ok:
        OBS.log_attempt(task_id, attempt, "govern", hashlib.sha256(code.encode()).hexdigest()[:12],
                        403, "", "; ".join(reasons))
        return "done", {"status": "blocked", "attempts": attempt, "task_id": task_id, "reasons": reasons}
    prov = SB.provenance_hash(code, system, ROUTER.MODEL_DEFAULT, str(attempt))
    res = SB.execute_farm(code, task_id=task_id, attempt=attempt, provenance=prov)
    latency = int((time.time() - t0) * 1000)
    OBS.log_attempt(task_id, attempt, ROUTER.MODEL_DEFAULT,
                    hashlib.sha256(code.encode()).hexdigest()[:12],
                    res.exit, res.stdout, res.stderr, latency)
    OBS.log_lineage(task_id, hashlib.sha256((system + task).encode()).hexdigest()[:12],
                    ctx["skills"][:5], ROUTER.MODEL_DEFAULT)
    last_output = f"exit={res.exit}\n--- stdout ---\n{res.stdout}\n--- stderr ---\n{res.stderr}"
    h = hashlib.sha256(code.encode()).hexdigest()[:12]
    return "observed", {"code_hash": h, "output": last_output,
                        "exit": res.exit, "stdout": res.stdout, "prov": prov}


def run_loop(task: str, task_id: str | None = None, max_attempts: int = A.MAX_ATTEMPTS,
             code_provider=None, system: str = "You are Forge, a terse coding agent. Output one ```python block.") -> dict:
    GOV.check_halt()
    me = identity()
    task_id = task_id or f"t-{uuid.uuid4().hex[:8]}"
    heartbeat(task_id)
    ctx = recall(task)
    pl = plan(task)
    A.decision_log(task_id, "G1-plan", "pass" if pl["gate"] else "needs-code", pl.get("goal", ""))
    if not pl["gate"]:
        return {"status": "needs-code", "attempts": 0, "task_id": task_id,
                "question": "Task is ambiguous — please state file, behavior, and done-criteria in one line."}
    t_start = time.time()
    # chars->tokens proxy: ~4 chars/token (over-blocks non-English, under-blocks
    # dense code — fail-closed direction is deliberate; usage feedback refines it).
    ok, msg = ROUTER.budget_check(prompt_tokens=(len(task) + len(system)) // 4, wall_s=0.0)
    if not ok:
        return {"status": "blocked", "attempts": 0, "task_id": task_id, "reasons": [msg]}
    history, last_output, diffs = "", "", []
    provider = code_provider or (lambda att, hist: default_provider(task, system, hist, att))
    with OBS.span(task_id, "forge-run", agent=me.get("agent_id", "?")):
        for attempt in range(1, max_attempts + 1):
            action, payload = _run_attempt(provider, attempt, history, task, system,
                                           task_id, ctx, t_start)
            if action == "done":
                return payload
            last_output = payload["output"]
            h = payload["code_hash"]
            if A.spinning(diffs + [h]):
                MEM.episodic_append(task, f"spinning identical diff {h}", "fix loop not changing code",
                                    "stop and ask", "failed")
                return {"status": "failed", "attempts": attempt, "task_id": task_id,
                        "output": last_output, "reason": "spinning (identical diffs)"}
            diffs.append(h)
            if payload["exit"] == 0:
                gate_ok, gate_why = _mutation_gate(payload["stdout"])
                if not gate_ok:
                    MEM.episodic_append(task, f"sandbox attempt {attempt} exit 0 void",
                                        "tester gaming (mutation gate)", "tighten assertions", "failed")
                    return {"status": "failed", "attempts": attempt, "task_id": task_id,
                            "output": last_output, "reason": gate_why}
                return _finish_success(task, task_id, attempt, payload["prov"], last_output)
            history += f"\n[attempt {attempt}] FAILED:\n{last_output}\nDiagnose root cause, patch minimally.\n"
            MEM.procedural_record("sandbox_exec", False)
            if attempt < max_attempts and not os.environ.get("FORGE_FAST_TEST"):
                time.sleep(A.backoff_for(attempt + 1))
        MEM.episodic_append(task, f"{max_attempts} sandbox attempts failed", history[-300:],
                            "budget exhausted", "failed")
        MEM.life_append(f"{task_id}: {task[:80]} -> failed after {max_attempts} attempts")
        return {"status": "failed", "attempts": max_attempts, "task_id": task_id, "output": last_output}


def main() -> None:
    ap = argparse.ArgumentParser(description="Forge Omega loop")
    ap.add_argument("--task", default="")
    ap.add_argument("--run-file", default="")
    ap.add_argument("--task-id", default="")
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()
    if args.offline:
        os.environ["FORGE_OFFLINE"] = "1"
    if args.run_file:
        from forge import execute_sandboxed
        src = Path(args.run_file)
        try:
            ok, reasons = GOV.govern(src.read_text(encoding="utf-8"))
        except OSError as e:
            print(f"blocked: cannot read --run-file: {e}")
            sys.exit(2)
        if not ok:
            print(f"blocked: govern denied --run-file: {'; '.join(reasons)}")
            sys.exit(2)
        r = execute_sandboxed(args.run_file)
        print(f"exit={r.returncode}\n--- stdout ---\n{r.stdout}\n--- stderr ---\n{r.stderr}")
        sys.exit(r.returncode)
    if not args.task:
        ap.error("--task is required unless --run-file is given")
    print(json.dumps(run_loop(args.task, task_id=args.task_id or None), indent=2))


if __name__ == "__main__":
    main()
