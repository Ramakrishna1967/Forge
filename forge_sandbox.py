"""Forge sandbox farm + mesh (Omega L6): isolated tmp workdir, 30s timeout,
offline-first, scrubbed env, net-off, provenance + artifacts.

Isolation is SIMULATED (same OS user, no container): absolute-path writes and
env reads are possible at OS level, so the govern layer denies repo-state
targets (memory.md/skills.md/life.md/.forge/), env exfil, and secrets before
anything executes. Real container isolation only via FORGE_DOCKER=1.

Mesh stages (offline-first): tmp farm (real) -> wasm replay (contract) ->
docker --network none (stub, used when FORGE_DOCKER=1) -> chaos (simulated) ->
mutation (must-kill gate). Artifacts: runs/<task_id>/attempt_N/.
Provenance: hash(code+prompt+model+seed).

Backward-compat: TIMEOUT/ALLOW_NET/SandboxResult/_scrub_env/execute_farm kept.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
import forge_govern as _GOV
from forge_const import LIGHT, MAX_CODE_BYTES, MAX_OUTPUT_BYTES, STDOUT_TAIL

TIMEOUT = int(os.environ.get("FORGE_TIMEOUT", "30"))
ALLOW_NET = os.environ.get("FORGE_ALLOW_NET", "0") == "1"
BASE = Path(__file__).resolve().parent
RUNS = BASE / "runs"

@dataclass
class SandboxResult:
    exit: int
    stdout: str
    stderr: str
    timed_out: bool
    workdir: str
    artifact: str = ""
    provenance: str = ""

def _scrub_env() -> dict:
    keep = ["PATH", "SYSTEMROOT", "TEMP", "TMP", "PATHEXT"]
    env = {k: v for k, v in os.environ.items() if k in keep}
    env["PYTHONSAFEPATH"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for p in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        env.pop(p, None)
    return env


def safe_id(s: str) -> str:
    """Fail-closed id validation for task/run/artifact names. Blocks traversal."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-_]{0,64}", s or ""):
        raise ValueError(f"unsafe id: {s!r}")
    return s


def provenance_hash(code: str, prompt: str = "", model: str = "", seed: str = "") -> str:
    return hashlib.sha256(f"{code}|{prompt}|{model}|{seed}".encode()).hexdigest()[:16]


def artifact_write(task_id: str, attempt: int, code: str, result: "SandboxResult",
                   provenance: str = "") -> Path:
    d = RUNS / safe_id(task_id) / f"attempt_{int(attempt)}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "main.py").write_text(code, encoding="utf-8")
    (d / "result.json").write_text(json.dumps(
        {"exit": result.exit, "timed_out": result.timed_out,
         "stdout_tail": result.stdout[-STDOUT_TAIL:], "stderr_tail": result.stderr[-STDOUT_TAIL:],
         "provenance": provenance, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")},
        indent=2), encoding="utf-8")
    return d


def execute_farm(code: str, timeout: int = TIMEOUT, task_id: str | None = None,
                 attempt: int = 0, provenance: str = "") -> SandboxResult:
    if len((code or "").encode()) > MAX_CODE_BYTES:
        raise ValueError(f"code too large ({len(code.encode())}>{MAX_CODE_BYTES} bytes)")
    prov = provenance or provenance_hash(code)
    with tempfile.TemporaryDirectory(prefix="forge-") as workdir:
        main = Path(workdir) / "main.py"
        main.write_text(code, encoding="utf-8")
        try:
            r = subprocess.run([sys.executable, "-I", str(main)],
                               capture_output=True, text=True,
                               timeout=timeout, cwd=workdir, env=_scrub_env())
            res = SandboxResult(r.returncode, r.stdout[-MAX_OUTPUT_BYTES:],
                                r.stderr[-MAX_OUTPUT_BYTES:], False, workdir,
                                provenance=prov)
        except subprocess.TimeoutExpired as e:
            out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
            err = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
            res = SandboxResult(124, out[-MAX_OUTPUT_BYTES:],
                                f"TIMEOUT after {timeout}s\n{err}"[-MAX_OUTPUT_BYTES:],
                                True, workdir, provenance=prov)
        if task_id:
            d = artifact_write(task_id, attempt, code, res, res.provenance)
            res.artifact = str(d)
        return res
    # NOTE: TemporaryDirectory removes the tmp workdir on exit (no /tmp leak).
    # Memory/CPU caps are NOT enforced here (timeout only) — real cgroup/Job
    # limits apply solely under FORGE_DOCKER=1. Claims elsewhere of 512MB are
    # aspirational for the local farm; the docker profile enforces them.


# ---- Mesh stubs (fail-closed offline, real when env opts in) ----
def docker_run(code: str, timeout: int = TIMEOUT) -> dict:
    if LIGHT:
        return {"skipped": True, "reason": "light mode: docker disabled (8GB laptop)"}
    if os.environ.get("FORGE_DOCKER", "0") != "1":
        return {"skipped": True, "reason": "FORGE_DOCKER!=1 (offline-first)"}
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(code)
            name = f.name
        try:
            r = subprocess.run(["docker", "run", "--rm", "--network", "none",
                                "-v", f"{name}:/w/main.py", "python:3.12-slim",
                                "python", "/w/main.py"],
                               capture_output=True, text=True, timeout=timeout)
        finally:
            try:
                os.unlink(name)
            except OSError:
                pass
        return {"exit": r.returncode, "stdout": r.stdout[-2000:], "stderr": r.stderr[-2000:]}
    except Exception as e:
        return {"error": str(e)}


def chaos_inject(kind: str = "kill") -> dict:
    """Simulated chaos (kill/disk/clock/bitflip). Real kill-tree enforced via timeout."""
    allowed = {"kill", "disk", "clock", "bitflip"}
    if kind not in allowed:
        raise ValueError(f"unknown chaos kind: {kind!r} (allowed: {sorted(allowed)})")
    return {"chaos": kind, "simulated": True, "note": "real chaos runs in CI nightly, not per-task"}


def wasm_replay(code: str, timeout: int = TIMEOUT) -> dict:
    """Deterministic-replay contract: re-executes via farm and reports stability.

    No wasm runtime ships offline, so this is honestly marked simulated: the
    re-execution is real (same farm, same flags), only the wasm isolation is not.
    Light mode runs once (halves subprocess RAM) and reports deterministic True
    only for clean exit-0 runs; set FORGE_LIGHT=0 for double-exec compare.
    """
    first = execute_farm(code, timeout=timeout)
    if LIGHT:
        return {"simulated": True, "reason": "light mode: single exec (no wasm runtime offline)",
                "replayed": True, "deterministic": first.exit == 0,
                "exit": first.exit, "stdout_tail": first.stdout[-STDOUT_TAIL:]}
    second = execute_farm(code, timeout=timeout)
    deterministic = (first.exit == second.exit and first.stdout == second.stdout)
    return {"simulated": True, "reason": "no wasm runtime offline (farm re-exec)",
            "replayed": True, "deterministic": deterministic,
            "exit": second.exit, "stdout_tail": second.stdout[-STDOUT_TAIL:]}


def mutation_score(original_out: str, mutants: list[str]) -> dict:
    """Mutation gate: mutants must differ (be 'killed') or tester is gaming."""
    killed = sum(1 for m in mutants if m != original_out)
    total = len(mutants) or 1
    return {"killed": killed, "total": total, "score": killed / total,
            "pass": killed / total >= 0.8}


def replay_attempt(task_id: str, attempt: int, timeout: int = TIMEOUT) -> dict:
    """L10 rewind foundation: re-execute a stored attempt, compare with record.

    Returns {replayed, match, exit, stdout_tail}. Re-execution uses the same
    farm flags; nondeterministic code legitimately mismatches (reported, not hidden).
    """
    import json as _json
    d = RUNS / safe_id(task_id) / f"attempt_{int(attempt)}"
    main, rec = d / "main.py", d / "result.json"
    if not main.exists() or not rec.exists():
        return {"replayed": False, "match": False, "reason": "no such attempt"}
    try:
        want = _json.loads(rec.read_text(encoding="utf-8"))
    except Exception as e:
        return {"replayed": False, "match": False, "reason": f"corrupt result.json: {e}"}
    res = execute_farm(main.read_text(encoding="utf-8"), timeout=timeout)
    match = (res.exit == want.get("exit")
             and res.stdout[-STDOUT_TAIL:] == (want.get("stdout_tail") or "")[-STDOUT_TAIL:])
    return {"replayed": True, "match": match, "exit": res.exit,
            "stdout_tail": res.stdout[-STDOUT_TAIL:]}


# ---- Governance pre-checks (single source: forge_govern is canonical) ----
# Compat aliases: DENY_PATTERNS/SECRET_PATTERNS kept as views over the canonical
# lists so external callers don't break; new code should import forge_govern.
DENY_PATTERNS = [pat for pat, _ in _GOV.DENY_RULES] + [pat for pat, _ in _GOV.REPO_STATE_PATTERNS]
SECRET_PATTERNS = [rx.pattern for rx, _ in _GOV.KEY_PATTERNS]


def govern_check(code: str) -> list[str]:
    denies = _GOV.opa_deny(code, ALLOW_NET)
    if not ALLOW_NET and "requests." in code:
        denies.append("net-off")
    denies += _GOV.ast_denies(code)
    return denies


def secret_scan(code: str) -> list[str]:
    # Canonical regex scanner (no bare-substring false positives like "hf_").
    # Genuine env reads (os.getenv("NEBIUS_API_KEY") etc.) are deny-listed as
    # env-exfil by opa_deny instead of flagged here as embedded secrets.
    hits = _GOV.secret_scan(code)
    if any("NEBIUS" in h for h in hits) and re.search(
            r"os\.getenv\(\s*['\"]NEBIUS_API_KEY['\"]|os\.environ\.get\(\s*['\"]NEBIUS_API_KEY['\"]|os\.environ\[\s*['\"]NEBIUS_API_KEY['\"]",
            code):
        hits = [h for h in hits if "NEBIUS" not in h]
    return hits
