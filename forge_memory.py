"""Forge memory: 9-tier durable state (Omega L1).

Tiers: 1 Sensory (ring, not persisted) 2 Working (last_context.json)
3 Episodic (ledger.jsonl, hash-chained, immutable) 4 Autobiographical (life.md)
5 Semantic (registry/*.vX.Y.Z.yaml, max 100) 6 Procedural (tool_patterns.yaml, Bayes)
7 Prospective (todo_future.jsonl) 8 Flashbulb (pinned footguns, never TTL)
9 Knowledge Graph + Vector mirror (never authoritative).

Backward-compat: episodic_append/read + working_save keep signatures.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
FORGE_DIR = BASE / ".forge"
EPISODIC = FORGE_DIR / "episodic" / "ledger.jsonl"
SEMANTIC_DIR = FORGE_DIR / "semantic" / "registry"
WORKING = FORGE_DIR / "working" / "last_context.json"
LIFE = BASE / "life.md"
PROCEDURAL = FORGE_DIR / "procedural" / "tool_patterns.yaml"
PROSPECTIVE = FORGE_DIR / "working" / "todo_future.jsonl"
FLASHBULB = FORGE_DIR / "working" / "flashbulb.jsonl"
GRAPH = FORGE_DIR / "graph" / "links.jsonl"
VECTOR_MIRROR = FORGE_DIR / "vector" / "mirror.json"

DECAY_PER_30D = 0.05
ARCHIVE_BELOW = 0.3


def _hash(s: str) -> str:
    return hashlib.blake2b(s.encode(), digest_size=8).hexdigest()


def _ensure_parent(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)


def _atomic_write(p: Path, text: str) -> None:
    """Crash-safe write: tmp file in same dir + os.replace (atomic on POSIX+Win)."""
    _ensure_parent(p)
    tmp = p.with_name(f".{p.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, p)


# ---- Tier 3: episodic (hash-chained, immutable, append-only) ----
def _tail_lines(limit: int) -> list[str]:
    """O(tail): stream from disk, keep only the last `limit` non-empty lines."""
    from collections import deque
    buf: deque[str] = deque(maxlen=max(1, limit))
    with EPISODIC.open(encoding="utf-8") as f:
        for ln in f:
            if ln.strip():
                buf.append(ln)
    return list(buf)


def _last_record() -> dict | None:
    if not EPISODIC.exists():
        return None
    tail = _tail_lines(1)
    if not tail:
        return None
    try:
        return json.loads(tail[0])
    except Exception:
        return None


def episodic_append(task: str, tried: str, root_cause: str, fix: str, status: str) -> dict:
    prev = _last_record()
    prev_hash = (prev or {}).get("hash", "genesis")
    eid = f"e_{int(time.time())}_{_hash(tried + fix)}"
    chain = _hash(prev_hash + "|" + tried + "|" + fix)
    rec = {"id": eid, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "task": task,
           "tried": tried, "root_cause": root_cause, "fix": fix,
           "status": status, "prev_hash": prev_hash, "hash": chain}
    _ensure_parent(EPISODIC)
    with EPISODIC.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def episodic_read(limit: int = 50) -> list[dict]:
    if not EPISODIC.exists():
        return []
    out = []
    for ln in _tail_lines(limit):
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return out


def episodic_verify_chain(limit: int = 100000) -> tuple[bool, int]:
    """Recompute hash chain. Returns (ok, bad_index). Genesis prev allowed."""
    recs = episodic_read(limit=limit)
    prev_hash = "genesis"
    # If ledger predates chaining (old recs w/o prev_hash), anchor from first hash.
    for i, r in enumerate(recs):
        h, ph = r.get("hash", ""), r.get("prev_hash")
        if ph is None:
            prev_hash = h  # legacy record: re-anchor, still verifiable forward
            continue
        expect = _hash(ph + "|" + r.get("tried", "") + "|" + r.get("fix", ""))
        if ph != prev_hash or expect != h:
            return False, i
        prev_hash = h
    return True, -1


def merkle_root(limit: int = 100000) -> str:
    leaves = [r.get("hash", "") for r in episodic_read(limit=limit) if r.get("hash")]
    if not leaves:
        return "empty"
    level = [_hash(x) for x in leaves]
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            pair = level[i] + (level[i + 1] if i + 1 < len(level) else level[i])
            nxt.append(_hash(pair))
        level = nxt
    return level[0]


# ---- Tier 2: working ----
def working_save(ctx: dict) -> None:
    _atomic_write(WORKING, json.dumps(ctx, indent=2))


# ---- Tier 5: semantic registry (YAML, max 100, tombstone on invalidate) ----
def _yaml_write(path: Path, rec: dict) -> None:
    try:
        import yaml  # type: ignore
    except ImportError as e:
        raise RuntimeError("pyyaml required (pip install -r requirements.txt)") from e
    _atomic_write(path, yaml.safe_dump(rec, sort_keys=False, allow_unicode=True))


def _yaml_read(path: Path) -> dict:
    try:
        import yaml  # type: ignore
    except ImportError as e:
        raise RuntimeError("pyyaml required (pip install -r requirements.txt)") from e
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _safe_name(s: str) -> str:
    """Fail-closed registry name/version guard. Blocks path traversal."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-_.]{0,64}", s or "") or ".." in s or "/" in s or "\\" in s:
        raise ValueError(f"unsafe name: {s!r}")
    return s


def semantic_save(name: str, rec: dict) -> Path:
    version = rec.get("version", "1.0.0")
    _safe_name(name)
    _safe_name(str(version))
    path = SEMANTIC_DIR / f"{name}.v{version}.yaml"
    _yaml_write(path, rec)
    return path


def semantic_load(name: str, version: str | None = None) -> dict | None:
    _safe_name(name)
    if version:
        _safe_name(str(version))
        p = SEMANTIC_DIR / f"{name}.v{version}.yaml"
        return _yaml_read(p) if p.exists() else None
    cands = sorted(SEMANTIC_DIR.glob(f"{name}.v*.yaml"))
    if not cands:
        return None
    return _yaml_read(cands[-1])


def semantic_list() -> list[Path]:
    SEMANTIC_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(SEMANTIC_DIR.glob("*.yaml"))


def semantic_tombstone(name: str, version: str, reason: str) -> Path | None:
    _safe_name(name)
    _safe_name(str(version))
    p = SEMANTIC_DIR / f"{name}.v{version}.yaml"
    if not p.exists():
        return None
    rec = _yaml_read(p)
    rec["deprecated"] = True
    rec["tombstone_reason"] = reason
    _yaml_write(p, rec)
    return p


# ---- Tier 6: procedural (Bayes-ish tool success rates) ----
def procedural_record(tool: str, ok: bool) -> dict:
    PROCEDURAL.parent.mkdir(parents=True, exist_ok=True)
    rates: dict = {}
    if PROCEDURAL.exists():
        try:
            import yaml  # type: ignore
            rates = yaml.safe_load(PROCEDURAL.read_text(encoding="utf-8")) or {}
        except Exception:
            rates = {}
    entry = rates.get(tool, {"uses": 0, "success": 0}) or {"uses": 0, "success": 0}
    entry["uses"] = int(entry.get("uses", 0)) + 1
    entry["success"] = int(entry.get("success", 0)) + (1 if ok else 0)
    rates[tool] = entry
    try:
        import yaml  # type: ignore
        PROCEDURAL.write_text(yaml.safe_dump(rates, sort_keys=True), encoding="utf-8")
    except Exception:
        PROCEDURAL.write_text(json.dumps(rates, indent=2), encoding="utf-8")
    return entry


def procedural_rate(tool: str) -> float:
    if not PROCEDURAL.exists():
        return 0.5
    try:
        import yaml  # type: ignore
        rates = yaml.safe_load(PROCEDURAL.read_text(encoding="utf-8")) or {}
    except Exception:
        try:
            rates = json.loads(PROCEDURAL.read_text(encoding="utf-8"))
        except Exception:
            return 0.5
    e = rates.get(tool)
    if not e or not e.get("uses"):
        return 0.5
    return float(e.get("success", 0)) / float(e.get("uses", 1))


# ---- Tier 7: prospective ----
def prospective_add(text: str) -> dict:
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "item": text}
    _ensure_parent(PROSPECTIVE)
    with PROSPECTIVE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def prospective_read(limit: int = 50) -> list[dict]:
    if not PROSPECTIVE.exists():
        return []
    from collections import deque
    buf: deque[str] = deque(maxlen=max(1, limit))
    with PROSPECTIVE.open(encoding="utf-8") as f:
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


# ---- Tier 8: flashbulb (pinned, never TTL/GC) ----
def flashbulb_pin(text: str, tag: str = "footgun") -> dict:
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "tag": tag, "text": text}
    _ensure_parent(FLASHBULB)
    with FLASHBULB.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def flashbulb_read(limit: int = 100) -> list[dict]:
    if not FLASHBULB.exists():
        return []
    from collections import deque
    buf: deque[str] = deque(maxlen=max(1, limit))
    with FLASHBULB.open(encoding="utf-8") as f:
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


# ---- Tier 4: autobiographical ----
def life_append(line: str) -> None:
    LIFE.parent.mkdir(parents=True, exist_ok=True)
    prefix = "" if (LIFE.exists() and LIFE.read_text(encoding="utf-8").endswith("\n")) or not LIFE.exists() else "\n"
    with LIFE.open("a", encoding="utf-8") as f:
        f.write(prefix + "- " + line.strip() + "\n")


# ---- Tier 9: graph + vector mirror (never authoritative) ----
def graph_link(a: str, b: str, rel: str = "relates") -> dict:
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "a": a, "b": b, "rel": rel}
    _ensure_parent(GRAPH)
    with GRAPH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def graph_neighbors(node: str, limit: int = 20) -> list[dict]:
    if not GRAPH.exists():
        return []
    from collections import deque
    from forge_const import LIGHT
    tail_n = 500 if LIGHT else 5000  # light: scan last 500 lines only (8GB laptop)
    buf: deque[str] = deque(maxlen=tail_n)
    with GRAPH.open(encoding="utf-8") as f:
        for ln in f:
            if ln.strip():
                buf.append(ln)
    out = []
    for ln in buf:
        try:
            r = json.loads(ln)
        except Exception:
            continue
        if r.get("a") == node or r.get("b") == node:
            out.append(r)
    return out[-limit:]


def vector_mirror_put(key: str, text: str) -> None:
    from forge_const import LIGHT, LIGHT_VECTOR_MAX
    store: dict = {}
    if VECTOR_MIRROR.exists():
        try:
            if VECTOR_MIRROR.stat().st_size > 1_000_000:
                store = {}  # light: oversized mirror resets instead of growing RAM
            else:
                store = json.loads(VECTOR_MIRROR.read_text(encoding="utf-8"))
        except Exception:
            store = {}
    store[key] = text
    if LIGHT and len(store) > LIGHT_VECTOR_MAX:
        for old in list(store)[:len(store) - LIGHT_VECTOR_MAX]:
            del store[old]
    _atomic_write(VECTOR_MIRROR, json.dumps(store, indent=2))


def vector_mirror_get(key: str) -> str | None:
    if not VECTOR_MIRROR.exists():
        return None
    try:
        return json.loads(VECTOR_MIRROR.read_text(encoding="utf-8")).get(key)
    except Exception:
        return None
