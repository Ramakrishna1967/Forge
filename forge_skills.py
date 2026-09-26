"""Forge skills: versioned Skill Genome registry (Omega L2).

Genome: {name, version, when, rule, reason, confidence, evidence[],
parents, children, conflicts, cost_saved, uses, failures}.
DAG + conflict resolver (new evidence wins). Evolution fitness =
lift*uses - tokens - failures*10. Fuzz 10 tasks pre-activation.
Market staging + human approve. Max 100 active.

Backward-compat: list_skills/active_count/should_promote/decay/needs_archive kept.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import forge_memory as M

BASE = Path(__file__).resolve().parent
REGISTRY = BASE / ".forge" / "semantic" / "registry"
PROJECTION = BASE / "skills.md"
MARKET = BASE / ".forge" / "market" / "staging"
MAX_ACTIVE = 100


def list_skills() -> list[Path]:
    return sorted(REGISTRY.glob("*.yaml"))


def active_count() -> int:
    return len([p for p in list_skills() if "_archive" not in str(p)])


def should_promote(cluster_count: int, severity: str) -> bool:
    if severity == "footgun":
        return True
    return cluster_count >= 2


def decay(confidence: float, days_stale: int) -> float:
    return max(0.0, confidence - 0.05 * (days_stale // 30))


def needs_archive(confidence: float) -> bool:
    return confidence < 0.3


@dataclass
class Skill:
    name: str
    version: str = "1.0.0"
    when: str = ""
    rule: str = ""
    reason: str = ""
    confidence: float = 0.5
    evidence: list = field(default_factory=list)
    parents: list = field(default_factory=list)
    children: list = field(default_factory=list)
    conflicts: list = field(default_factory=list)
    cost_saved: float = 0.0
    uses: int = 0
    failures: int = 0
    lift: float = 0.0
    tokens: int = 0

    def fitness(self) -> float:
        return fitness(self.lift, self.uses, self.tokens, self.failures)


def fitness(lift: float, uses: int, tokens: int, failures: int) -> float:
    return lift * uses - tokens - failures * 10


def skill_validate(rec: dict) -> tuple[bool, str]:
    for k in ("name", "when", "rule", "reason"):
        if not rec.get(k):
            return False, f"missing {k}"
    c = float(rec.get("confidence", 0.5))
    if not (0.0 <= c <= 1.0):
        return False, "confidence out of range"
    return True, "ok"


def skill_save(s: Skill) -> Path:
    rec = {"name": s.name, "version": s.version, "when_applies": s.when,
           "rule": s.rule, "reason": s.reason, "confidence": s.confidence,
           "evidence": s.evidence, "parents": s.parents, "children": s.children,
           "conflicts": s.conflicts, "cost_saved": s.cost_saved,
           "uses": s.uses, "failures": s.failures,
           "deprecated": False, "superseded_by": None}
    ok, msg = skill_validate({"name": s.name, "when": s.when, "rule": s.rule,
                              "reason": s.reason, "confidence": s.confidence})
    if not ok:
        raise ValueError(f"invalid skill: {msg}")
    return M.semantic_save(s.name, rec)


def skill_load(name: str, version: str | None = None) -> Skill | None:
    rec = M.semantic_load(name, version)
    if not rec:
        return None
    return Skill(name=rec.get("name", name), version=str(rec.get("version", "1.0.0")),
                 when=str(rec.get("when_applies", rec.get("when", ""))),
                 rule=str(rec.get("rule", "")), reason=str(rec.get("reason", "")),
                 confidence=float(rec.get("confidence", 0.5)),
                 evidence=list(rec.get("evidence", []) or []),
                 parents=list(rec.get("parents", []) or []),
                 children=list(rec.get("children", []) or []),
                 conflicts=list(rec.get("conflicts", []) or []),
                 cost_saved=float(rec.get("cost_saved", 0.0)),
                 uses=int(rec.get("uses", 0)), failures=int(rec.get("failures", 0)))


def conflict_resolve(existing: dict, incoming: dict) -> dict:
    """New evidence wins; merge evidence lists, bump minor version."""
    merged = dict(existing)
    merged_ev = list(dict.fromkeys(list(existing.get("evidence", [])) + list(incoming.get("evidence", []))))
    merged.update(incoming)
    merged["evidence"] = merged_ev
    try:
        major, minor, patch = (str(existing.get("version", "1.0.0")).split(".") + ["0", "0", "0"])[:3]
        merged["version"] = f"{major}.{minor}.{int(patch) + 1}"
    except Exception:
        merged["version"] = incoming.get("version", "1.0.1")
    return merged


def fuzz_gate(results: list[bool], required: int = 10) -> bool:
    """10 sandbox tasks must all pass before activation (prevents gaming)."""
    return len(results) >= required and all(results)


def stage_for_market(s: Skill) -> Path:
    M._safe_name(s.name)
    M._safe_name(str(s.version))
    MARKET.mkdir(parents=True, exist_ok=True)
    dest = MARKET / f"{s.name}.v{s.version}.yaml"
    M._yaml_write(dest, {"name": s.name, "version": s.version, "when_applies": s.when,
                         "rule": s.rule, "reason": s.reason, "confidence": s.confidence,
                         "evidence": s.evidence, "needs_human_approve": True})
    return dest


def record_use(name: str, ok: bool, tokens: int = 0) -> None:
    s = skill_load(name)
    if not s:
        return
    s.uses += 1
    s.tokens += tokens
    if not ok:
        s.failures += 1
    skill_save(s)


def projection_sync(limit: int = MAX_ACTIVE) -> Path:
    """Regenerate skills.md projection from top-confidence registry entries."""
    recs = []
    for p in list_skills():
        if "_archive" in str(p):
            continue
        try:
            recs.append(M._yaml_read(p))
        except Exception:
            continue
    recs.sort(key=lambda r: float(r.get("confidence", 0) or 0), reverse=True)
    lines = ["# Forge Skills — distilled reusable knowledge (keep small, high-signal)", ""]
    for r in recs[:limit]:
        lines += [f"## {r.get('name')}",
                  f"- when this applies: {r.get('when_applies', '')}",
                  f"- rule: {r.get('rule', '')}",
                  f"- reason: {r.get('reason', '')}", ""]
    PROJECTION.write_text("\n".join(lines), encoding="utf-8")
    return PROJECTION
