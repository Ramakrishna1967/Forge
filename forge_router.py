"""Forge LLM router: Token Factory only, cache + budget + cascade (Omega L7).

Cascade: cache -> Super-120B (attempt<=3) -> reasoning-high (attempt>3).
No non-Nemotron fallback. Retry 429/5xx only with backoff 0/5/15/45/120s.
Cache sha256(system|task|history). Budget tokens/USD/CO2/wall-clock,
economist veto. --run-file / FORGE_OFFLINE=1 bypasses LLM entirely.

Backward-compat: MODEL..., cache_key/get/put, get_client, call, log_cost kept.
"""
from __future__ import annotations
import hashlib
import json
import os
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
CACHE_DIR = BASE / ".forge" / "cache"
COST_LOG = BASE / "runs" / "cost.jsonl"
from forge_const import BACKOFF, BASE_URL, MODEL_DEFAULT  # noqa: E402 single source
MODEL_REASONING = os.environ.get("FORGE_REASONING_MODEL", "nvidia/nemotron-3-super-120b-a12b-high")
CO2_PER_1K_TOKENS_G = 0.4  # rough estimate for dashboard, not a claim

def cache_key(system: str, task: str, history: str) -> str:
    return hashlib.sha256(f"{system}|{task}|{history}".encode()).hexdigest()

def cache_get(key: str):
    p = CACHE_DIR / f"{key}.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            import sys as _sys
            print(f"[warn] corrupt router cache {p.name}: {e}", file=_sys.stderr)
            return None
    return None

def cache_put(key: str, val: dict) -> None:
    from forge_const import LIGHT, LIGHT_CACHE_MAX
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / f"{key}.json").write_text(json.dumps(val), encoding="utf-8")
    if LIGHT:
        try:
            files = sorted(CACHE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime)
            for stale in files[:-LIGHT_CACHE_MAX]:
                try:
                    stale.unlink()
                except OSError:
                    pass
        except OSError:
            pass

def get_client():
    try:
        from openai import OpenAI
    except ImportError as e:
        raise RuntimeError("pip install -r requirements.txt (needs openai)") from e
    api_key = os.environ.get("NEBIUS_API_KEY", "")
    if not api_key:
        raise RuntimeError("NEBIUS_API_KEY not set (see .env.example)")
    return OpenAI(base_url=BASE_URL, api_key=api_key)

def _retryable(msg: str) -> bool:
    m = str(msg).lower()
    return any(k in m for k in ("429", "500", "502", "503", "504", "timeout", "rate", "overloaded"))


def call(task: str, system: str, history: str = "", model: str = MODEL_DEFAULT,
         max_retries: int = 3):
    key = cache_key(system, task, history)
    if os.environ.get("FORGE_CACHE", "1") == "1":
        hit = cache_get(key)
        if hit is not None:
            return hit["content"], True
    client = get_client()
    last = None
    for i in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": task + ("\n\n" + history if history else "")}])
            content = resp.choices[0].message.content
            usage = getattr(resp, "usage", None)
            log_cost(task[:60], usage)
            cache_put(key, {"content": content})
            return content, False
        except Exception as e:
            last = e
            if _retryable(str(e)) and i < max_retries - 1:
                time.sleep(BACKOFF[min(i + 1, len(BACKOFF) - 1)] if not os.environ.get("FORGE_FAST_TEST") else 0)
                continue
            raise
    raise last


def call_cascade(task: str, system: str, history: str = "", attempt: int = 1):
    """System-1 (attempt 1-3, cached Super) vs System-2 (attempt>3, reasoning-high)."""
    model = MODEL_DEFAULT if attempt <= 3 else MODEL_REASONING
    cached_first = attempt == 1
    content, hit = call(task, system, history, model=model)
    return {"content": content, "cached": hit, "model": model,
            "system2": attempt > 3, "fast_path": cached_first and hit}


def budget_check(prompt_tokens: int = 0, completion_tokens: int = 0,
                 wall_s: float = 0.0) -> tuple[bool, str]:
    max_tok = int(os.environ.get("FORGE_BUDGET_TOKENS", "200000"))
    max_wall = float(os.environ.get("FORGE_BUDGET_WALL_S", "600"))
    used_tok = prompt_tokens + completion_tokens
    if used_tok > max_tok:
        return False, f"token budget exceeded {used_tok}>{max_tok} (economist veto)"
    if wall_s > max_wall:
        return False, f"wall-clock budget exceeded {wall_s:.0f}s>{max_wall:.0f}s"
    return True, "ok"


def offline_bypass() -> bool:
    return os.environ.get("FORGE_OFFLINE", "0") == "1" or not os.environ.get("NEBIUS_API_KEY", "")

def log_cost(task: str, usage) -> None:
    try:
        import re as _re
        task = _re.sub(r"hf_[A-Za-z0-9]+|sk-[A-Za-z0-9]+|AKIA[0-9A-Z]{16}", "***", task)
        COST_LOG.parent.mkdir(parents=True, exist_ok=True)
        pin, pout = 0, 0
        if usage is not None:
            pin = int(getattr(usage, "prompt_tokens", 0) or 0)
            pout = int(getattr(usage, "completion_tokens", 0) or 0)
        co2_g = round((pin + pout) / 1000 * CO2_PER_1K_TOKENS_G, 3)
        rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "task": task,
               "in": pin, "out": pout, "co2_g": co2_g}
        with COST_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception:
        pass
