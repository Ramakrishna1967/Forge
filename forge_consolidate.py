"""Forge consolidate + sleep: episodic -> semantic promotion (Omega L1/L2).

Promote when: cluster>=2 OR footgun severity, AND sandbox proof exists,
AND critic review passes. Decay 0.05/30d, archive <0.3, tombstone on
invalidate. Sleep: ledger -> skills + dream counterfactuals + vacuum +
Merkle root. GC archives low-confidence skills.

Backward-compat: gc_archive_low_confidence() kept.
"""
from __future__ import annotations
import json
import shutil
import time
from pathlib import Path
import forge_memory as MEM
import forge_skills as S

BASE = Path(__file__).resolve().parent


def gc_archive_low_confidence() -> list[str]:
    moved = []
    for p in S.list_skills():
        try:
            rec = MEM._yaml_read(p)
            conf = float(rec.get("confidence", 1.0))
        except Exception:
            continue
        if S.needs_archive(conf):
            dest = p.parent / "_archive"
            dest.mkdir(exist_ok=True)
            shutil.move(str(p), str(dest / p.name))
            moved.append(p.name)
    return moved


def cluster_by_pattern(records: list[dict]) -> dict[str, list[dict]]:
    clusters: dict[str, list[dict]] = {}
    for r in records:
        key = (r.get("root_cause") or "unknown").strip().lower()[:80]
        clusters.setdefault(key, []).append(r)
    return clusters


def consolidate(records: list[dict] | None = None, sandbox_proof: bool = False,
                critic_ok: bool = False, min_cluster: int = 2) -> list[str]:
    """Promote clusters to semantic skills. Returns promoted skill names."""
    recs = records if records is not None else MEM.episodic_read(limit=200)
    promoted = []
    for pattern, group in cluster_by_pattern(recs).items():
        blob = json.dumps(group).lower()
        is_footgun = ("footgun" in blob) or any(
            g.get("status") == "failed" and "key" in json.dumps(g).lower() for g in group)
        severity = "footgun" if is_footgun else "normal"
        if not S.should_promote(len(group), severity):
            continue
        if len(group) >= min_cluster or severity == "footgun":
            if not (sandbox_proof and critic_ok):
                continue  # Eval Fortress gate: no proof, no promotion
            name = "lesson-" + MEM._hash(pattern)[:8]
            if _semantic_exists(name):
                continue
            skill = S.Skill(name=name, version="1.0.0",
                            when=f"when root cause matches: {pattern[:120]}",
                            rule=str(group[-1].get("fix", ""))[:500],
                            reason=str(pattern)[:200],
                            confidence=0.6, evidence=[g.get("id", "") for g in group])
            S.skill_save(skill)
            promoted.append(name)
    return promoted


def _semantic_exists(name: str) -> bool:
    return MEM.semantic_load(name) is not None


def dream_counterfactual(failed: dict) -> dict:
    """Dream: counterfactual hypothesis + proof-obligation artifact (needs_proof)."""
    rec = {"about": failed.get("id"), "hypothesis": f"if tried != {str(failed.get('tried'))[:80]}",
           "predicted": "sandbox exit 0 on retry with patched root cause",
           "needs_proof": True}
    try:
        import re as _re
        about = str(rec["about"] or "unknown")
        if not _re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-_]{0,64}", about):
            about = "h" + MEM._hash(about)
        d = BASE / ".forge" / "dreams"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"dream-{about}.json").write_text(
            json.dumps(rec, indent=2), encoding="utf-8")
        rec["artifact"] = True
    except Exception:
        rec["artifact"] = False
    return rec


def vacuum() -> dict:
    """Vacuum working cache + archive stale low-confidence skills."""
    from forge_const import LIGHT, LIGHT_CACHE_MAX
    moved = gc_archive_low_confidence()
    cache = BASE / ".forge" / "cache"
    pruned = 0
    if cache.exists():
        files = sorted(cache.glob("*.json"), key=lambda p: p.stat().st_mtime)
        if LIGHT and len(files) > LIGHT_CACHE_MAX:
            for stale in files[:-LIGHT_CACHE_MAX]:
                try:
                    stale.unlink()
                    pruned += 1
                except OSError:
                    pass
            files = files[-LIGHT_CACHE_MAX:]
    return {"archived": moved, "cache_entries": len(files) if cache.exists() else 0,
            "pruned": pruned}


def sleep_cycle(sandbox_proof: bool = True, critic_ok: bool = True) -> dict:
    """Sleep: consolidate ledger->skills + dream + vacuum + Merkle root."""
    from forge_const import LIGHT
    recs = MEM.episodic_read(limit=50 if LIGHT else 200)
    promoted = consolidate(recs, sandbox_proof=sandbox_proof, critic_ok=critic_ok)
    dreams = [dream_counterfactual(r) for r in recs if r.get("status") == "failed"][:2 if LIGHT else 5]
    dreams_dir = BASE / ".forge" / "dreams"
    dreams_dir.mkdir(parents=True, exist_ok=True)
    if dreams:
        (dreams_dir / f"dream-{int(time.time())}.json").write_text(
            json.dumps(dreams, indent=2), encoding="utf-8")
    vac = vacuum()
    root = MEM.merkle_root()
    log = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "promoted": promoted,
           "dreams": len(dreams), "vacuum": vac, "merkle_root": root}
    slog = BASE / ".forge" / "sleep_logs" / f"sleep-{int(time.time())}.json"
    slog.parent.mkdir(parents=True, exist_ok=True)
    slog.write_text(json.dumps(log, indent=2), encoding="utf-8")
    return log
