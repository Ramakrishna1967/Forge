# Forge — Self-Improving Coding Agent

[![tests](https://img.shields.io/badge/tests-57_passed-brightgreen)](tests/)
[![coverage](https://img.shields.io/badge/coverage-76%25-yellowgreen)](pyproject.toml)
[![lint](https://img.shields.io/badge/ruff-clean-brightgreen)](pyproject.toml)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![python](https://img.shields.io/badge/python-%3E%3D3.10-blue)](pyproject.toml)

Built for the **Nebius x NVIDIA hackathon**. Forge runs on
`nvidia/nemotron-3-super-120b-a12b` via the Nebius Token Factory. It writes
code, executes it in an isolated sandbox, diagnoses real output, fixes
failures, and remembers what worked — a full Recall → Plan → Write → Run →
Observe → Fix → Learn loop with hash-chained memory and policy governance.

No local model, no GPU, no Docker required. The default path is a remote API
call plus a local `sys.executable -I` sandbox; everything else degrades
honestly to simulated/offline stubs that say so.

## Features

- **Agentic coding loop** — up to 5 fix attempts per task with G0–G4 quality
  gates, backoff (`0/5/15/45/120s`), spinning detection, and a void-output
  mutation gate.
- **9-tier memory** — sensory ring, working context, hash-chained episodic
  ledger with Merkle root, autobiographical `life.md`, YAML semantic registry
  (tombstoned, max 100), Bayesian procedural rates, prospective queue,
  pinned flashbulb footguns, plus graph and file-backed vector mirrors
  (never authoritative).
- **Skill Genome** — versioned skills with fitness scoring
  (`lift × uses − tokens − failures × 10`), conflict resolution, 10-task fuzz
  gate, and human-approved market staging.
- **15-role swarm + planners** — orchestrator, planner, coder, critic, tester,
  security, red-teamer, oracle and more, with 2/3 Byzantine merge, coder
  auction, quality debate, real UCB1 MCTS, scored Tree-of-Thought, and
  GIVEN/WHEN/THEN decidable goals.
- **Sandbox mesh** — isolated tmp workdir, scrubbed env, net-off, 30s
  timeout, provenance hashes, per-attempt artifacts, deterministic-replay
  contract, chaos allow-list, Docker opt-in (`--network none`).
- **LLM economy** — cache → Super-120B → reasoning-high cascade, SHA-256
  prompt cache (LRU-capped), token/wall-clock budget vetoes, cost + CO₂
  ledger. Fully offline-capable via `--run-file` / `FORGE_OFFLINE=1`.
- **Governance** — substring + AST deny lists (single-sourced), secret
  scanning, traversal guards, `HALT=1` kill-switch, redacted audit exports.
- **Light mode** — one-switch low-RAM profile for 8 GB laptops (see below).

## Quickstart

```bat
pip install -r requirements.txt
set NEBIUS_API_KEY=your_key_here
python forge_loop.py --task "write fib(10) to out.txt and print it"
```

No key? Run the offline proof — no network, no model calls:

```bat
python forge_loop.py --run-file examples/demo_task.py
python -m pytest tests/ -v
```

Expected: `exit=0 … demo-ok` and `57 passed`.

## Usage

```bat
:: Omega loop (recommended)
python forge_loop.py --task "<file, behavior, done-criteria in one line>"
python forge_loop.py --task "..." --offline        :: verify without LLM calls
python forge_loop.py --run-file examples/demo_task.py

:: Compat harness (v1 loop, governed)
python forge.py --task "..."
python forge.py --run-file examples/demo_task.py

:: Maintenance
make test        :: compile + full suite
make test-light  :: quiet low-RAM suite
make demo        :: both-harness fib demo
make prune       :: trim router cache + archive weak skills
make cov         :: coverage report (needs RAM headroom)
make clean       :: drop caches
```

## Configuration

| Variable | Default | Effect |
|---|---|---|
| `NEBIUS_API_KEY` | — | Required for live LLM calls; without it the loop runs offline paths only |
| `FORGE_LIGHT` | `1` | Low-RAM profile: single-exec replay, Docker disabled, capped tails/cache (set `0` for full mesh) |
| `FORGE_OFFLINE` | `0` | `1` disables all LLM calls |
| `FORGE_FAST_TEST` | `0` | `1` skips retry sleeps (used by the test suite) |
| `FORGE_TIMEOUT` | `30` | Sandbox seconds per attempt |
| `FORGE_BUDGET_TOKENS` | `200000` | Economist veto ceiling |
| `FORGE_BUDGET_WALL_S` | `600` | Wall-clock veto ceiling |
| `FORGE_VECTOR` | `file` | `faiss`/`chroma` opt in to native backends (needs `pip install forge[vector]`) |
| `FORGE_DOCKER` | `0` | `1` enables real container execution |
| `FORGE_CACHE` | `1` | `0` disables the prompt cache |
| `HALT` | `0` | `1` engages the kill-switch, all runs abort |

## Architecture

```
Recall (memory+skills) → Plan (G1) → Write (LLM cascade)
  → Govern (deny/scan) → Run (sandbox farm) → Observe (output+artifacts)
  → Fix (≤5, backoff, spin/mutation gates) → Learn (ledger/skills)
```

- `forge_loop.py` — Omega wiring: identity, gates, budget, artifacts.
- `forge_memory.py` — 9-tier durable state, chain verify, Merkle root.
- `forge_skills.py` — Skill Genome evolution and market staging.
- `forge_agents.py` — swarm votes, auction, debate, MCTS/ToT, cognition ledger.
- `forge_sandbox.py` — farm, provenance, replay, chaos, mutation, docker stub.
- `forge_router.py` — Token Factory client, cache, cascade, budgets.
- `forge_obs.py` — spans, lineage, cost/carbon dashboard, audit export.
- `forge_govern.py` — canonical deny lists, AST guard, secret scan, HALT.
- `forge_consolidate.py` — sleep cycle: promote, dream, vacuum.
- `forge_const.py` — single source for shared constants and caps.
- `forge.py` — backward-compatible v1 harness.
- Full spec: [`ARCHITECTURE.md`](ARCHITECTURE.md). Submission notes: [`SUBMISSION.md`](SUBMISSION.md).

## Verification status

| Gate | Result |
|---|---|
| Tests | 57 passed (9 harness + 6 v2 + 10 omega + 7 hardening + 17 phase2 + 8 offline-cov) |
| Lint | `ruff check` clean |
| Coverage | 76% (gate: 70; uncovered lines need a live key) |
| Security | `pip-audit` 0 vulnerabilities; secret rescan = fixture self-matches only |
| E2E | `demo-ok` on both harnesses |
| Ledger | hash chain `(True, -1)`, Merkle stable, zero test pollution |

## Limits (honest)

- Local sandbox isolation is **simulated** (same OS user, timeout-only);
  real containment requires `FORGE_DOCKER=1`. Never run untrusted LLM output
  without it.
- `faiss`/`chroma` are interfaces; the default vector store is a capped file
  mirror.
- L10–L17 (multiverse, federation, proofs) exist as replay/market/ledger
  foundations only.
- Live-model verification needs `NEBIUS_API_KEY`.

## License

MIT — see [LICENSE](LICENSE).
