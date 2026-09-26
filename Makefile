.PHONY: test test-light demo demo-light clean audit compile e2e cov prune

compile:
	python -m py_compile forge.py forge_loop.py forge_agents.py forge_memory.py forge_skills.py forge_sandbox.py forge_router.py forge_obs.py forge_govern.py forge_consolidate.py forge_const.py

test: compile
	python -m pytest tests/ -v

test-light: compile
	FORGE_LIGHT=1 FORGE_OFFLINE=1 FORGE_FAST_TEST=1 python -m pytest tests/ -q -p no:cacheprovider

demo-light:
	FORGE_LIGHT=1 FORGE_OFFLINE=1 python forge_loop.py --run-file examples/demo_task.py

prune:
	FORGE_LIGHT=1 python -c "import forge_consolidate as C; print(C.vacuum())"

cov:
	python -m pytest tests/ -q --cov=. --cov-report=term-missing

demo:
	python forge.py --run-file examples/demo_task.py
	python forge_loop.py --run-file examples/demo_task.py

e2e: compile demo
	python -m pytest tests/test_phase2.py tests/test_omega.py -q

audit: compile
	python -m pytest tests/test_hardening.py -q

clean:
	rm -rf __pycache__ .pytest_cache htmlcov .coverage coverage.xml
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
