# Forge — Self-Improving Coding Agent

[![tests](https://img.shields.io/badge/tests-57_passed-brightgreen)](tests/)
[![coverage](https://img.shields.io/badge/coverage-76%25-yellowgreen)](pyproject.toml)
[![lint](https://img.shields.io/badge/ruff-clean-brightgreen)](pyproject.toml)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

## What is this

Forge is a coding agent built for the **Nebius x NVIDIA hackathon**. You give
it a task in one line; it writes the code, runs it, reads the real output,
fixes what failed, and remembers what worked for next time.

It runs on `nvidia/nemotron-3-super-120b-a12b` via the Nebius Token Factory —
no local model, no GPU, no Docker needed.

## How it works

One loop, seven steps:

```
Recall → Plan → Write → Run → Observe → Fix → Learn
```

1. **Recall** — loads past episodes and learned skills from memory.
2. **Plan** — scores the task against quality gates; ambiguous tasks are sent
   back with one clarifying question instead of guessed at.
3. **Write** — the model produces a single Python block.
4. **Run** — the block executes in an isolated sandbox (tmp workdir, scrubbed
   env, no network, 30s timeout). Nothing is trusted until it runs.
5. **Observe** — exit code and real stdout/stderr are captured with a
   provenance hash.
6. **Fix** — up to 5 attempts with backoff. Identical retries are detected
   as spinning and stopped; empty output is rejected as gaming.
7. **Learn** — successes and failures are appended to a hash-chained ledger
   and distilled into reusable skills.

Every step is governed: deny-lists plus AST checks block shell, network,
secrets, and repo-state writes before anything executes, and `HALT=1` stops
all runs instantly.

## Proof it works

No API key needed — the offline proof runs the full loop on this machine:

```bat
pip install -r requirements.txt
python forge_loop.py --run-file examples/demo_task.py
python -m pytest tests/ -v
```

Expected output:

```
exit=0
--- stdout ---
[0, 1, 1, 2, 3, 5, 8, 13, 21, 34]
demo-ok
...
57 passed
```

57 offline tests cover the loop, memory chain, skill genome, sandbox mesh,
swarm votes, planning, governance, and hardening — with `ruff` clean and
`pip-audit` reporting zero vulnerabilities.
