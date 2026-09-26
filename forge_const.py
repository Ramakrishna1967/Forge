"""Forge shared constants: single source for cross-module values.

Import these instead of redefining: BACKOFF schedule, sandbox timeout,
Nemotron model defaults, code-block pattern. Re-exported by owner
modules (forge_agents.BACKOFF, forge_router.BACKOFF, forge.CODE_BLOCK_RE)
for backward compat.
"""
from __future__ import annotations
import os
import re

BACKOFF = [0, 5, 15, 45, 120]
SANDBOX_TIMEOUT = int(os.environ.get("FORGE_TIMEOUT", "30"))
MODEL_DEFAULT = os.environ.get("FORGE_MODEL", "nvidia/nemotron-3-super-120b-a12b")
BASE_URL_DEFAULT = os.environ.get("FORGE_BASE_URL", "https://api.tokenfactory.nebius.com/v1")
BASE_URL = BASE_URL_DEFAULT  # router alias
CODE_BLOCK_RE = re.compile(r"```(?:python|py)?\s*\n?(.*?)```", re.DOTALL | re.IGNORECASE)
MAX_FIX_ATTEMPTS = 5
MAX_ATTEMPTS = MAX_FIX_ATTEMPTS  # agent-loop alias
# Fail-closed caps (DoS/cost guards): oversized LLM code is blocked, giant
# outputs truncated before SandboxResult, history tail-capped per attempt.
MAX_CODE_BYTES = 200_000
MAX_OUTPUT_BYTES = 1_000_000
HISTORY_TAIL = 4000


def extract_python_blocks(text: str) -> list[str]:
    """Single-source fenced-block extractor (forge + forge_loop delegate here)."""
    return [b.strip() for b in CODE_BLOCK_RE.findall(text or "") if b.strip()]
# Light mode (8GB-laptop defaults): halves subprocess work, caps cache tails.
# ON by default; set FORGE_LIGHT=0 to restore full mesh behavior.
LIGHT = os.environ.get("FORGE_LIGHT", "1") == "1"
LIGHT_STDOUT_TAIL = 500
FULL_STDOUT_TAIL = 2000
STDOUT_TAIL = LIGHT_STDOUT_TAIL if LIGHT else FULL_STDOUT_TAIL
LIGHT_CACHE_MAX = 100
LIGHT_VECTOR_MAX = 200
