# Forge - Hackathon Submission

## What it is
Self improving coding agent on Nemotron via Nebius Token Factory. Writes code, runs it in sandbox, fixes it, remembers what worked.

## Quickstart
pip install -r requirements.txt
Set NEBIUS_API_KEY in env, see .env.example
python forge.py --task write fib 10 to out.txt and print it
python forge_loop.py --task write fib 10 to out.txt and print it
python forge_loop.py --run-file examples/demo_task.py
python forge_loop.py --task demo --offline
python -m pytest tests/ -v

## Verification
49 tests green offline, no key needed
py_compile clean on all modules
fib demo-ok on both harnesses
chain verify ok, merkle root stable
govern True halt False
coverage 76 percent total (threshold 70 pass), uncovered paths need live key

## Token Factory proof
Base URL https api.tokenfactory.nebius.com v1
Model nvidia nemotron-3-super-120b-a12b
Reasoning model same family with high suffix after attempt 3
Client OpenAI compatible, no silent fallback
Cache sha256, retry 429 5xx only, budget veto enforced

## Architecture map
L0 identity plus time, L1 9 tier memory, L2 skill genome, L3 15 role swarm
L4 planning engine, L5 cognition, L6 sandbox mesh, L7 cascade plus economy
L8 eval fortress, L9 observability plus governance
L10 to L17 foundations only, deferred honestly, see ARCHITECTURE.md

## Limits
Local farm isolation is simulated, real isolation needs FORGE_DOCKER equals 1
Memory CPU caps enforced only in docker profile, timeout only locally
Vector backends faiss chroma are interfaces, file mirror is default
Live key smoke needs NEBIUS_API_KEY from user, not run offline

## Judging notes
Working software over prose, terse concrete output
Every claim re verified fresh, caches cleaned
See ARCHITECTURE.md plus README.md plus memory.md for history
