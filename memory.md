# Forge Memory — episodic log (append-only, most recent last)

## [init] — [success]
- what was tried: bootstrapped Forge harness in empty repo (D:\NVDIA_hackthhon)
- root cause N/A (greenfield init)
- what fixed it: created forge.py + forge_system_prompt.xml + memory.md/skills.md + tests

## [forge bootstrap orchestration] — [success]
- what was tried: multi-agent orchestration (planner, architect, tdd-guide, reviewers) to build Forge harness from empty dir
- root cause N/A: greenfield build, 9 offline tests passed, sandbox demo verified via forge.py --run-file
- what fixed it: sys.executable sandbox (not python3 alias), single-quoted PS strings for file writes, offline-first tests

## [system architecture doc] — [success]
- what was tried: audited forge.py vs spec, ran py_compile + pytest + --run-file, wrote ARCHITECTURE.md, cleaned caches
- root cause N/A: arch matched spec, 9 passed + demo-ok re-verified
- what fixed it: documented 6 components + data flow; removed __pycache__/.pytest_cache regen noise

## [v4 omega arch locked] — [success]
- what was tried: 3-subagent fan-out (memory/skills, orchestration, sandbox/router) then v3/v4 over-engineer to Hermes Omega, design-only per user halt on code
- root cause N/A: user rejected v1/v2 as too simple, demanded max complexity
- what fixed it: locked 17-layer ARCHITECTURE.md (9-tier memory, 15-role swarm, sandbox mesh, cascade, multiverse, federation, proofs); no code writes after halt

## [v4 omega implementation] — [success]
- what was tried: phased multi-agent orchestration to implement locked ARCHITECTURE.md (memory/skills/sandbox/router/swarm/obs/govern/loop tracks, then eval fortress, then review/docs)
- root cause N/A: greenfield build on thin v2 stubs; 1 typo (PROCEDEURAL) caught by new omega tests
- what fixed it: backward-compat extensions (ROLES 7 kept, SWARM_ROLES 15 added), hash-chained ledger + Merkle root, Skill Genome + fuzz gate, sandbox artifacts + provenance, cascade + budget veto, byzantine/auction/debate, spans + HALT switch, forge_loop wiring; 25 passed + fib demo-ok on both harnesses

## [refine everything, behavior-neutral] — [success]
- what was tried: orch-refine-code on all modules; refactor-cleaner audit found govern/hash/agent dups are tested or digest-sensitive so kept; removed only zero-effect dead code in 4 small steps with pytest after each
- root cause N/A: dead code was uncalled+untested (asdict import, DREAMS/SLEEP_LOGS consts, working_load, confidence_decay dup)
- what fixed it: 4 deletions, code-reviewer PASS, 25 passed + demo-ok re-verified, caches cleaned (no commit: not requested)

## [code-review BLOCK triage + harden] — [success]
- what was tried: triaged 5 HIGHs (all confirmed) + 6 MEDIUMs; fixed in batches with pytest after each: forge.py -I+scrub, safe_id traversal guards (artifacts + registry), additive AST guard in govern + sandbox, budget_check wired into run_loop, requirements pinned (openai==3.19.2 pytest==9.1.1 pyyaml==6.0.3), corrupt-state backup, docker unlink, PYTHONPATH dropped, gc via _yaml_read; added tests/test_hardening.py (7 tests)
- root cause N/A (proactive hardening, no incident): compat shim bypassed farm flags, ids unsanitized, substring-only govern, unenforced budget, unpinned deps
- what fixed it: 32 passed + demo-ok both harnesses; secret rescan = 2 pattern-definition self-matches only (deny-list literal + test fixture), no real credentials

## [phase 2 mesh+cognition+vector] — [success]
- what was tried: executed orchestration plan tracks 1-3 + eval fortress: wasm_replay contract, chaos allow-list, mutation_score wired to G2, real UCB1 (c=1.414) + scored ToT + quality debate + oracle_break_tie + 3-window spinning, vector file backend, dream proof artifacts; 1 test assertion updated stub->real UCB1 (documented in-test); security FAIL re-triage fixed 4 traversal residuals (dream id hash-fallback, stage_for_market + audit_export guards, attempt int-coerce) + substring cover for AST-only tokens; added tests/test_phase2.py (13 tests)
- root cause N/A: stubs intentionally shipped in prior phase; mcts visits persistence skipped (no caller in loop, would be dead code)
- what fixed it: 45 passed + demo-ok both harnesses; code-reviewer PASS; security residuals closed; docs synced (ARCHITECTURE 45, README tracks, life.md); test dream fixtures cleaned

## [review2 BLOCK triage + harden] — [success]
- what was tried: triaged 3 CRITICALs + 8 HIGHs + MEDIUM/LOWs in 4 batches with pytest after each: legacy forge.py loop now governed + cwd-contained; AST Name(open)/Attribute guard + KEY whitespace-normalize + repo-state/env targeted denies (isolation honestly documented as simulated, docker-only for real); run_loop helpers extracted (_fetch_code/_mutation_gate/_finish_success), all provider exceptions -> needs-code, mutation gate requires non-empty + 2 mutants, tmp workdir auto-cleaned with limits honestly marked aspirational; tar symlink filter, secret_scan read-only exemption, YAML fail-loud (fallback deleted), log redaction, test path portable, placeholder + requires-python fixed; added 3 gate tests
- root cause N/A (proactive, no incident): ungoverned legacy loop, deny-list gaps, swallowed provider errors, void-output gaming, tmp leak, fragile parsers
- what fixed it: 48 passed + demo-ok both harnesses; rescan = same 2 known self-matches, no real secrets; deferred honestly: OS-level containment, O(n) reads, config DRY, stderr warn-prints

## [all-phases completion sweep] — [success]
- what was tried: orchestration recon + parallel gates (tests, e2e, security, quality) + synthesis; independently re-verified every claim fresh
- root cause N/A: only drift was ARCHITECTURE.md verification block (already 48-accurate), zero cache residue
- what fixed it: py_compile clean (10 modules), 48 passed, demo-ok both harnesses, govern (True,[]) halt False; L10-L17 stays honestly deferred; caches cleaned

## [4-phases via subagents] — [success]
- what was tried: Phase 1 planner (scope lock, gaps NONE) → Phase 2 four parallel subagents (mesh/planning/memory tracks verified, e2e baseline) → Phase 3 code+security review → Phase 4 doc-updater + synthesis gate
- root cause N/A: tree already complete; tracks changed NONE; security PASS; code BLOCK items adjudicated as previously-accepted (run_loop helpers already extracted, layered-govern dups test-pinned)
- what fixed it: compile clean, 48 passed, demo-ok both harnesses; docs verified NONE-stale; caches cleaned

## [complete-all open items] — [success]
- what was tried: closed every completable review item in gated batches: forge_const.py single source (BACKOFF/timeout/model/pattern re-exported, pinned tests intact) + unused re import dropped; run_loop split via _run_attempt; O(n)->O(tail) ledger reads (deque); stderr warns (identity/cache); replay_attempt rewind primitive; traversal/AST/budget work from before untouched and still green
- root cause N/A: remaining BLOCK items were accepted trade-offs, now completed except honestly-refused (below)
- what fixed it: 49 passed + demo-ok both harnesses; rescan = same 2 self-matches; REFUSED with reasons: OS cgroup/Firecracker isolation (needs infra), federation/ZK (needs network), live-key smoke (needs NEBIUS_API_KEY from user), git commit (not explicitly requested)

## [test-isolation completion sweep] — [success]
- what was tried: orchestration recon plus isolation fix (phase2 loop tests, omega wiring PROCEDURAL, hardening budget veto) plus parallel e2e and security gates plus docs and packaging synthesis
- root cause: loop tests patched only SB.RUNS, so each pytest run appended to real episodic ledger, life.md, runs ledgers (29 identical t-p2 lines, plus 1 decision per run)
- what fixed it: full-path isolation to tmp_path (MEM EPISODIC LIFE WORKING PROCEDURAL SEMANTIC_DIR plus OBS LEDGER TRACES LINEAGE plus A.DECISION_LEDGER); suite re-run twice with zero ledger growth; life.md dupes collapsed to counted line; ARCHITECTURE verification 48 to 49 (17 phase2); .gitignore added; demo-ok both harnesses; rescan equals known self-matches only; chain verify ok

## [whole project completion sweep] - [success]
- what was tried: orchestration recon plus parallel gates plus packaging synthesis, 49 tests green, e2e both harnesses demo-ok, chain verify ok, coverage 80 percent, added pyproject Makefile Dockerfile CI LICENSE SUBMISSION, extended gitignore, git init no commit, caches cleaned
- root cause N-A: core already complete, gaps were submission scaffolding only, no code changes needed
- what fixed it: new scaffolding files plus docs, zero behavior change, 49 passed re verified after clean, merkle stable, govern True halt False

## [light mode for 8GB laptop] — [success]
- what was tried: cut RAM without changing behavior: FORGE_LIGHT=1 default (single-exec wasm replay, docker forced-skip, 500-line tails, router cache capped at 100 LRU, vector mirror capped at 200, graph/prospective/flashbulb/ledger streaming tails, sleep 50 recs/2 dreams, vector adapter file-only unless FORGE_VECTOR set); Makefile test-light/demo-light/prune; Dockerfile FORGE_LIGHT=1; README light section
- root cause N/A (8GB laptop cannot handle docker/faiss/coverage bursts; subprocess double-exec + unbounded cache/mirror were heaviest local RAM)
- what fixed it: 9 files edited (const/sandbox/router/memory/obs/consolidate/vector-adapter/Makefile/Dockerfile/README/requirements); COMPILE_OK, 49 passed light + 49 passed full, demo-light demo-ok, prune ok, ledgers 51/110 zero growth

## [lint fix sweep] — [success]
- what was tried: ruff 14 errors (F811 shadow, E402 x6, E702, F841 dead t0, F401 x4) fixed behavior-neutrally: BACKOFF-only import, noqa E402/F401, obs indent split, dead import drops
- root cause N/A (style/import hygiene, no logic bug)
- what fixed it: ruff 0 errors, COMPILE_OK, 49 passed, zero ledger growth

## [awesome-clean patch] — [success]
- what was tried: closed BLOCK items that were test-safe: govern canonical REPO_STATE_PATTERNS (pathlib/io.open repo-state bypass now blocked in BOTH govern paths, verified), extended KEY_PATTERNS (stripe/github/slack/google), getattr-obfuscation AST flag, sandbox single-source delegation (regex secret scan, no bare hf_ false positives), MAX_CODE_BYTES/HISTORY_TAIL caps, stdout truncation, atomic writes (working/yaml/mirror/agent/tick), CODE_BLOCK_RE py/no-lang/ignorecase, MAX_ATTEMPTS unshadowed, extract helper in const, CLI --run-file govern scan, Dockerfile USER forge + HEALTHCHECK, .gitignore runtime ignores (.forge subdirs + runs/, adapter.py stays tracked)
- root cause N/A (hardening pass, no incident; previous bypass verified live before fix)
- what fixed it: ruff 0, COMPILE_OK, 49 passed light + full, demo-ok both, ledgers 51/110 zero growth; DECLINED with reasons: docker-mandate (breaks offline/tests + no-docker 8GB laptop), open()-allowlist (breaks hardening pins), tz reformat (format stability), bare-except->logging (pinned silent-None + spam risk), real semantic mutants (test-pinned reason string), pip-audit (not installed)

## [orchestrate patch-and-complete] � [success]
- what was tried: full orchestration (planner recon + parallel tdd/code/security/architect gates + doc-updater synthesis); re-verified every claim fresh
- root cause N/A: code already complete (49 green, ruff clean, demos-ok both harnesses, chain True merkle c86cc6, govern True halt False); drift was docs/hygiene only
- what fixed it: SUBMISSION coverage 80->71 percent (threshold 70 pass, matches fresh cov), .gitignore added .ruff_cache/, caches cleaned (__pycache__/.pytest_cache/.ruff_cache/.coverage/vector __pycache__); ledger 51 zero growth confirms test isolation holds; git commit deferred (not explicitly requested)
