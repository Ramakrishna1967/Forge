"""Forge observability: decision ledger + traces + lineage + carbon (Omega L9).

OTel-style spans -> runs/traces.jsonl. Lineage prompt->skill.
Cost/carbon dashboard source: runs/cost.jsonl. Audit export: tar.gz of runs/<id>.

Backward-compat: LEDGER/log_attempt/read_ledger kept.
"""
from __future__ import annotations
import contextlib
import json
import re
import tarfile
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
LEDGER = BASE / "runs" / "ledger.jsonl"
TRACES = BASE / "runs" / "traces.jsonl"
LINEAGE = BASE / "runs" / "lineage.jsonl"

_REDACT_RES = [
    re.compile(r"NEBIUS_API_KEY\s*=\s*['\"][^'\"]*['\"]"),
    re.compile(r"hf_[A-Za-z0-9]+"),
    re.compile(r"sk-[A-Za-z0-9]+"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
]


def redact(text: str) -> str:
    for rx in _REDACT_RES:
        text = rx.sub("***", text)
    return text

def log_attempt(task_id: str, attempt: int, model: str, code_hash: str,
                exit_code: int, stdout_tail: str = "", stderr_tail: str = "",
                latency_ms: int = 0) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "task_id": task_id,
           "attempt": attempt, "model": model, "code_hash": code_hash,
           "exit": exit_code, "stdout_tail": redact(stdout_tail[-500:]),
           "stderr_tail": redact(stderr_tail[-500:]), "latency_ms": latency_ms}
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")

def read_ledger(limit: int = 20) -> list[dict]:
    if not LEDGER.exists():
        return []
    from collections import deque
    buf: deque[str] = deque(maxlen=max(1, limit))
    with LEDGER.open(encoding="utf-8") as f:
        for ln in f:
            if ln.strip():
                buf.append(ln)
    out = []
    for ln in buf:
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return out


@contextlib.contextmanager
def span(task_id: str, name: str, **attrs):
    t0 = time.time()
    try:
        yield {"task_id": task_id, "name": name}
        status = "ok"
    except Exception as e:
        status = f"error: {e}"
        raise
    finally:
        TRACES.parent.mkdir(parents=True, exist_ok=True)
        rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "task_id": task_id,
               "span": name, "latency_ms": int((time.time() - t0) * 1000),
               "status": status, "attrs": attrs}
        with TRACES.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")


def log_lineage(task_id: str, prompt_hash: str, skill_ids: list[str], model: str) -> None:
    LINEAGE.parent.mkdir(parents=True, exist_ok=True)
    with LINEAGE.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                           "task_id": task_id, "prompt_hash": prompt_hash,
                           "skills": skill_ids, "model": model}) + "\n")


def dashboard() -> dict:
    """Cost/carbon summary from runs/cost.jsonl (operator view)."""
    cost_log = BASE / "runs" / "cost.jsonl"
    total_in, total_out, n = 0, 0, 0
    if cost_log.exists():
        with cost_log.open(encoding="utf-8") as f:
            for ln in f:
                if not ln.strip():
                    continue
                try:
                    r = json.loads(ln)
                    total_in += int(r.get("in", 0))
                    total_out += int(r.get("out", 0))
                    n += 1
                except Exception:
                    continue
    return {"calls": n, "prompt_tokens": total_in, "completion_tokens": total_out,
            "total_tokens": total_in + total_out,
            "co2_g_est": round((total_in + total_out) / 1000 * 0.4, 2)}


def audit_export(task_id: str) -> Path | None:
    from forge_sandbox import safe_id
    try:
        safe_id(task_id)
    except ValueError:
        return None
    src = BASE / "runs" / task_id
    if not src.exists():
        return None
    dest = BASE / "runs" / f"{task_id}-audit.tar.gz"

    def _safe_filter(ti):
        # refuse symlinks/hardlinks/specials: sandbox code could plant them
        if getattr(ti, "issym", lambda: False)() or getattr(ti, "islnk", lambda: False)():
            return None
        if not (ti.isfile() or ti.isdir()):
            return None
        return ti

    with tarfile.open(dest, "w:gz") as tar:
        tar.add(src, arcname=task_id, filter=_safe_filter)
    return dest
