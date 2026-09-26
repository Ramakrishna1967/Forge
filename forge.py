"""Forge — self-improving coding agent harness (Nebius x NVIDIA hackathon).

Implements the behavioral spec: Recall -> Plan -> Write -> Run -> Observe
-> Fix-or-Finish (max 5) -> Learn, on Nemotron via Nebius Token Factory.
"""
from __future__ import annotations
import argparse
import os  # used by get_client (NEBIUS_API_KEY)
import subprocess
import sys
from pathlib import Path
from forge_const import (  # single source; re-exported for compat
    BASE_URL_DEFAULT,
    CODE_BLOCK_RE,  # noqa: F401 re-exported for compat (canonical: forge_const)
    HISTORY_TAIL,
    MAX_CODE_BYTES,
    MAX_FIX_ATTEMPTS,
    MODEL_DEFAULT,
    SANDBOX_TIMEOUT,
    extract_python_blocks as _extract_blocks,
)

BASE_DIR = Path(__file__).resolve().parent
MEMORY_PATH = BASE_DIR / "memory.md"
SKILLS_PATH = BASE_DIR / "skills.md"
PROMPT_PATH = BASE_DIR / "forge_system_prompt.xml"


def read_memory(mem_path: Path = MEMORY_PATH, skills_path: Path = SKILLS_PATH):
    """Recall step: load durable state. Missing files -> empty string (fresh agent)."""
    mem = mem_path.read_text(encoding="utf-8") if mem_path.exists() else ""
    skills = skills_path.read_text(encoding="utf-8") if skills_path.exists() else ""
    return mem, skills


def load_system_prompt(path: Path = PROMPT_PATH) -> str:
    if not path.exists():
        raise FileNotFoundError(f"system prompt not found: {path}")
    return path.read_text(encoding="utf-8")


def get_client():
    """Nemotron via Token Factory only — no silent fallback."""
    try:
        from openai import OpenAI
    except ImportError as e:
        raise RuntimeError("missing dependency: pip install -r requirements.txt (needs openai)") from e
    api_key = os.environ.get("NEBIUS_API_KEY", "")
    if not api_key:
        raise RuntimeError("NEBIUS_API_KEY env var is not set (see .env.example)")
    return OpenAI(base_url=BASE_URL_DEFAULT, api_key=api_key)


def build_messages(task: str, mem: str, skills: str, system_prompt: str, history: str = ""):
    user_block = f"memory.md:\n{mem}\n\nskills.md:\n{skills}\n\nTask:\n{task}"
    if history:
        user_block += f"\n\nPrevious sandbox feedback (fix loop):\n{history}"
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_block},
    ]


def run_task(task_description: str, model: str = MODEL_DEFAULT) -> str:
    """Single-shot call (used by loop below)."""
    mem, skills = read_memory()
    system_prompt = load_system_prompt()
    client = get_client()
    messages = build_messages(task_description, mem, skills, system_prompt)
    resp = client.chat.completions.create(model=model, messages=messages)
    return resp.choices[0].message.content


def extract_python_blocks(text: str) -> list[str]:
    return _extract_blocks(text)  # compat wrapper: canonical impl lives in forge_const


def execute_sandboxed(code_path: str | Path, timeout: int = SANDBOX_TIMEOUT):
    """Run step: execute a python file, return CompletedProcess-like result."""
    p = Path(code_path)
    if not p.exists():
        raise FileNotFoundError(str(p))
    # sys.executable works on Windows + Linux (avoids python3 vs python alias bug).
    # -I + scrubbed env match the Omega farm (forge_sandbox.execute_farm).
    from forge_sandbox import _scrub_env
    return subprocess.run(
        [sys.executable, "-I", str(p)], capture_output=True, text=True,
        timeout=timeout, env=_scrub_env(),
    )


def append_file(path: str | Path, text: str) -> None:
    p = Path(path)
    with p.open("a", encoding="utf-8") as f:
        f.write("\n" + text.strip() + "\n")


def _contain_work_file(work_file: str | Path) -> Path:
    """work_file must resolve inside cwd (blocks --file ../../evil.py writes)."""
    p = (Path.cwd() / str(work_file)).resolve()
    if p != Path.cwd().resolve() and Path.cwd().resolve() not in p.parents:
        raise ValueError(f"work_file escapes cwd: {work_file!r}")
    return p


def run_task_loop(task: str, work_file: str | Path = "sandbox_task.py", model: str = MODEL_DEFAULT) -> dict:
    """Full core loop with up to MAX_FIX_ATTEMPTS sandbox round-trips."""
    from forge_govern import govern
    mem, skills = read_memory()
    system_prompt = load_system_prompt()
    client = get_client()
    target = _contain_work_file(work_file)
    history = ""
    last_output = ""
    for attempt in range(1, MAX_FIX_ATTEMPTS + 1):
        messages = build_messages(task, mem, skills, system_prompt, history)
        resp = client.chat.completions.create(model=model, messages=messages)
        content = resp.choices[0].message.content
        blocks = extract_python_blocks(content)
        if not blocks:
            # No code to run — ambiguous spec counts as needing clarification
            return {"status": "needs-code", "attempts": attempt, "response": content}
        if len(blocks[0].encode()) > MAX_CODE_BYTES:
            return {"status": "blocked", "attempts": attempt, "response": content,
                    "reasons": [f"code too large ({len(blocks[0].encode())}>{MAX_CODE_BYTES} bytes)"]}
        ok, reasons = govern(blocks[0])
        if not ok:
            return {"status": "blocked", "attempts": attempt, "response": content,
                    "reasons": reasons}
        target.write_text(blocks[0], encoding="utf-8")
        try:
            result = execute_sandboxed(target)
        except subprocess.TimeoutExpired as e:
            history += f"\n[attempt {attempt}] TIMEOUT after {SANDBOX_TIMEOUT}s: {e}\n"
            continue
        last_output = f"exit={result.returncode}\n--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
        if result.returncode == 0:
            return {"status": "success", "attempts": attempt, "response": content, "output": last_output}
        history = (history + f"\n[attempt {attempt}] FAILED:\n{last_output}\n"
                   f"Diagnose root cause (not symptom) and patch.\n")[-HISTORY_TAIL:]
    return {"status": "failed", "attempts": MAX_FIX_ATTEMPTS, "response": "fix budget exhausted", "output": last_output}


def main():
    ap = argparse.ArgumentParser(description="Forge harness")
    ap.add_argument("--task", required=False, default="", help="task description")
    ap.add_argument("--file", required=False, default="sandbox_task.py", help="sandbox work file")
    ap.add_argument("--run-file", required=False, default="", help="directly execute a file in sandbox (no LLM call)")
    ap.add_argument("--model", required=False, default=MODEL_DEFAULT)
    args = ap.parse_args()
    if args.run_file:
        from forge_govern import govern as _govern
        try:
            _content = Path(args.run_file).read_text(encoding="utf-8")
        except OSError as e:
            print(f"blocked: cannot read --run-file: {e}")
            sys.exit(2)
        _ok, _reasons = _govern(_content)
        if not _ok:
            print(f"blocked: govern denied --run-file: {'; '.join(_reasons)}")
            sys.exit(2)
        r = execute_sandboxed(args.run_file)
        print(f"exit={r.returncode}\n--- stdout ---\n{r.stdout}\n--- stderr ---\n{r.stderr}")
        sys.exit(r.returncode)
    if not args.task:
        ap.error("--task is required unless --run-file is given")
    out = run_task_loop(args.task, work_file=args.file, model=args.model)
    print(out)


if __name__ == "__main__":
    main()
