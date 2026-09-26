"""Forge governance (Omega L9): secret scan, OPA-style deny, HALT kill-switch.

Deny: shell=True, direct net dials, key-in-code. HALT=1 stops all runs.
Used by forge_loop before any sandbox execution. Offline, no dependencies.
"""
from __future__ import annotations
import ast
import os
import re

HALT_ENV = "HALT"

DENY_RULES = [
    ("shell=True", "shell execution denied (use sandbox farm, no shell=True)"),
    ("os.system(", "os.system denied"),
    ("subprocess.call(", "raw subprocess.call denied (use sandbox farm)"),
    ("socket.create_connection", "direct socket dial denied (net-off)"),
    ("__import__", "dynamic __import__ denied"),
    ("exec(", "exec() denied"),
    ("compile(", "compile() denied"),
    (".popen", ".popen denied"),
    ("execv", "execv denied"),
    ("execl", "execl denied"),
]

# Single source for repo-state/env deny substrings (forge_sandbox imports these;
# do not redefine deny lists elsewhere). Substring layer is a fast pre-filter;
# the AST guard below is authoritative for parseable code.
REPO_STATE_PATTERNS = [
    ("memory.md", "repo-state write denied: memory.md"),
    ("skills.md", "repo-state write denied: skills.md"),
    ("life.md", "repo-state write denied: life.md"),
    (".forge/", "repo-state write denied: .forge/"),
    ("os.environ", "env exfil denied: os.environ"),
    ("os.getenv", "env exfil denied: os.getenv"),
    ("getenv(", "env exfil denied: getenv("),
]

KEY_PATTERNS = [
    (re.compile(r"NEBIUS_API_KEY\s*=\s*['\"][^'\"]+['\"]"), "embedded NEBIUS_API_KEY"),
    (re.compile(r"hf_[A-Za-z0-9]{10,}"), "embedded HF token"),
    (re.compile(r"sk-(?:live|test)-[A-Za-z0-9]{10,}"), "embedded Stripe key"),
    (re.compile(r"sk-[A-Za-z0-9]{10,}"), "embedded secret key"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "embedded AWS key"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{10,}"), "embedded GitHub token"),
    (re.compile(r"xox[pbpa]-[A-Za-z0-9-]{10,}"), "embedded Slack token"),
    (re.compile(r"AIza[A-Za-z0-9_-]{10,}"), "embedded Google key"),
]


def halted() -> bool:
    return os.environ.get(HALT_ENV, "0") == "1"


def check_halt() -> None:
    if halted():
        raise SystemExit("HALT=1 kill-switch engaged — run aborted")


def opa_deny(code: str, allow_net: bool = False) -> list[str]:
    hits = [msg for pat, msg in DENY_RULES if pat in code]
    hits += [msg for pat, msg in REPO_STATE_PATTERNS if pat in code]
    if not allow_net and ("socket." in code or "urllib.request" in code):
        hits.append("network egress denied (net-off sandbox)")
    return hits


DENY_IMPORTS = {"os", "sys", "subprocess", "socket", "shutil", "pty"}
DENY_CALLS = {"eval", "exec", "compile", "__import__"}


DENY_ATTRS = {"system", "popen", "execv", "execl", "connect", "urlopen",
              "request", "getresponse"}


class _Guard(ast.NodeVisitor):
    def __init__(self) -> None:
        self.hits: list[str] = []

    def visit_Import(self, n: ast.Import) -> None:
        for a in n.names:
            if (a.name or "").split(".")[0] in DENY_IMPORTS:
                self.hits.append(f"denied import: {a.name}")
        self.generic_visit(n)

    def visit_ImportFrom(self, n: ast.ImportFrom) -> None:
        if (n.module or "").split(".")[0] in DENY_IMPORTS:
            self.hits.append(f"denied import-from: {n.module}")
        self.generic_visit(n)

    def visit_Name(self, n: ast.Name) -> None:
        if n.id == "open":
            self.hits.append("denied builtin: open() (sandbox has no file need)")
        self.generic_visit(n)

    def visit_Attribute(self, n: ast.Attribute) -> None:
        if n.attr in DENY_ATTRS:
            self.hits.append(f"denied attr: .{n.attr}")
        self.generic_visit(n)

    def visit_Call(self, n: ast.Call) -> None:
        f = n.func
        if isinstance(f, ast.Name) and f.id in DENY_CALLS:
            self.hits.append(f"denied call: {f.id}()")
        elif isinstance(f, ast.Attribute) and f.attr in ("system", "popen", "execv", "execl"):
            self.hits.append(f"denied call: .{f.attr}()")
        elif isinstance(f, ast.Name) and f.id == "getattr":
            for a in n.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str) \
                        and a.value in ("system", "popen", "execv", "execl",
                                        "__import__", "open", "eval", "exec"):
                    self.hits.append(f"denied getattr obfuscation: {a.value!r}")
                    break
        self.generic_visit(n)


def ast_denies(code: str) -> list[str]:
    """Additive AST guard. Unparseable code -> no AST verdict (substring rules still apply)."""
    try:
        tree = ast.parse(code)
    except Exception:
        return []
    g = _Guard()
    g.visit(tree)
    return g.hits


def secret_scan(code: str) -> list[str]:
    hits = []
    for rx, label in KEY_PATTERNS:
        if rx.search(code):
            hits.append(label)
    # whitespace-obfuscated assignment (NEBIUS_API_KEY =\n "sk-...") still blocked
    if not any("NEBIUS" in h for h in hits):
        norm = re.sub(r"\s+", "", code)
        if re.search(r"NEBIUS_API_KEY=['\"][^'\"]+['\"]", norm):
            hits.append("embedded NEBIUS_API_KEY (obfuscated)")
    return hits


def govern(code: str, allow_net: bool = False) -> tuple[bool, list[str]]:
    """Returns (ok, reasons). Fail-closed: any hit blocks execution."""
    check_halt()
    reasons = opa_deny(code, allow_net) + secret_scan(code) + ast_denies(code)
    return (not reasons), reasons
