# Forge — self-improving coding agent (Nebius x NVIDIA hackathon)

Runs on NVIDIA Nemotron via Nebius Token Factory. Writes code, runs it, fixes it, remembers what worked.

## Quickstart

    pip install -r requirements.txt
    set NEBIUS_API_KEY=your_key_here
    python forge.py --task "write fib(10) to out.txt and print it"
    python forge_loop.py --task "write fib(10) to out.txt and print it"
    python forge_loop.py --run-file examples/demo_task.py
    python forge_loop.py --task "..." --offline   # verify without LLM calls
    python -m pytest tests/ -v

## Light mode (8GB laptops, default ON)

    set FORGE_LIGHT=1        # default; single-exec replay, no docker, capped cache
    set FORGE_OFFLINE=1      # no LLM calls, remote Nemotron only when key set
    make test-light          # quiet, no coverage, fast backoff
    make demo-light          # offline fib demo, minimal RAM
    make prune               # evict router cache to newest 100 + archive weak skills
    set FORGE_LIGHT=0        # restore full mesh (double replay, docker opt-in)

    Skip on weak hardware: Docker, `pip install forge[vector]` (faiss/chroma),
    `make cov` (coverage doubles RAM). Vector stays file-mirror unless
    `FORGE_VECTOR=faiss|chroma` is set explicitly.

## Core loop

Recall memory.md and skills.md, Plan 2-5 lines, Write minimal code, Run sandbox 30s timeout, Observe real output, Fix max 5 attempts, Learn to memory files.

## Files

    forge.py = compat harness (v1 Recall->Learn loop, intact)
    forge_loop.py = Omega wiring (L0 identity + G0-G4 gates + govern + artifacts)
    forge_memory.py = 9-tier memory (hash-chained episodic, semantic YAML, procedural Bayes, prospective, flashbulb, graph, vector mirror)
    forge_skills.py = Skill Genome (fitness, conflict resolver, fuzz gate, market staging, projection sync)
    forge_sandbox.py = sandbox mesh (farm + artifacts + provenance + docker fail-closed + chaos allow-list + wasm replay contract + mutation gate + govern checks)
    forge_router.py = Token Factory cascade (cache -> Super-120B -> reasoning-high, budget veto enforced in loop, offline bypass)
    forge_agents.py = 15-role swarm (byzantine merge, auction, quality debate + oracle tie-break) + planning (real UCB1 MCTS/scored ToT/decidable goal, 3-window spin) + cognition
    forge_obs.py = observability (spans, lineage, cost/carbon dashboard, audit export)
    forge_govern.py = governance (OPA deny, secret scan, HALT=1 kill-switch)
    forge_consolidate.py = sleep cycle (ledger->skills + dreams + vacuum + Merkle root)
    forge_const.py = shared constants (BACKOFF, timeouts, model, code-block pattern — single source)
    forge_system_prompt.xml = behavioral spec
    memory.md = episodic log, append only
    skills.md = registry projection (regenerated via forge_skills.projection_sync)
    life.md = autobiographical 1-line/task
    tests/test_harness.py = 9 offline tests, no API key needed
    tests/test_v2.py = 6 offline module tests
    tests/test_omega.py = 10 offline Omega tests (chain, tiers, genome, gates, mesh, economy, swarm, loop)
    tests/test_hardening.py = 7 offline hardening tests (traversal, AST govern, budget veto, scrub)
    tests/test_phase2.py = 17 offline Phase 2 tests (mesh contracts incl. replay, UCB1/ToT/debate determinism, vector fallback, gates, traversal residuals, void-output gate)
    tests/test_offline_cov.py = 8 offline coverage tests (mocked router cascade/cache/retry/budget, legacy loop paths, farm caps)
    examples/demo_task.py = sandbox proof
