# Forge — System Architecture v4 Omega (Hermes++)

Self-improving coding agent. Nebius x NVIDIA hackathon.
Model: `nvidia/nemotron-3-super-120b-a12b` via `https://api.tokenfactory.nebius.com/v1`.
Status: IMPLEMENTED + HARDENED + PHASE2 + REVIEW2 + COMPLETE — 57 offline tests green (9 harness + 6 v2 + 10 omega + 7 hardening + 17 phase2 + 8 offline-cov), demo-ok re-verified.

## L0 Identity + Time
Persistent `agent_id`, `incarnation N` (`.forge/agent.json`). Heartbeat `tick.json`.
Sleep/wake: wake=serve, sleep=consolidate ledger→skills + dream counterfactuals + vacuum.
`life.md` autobiographical 1-line/task for continuity.
Impl: `forge_loop.identity/heartbeat` + `forge_memory.life_append` + `forge_consolidate.sleep_cycle`.

## L1 9-Tier Memory
1. Sensory (raw ring, 10k tokens) 2. Working (task+top-k+last5+hypotheses)
3. Episodic `.forge/episodic/ledger.jsonl` hash-chained, immutable
4. Autobiographical `life.md` 5. Semantic `.forge/semantic/registry/*.vX.Y.Z.yaml` max100
6. Procedural `tool_patterns.yaml` Bayes 7. Prospective `todo_future.jsonl`
8. Flashbulb (pinned footguns, never TTL) 9. Knowledge Graph + Vector mirror (never authoritative)
Consolidate: cluster>=2 OR footgun + sandbox proof + critic review. Decay 0.05/30d, <0.3 archive. Tombstone on invalidate. GC + Merkle root per sleep.
Impl: `forge_memory.py` (chain verify, merkle_root, semantic CRUD+tombstone, procedural Bayes, prospective, flashbulb, graph, vector mirror).

## L2 Skill Genome
`{name, version, when, rule, reason, confidence, evidence[], parents, children, conflicts, cost_saved, uses, failures}`. DAG + conflict resolver (new evidence wins). Evolution: mutate/crossover, fitness=`lift*uses-tokens-failures*10`. Fuzz 10 tasks pre-activation. Market staging + human approve.
Impl: `forge_skills.Skill/fitness/conflict_resolve/fuzz_gate/stage_for_market/record_use/projection_sync`.

## L3 15-Role Swarm
`orchestrator, planner, librarian, historian, coder, critic, tester, security, red-teamer, oracle, economist, auditor, archivist, dreamer, meta`
Envelope `{task_id, dag_node, from→to, artifact, PASS/FAIL/NEEDS-CODE, evidence, self_score, tokens}`. Byzantine 2/3 (critic/tester/security/oracle) to merge. Auction for coder. Debate coder vs red-teamer 2 rounds.
Impl: `forge_agents.SWARM_ROLES/byzantine_merge/auction/debate_round` (compat `ROLES` 7 kept).

## L4 Planning Engine
HTN + MCTS(4 rollouts UCB1) + Tree-of-Thought(branch3 prune1) + GIVEN/WHEN/THEN decidable goal.
G0 identity, G1 plan>=4, G2 tests+mutation, G3 sec+redteam, G4 budget+provenance. Max 5 attempts, backoff 0/5/15/45/120s. Ambiguous → needs-code.queue, freeze writes, ask 1 question.
Impl: `forge_agents.gate_g0/g1/g2/g3/g4, mcts_pick, tot_branch, decidable_goal, needs_code, backoff_for` + `forge_loop.plan/run_loop`.

## L5 Cognition
System-1 (cache/skill>0.9 single call) vs System-2 (full swarm ToT self-consistency n=5). Dual self-score, delta>1 audit. Reflection `{failed,hypothesis,change,predicted}`. Immutable decision ledger.
Impl: `forge_agents.system_route/audit_scores/reflection_record/decision_log` (`runs/decisions.jsonl`).

## L6 Sandbox Mesh
`tmp/forge-xxx/main.py`, `sys.executable -I`, timeout30, scrubbed env, PYTHONSAFEPATH=1, net-off, 512MB/30s, kill-tree. → wasm replay → docker --network none → chaos (kill/disk/clock/bitflip) → mutation (must kill or tester gaming). Artifacts `runs/<id>/attempt_N/`. Provenance `code+prompt+model+seed` hash.
Impl: `forge_sandbox.execute_farm/artifact_write/provenance_hash/docker_run/chaos_inject/mutation_score/govern_check/secret_scan` (mesh stages fail-closed offline).

## L7 LLM Cascade + Economy
`cache → draft → Super-120B → reasoning-high(attempt>3)`. No non-Nemotron fallback. Retry 429/5xx only. Cache sha256. Budget tokens/USD/CO2/wall-clock, economist veto. `--run-file` offline bypass.
Impl: `forge_router.call/call_cascade/budget_check/offline_bypass/log_cost` (+`FORGE_OFFLINE=1`).

## L8 Eval Fortress
Unit offline 9+, integration, e2e fib demo-ok, hidden oracle, metamorphic, fuzz100, red-team, regression replay, Elo per skill/agent. Fail blocks Learn.
Impl: `tests/test_harness.py` (9) + `tests/test_v2.py` (6) + `tests/test_omega.py` (10: chain, tiers, genome, consolidate gates, mesh, economy, swarm, obs/govern, loop wiring). Consolidate requires sandbox proof + critic ok or promotion is refused.

## L9 Observability + Governance
OTel spans, lineage prompt→skill, cost/carbon dashboard, secret scan, OPA deny(shell=True,net,key-in-code), HALT=1 kill-switch, audit tar replayable.
Impl: `forge_obs.span/log_lineage/dashboard/audit_export` + `forge_govern.govern/opa_deny/secret_scan/check_halt`.

## L10 Multiverse / L11 Federation / L12 Proofs / L13-L17
Universes fork+rewind+replay. CRDT gossip, 3f+1 global skill vote, slashing. Proof-carrying patch, TLA+ loop, SLSA L4, ZK receipt, Firecracker+seccomp+eBPF. Active inference (surprise minimization, curiosity, empowerment). Self-rewriting prompts via Elo nightly, Gödel-gate (prove no regression). Prediction market staking, royalties. Adversarial hell mandatory. Full provenance forever.
Impl (foundations, full mesh deferred): provenance hash + artifacts (replay/rewind), market staging dir + human approve (royalties hook), decision ledger (audit), fuzz/mutation gates (adversarial hell seed), vector adapter interface (plug backend).

## File Spine (CODED)
```
forge.py (compat shim, v1 loop intact), forge_loop.py (Omega wiring),
forge_memory/skills/sandbox/router/agents/obs/consolidate/govern.py
.forge/{agent.json, episodic,semantic/procedural,graph,vector,working,cache,dreams,sleep_logs,market}/
runs/<id>/attempt_N/ + ledger.jsonl + decisions.jsonl + traces.jsonl + lineage.jsonl + cost.jsonl
tests/test_omega.py (10) memory.md/skills.md/life.md
```

## Verification (57 green, offline, no key)
py_compile ok, 57 passed (9 harness + 6 v2 + 10 omega + 7 hardening + 17 phase2 + 8 offline-cov), fib demo-ok via forge.py AND forge_loop.py --run-file.

