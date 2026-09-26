"""Offline coverage lifts: mocked router cascade + legacy loop paths.
All offline, no API key, hermetic (tmp dirs, mocked client)."""
import os
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["FORGE_FAST_TEST"] = "1"
import forge
import forge_router as R


def _fake_client(contents, models=None, fail_first=None):
    """Fake OpenAI client: contents dequeued per create() call."""
    state = {"n": 0}

    def _create(model=None, messages=None):
        if models is not None:
            models.append(model)
        if fail_first and state["n"] == 0:
            state["n"] += 1
            raise Exception("503 overloaded, try again")
        state["n"] += 1
        text = contents[min(state["n"] - 1, len(contents) - 1)]
        msg = types.SimpleNamespace(content=text)
        choice = types.SimpleNamespace(message=msg)
        usage = types.SimpleNamespace(prompt_tokens=3, completion_tokens=5)
        return types.SimpleNamespace(choices=[choice], usage=usage)

    comp = types.SimpleNamespace(create=_create)
    chat = types.SimpleNamespace(completions=comp)
    return types.SimpleNamespace(chat=chat)


def test_router_call_cascade_and_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(R, "COST_LOG", tmp_path / "cost.jsonl")
    monkeypatch.setenv("FORGE_CACHE", "1")
    client = _fake_client(["```python\nprint(1)\n```"])
    monkeypatch.setattr(R, "get_client", lambda: client)
    out = R.call_cascade("t", "s", "", attempt=1)
    assert "print(1)" in out["content"] and out["cached"] is False
    out2 = R.call_cascade("t", "s", "", attempt=1)
    assert out2["cached"] is True  # second identical call hits cache
    models = []
    client2 = _fake_client(["```python\nprint(2)\n```"], models=models)
    monkeypatch.setattr(R, "get_client", lambda: client2)
    out3 = R.call_cascade("other", "s", "", attempt=4)
    assert out3["system2"] is True and models and models[0] == R.MODEL_REASONING


def test_router_retry_then_success(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(R, "COST_LOG", tmp_path / "cost.jsonl")
    client = _fake_client(["hi"], fail_first=True)
    monkeypatch.setattr(R, "get_client", lambda: client)
    text, hit = R.call("t topography", "s", model=R.MODEL_DEFAULT, max_retries=2)
    assert text == "hi" and hit is False


def test_router_budget_cache_evict_and_bypass(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cache")
    for i in range(105):
        R.cache_put(f"k{i:04d}", {"content": "v"})
    left = list((tmp_path / "cache").glob("*.json"))
    assert len(left) <= 100 and (tmp_path / "cache" / "k0104.json").exists()
    assert R.cache_get("no-such-key") is None
    ok, _ = R.budget_check(prompt_tokens=1)
    assert ok is True
    ok, msg = R.budget_check(prompt_tokens=10**9)
    assert ok is False and "token budget" in msg
    monkeypatch.setenv("FORGE_OFFLINE", "1")
    assert R.offline_bypass() is True
    monkeypatch.delenv("FORGE_OFFLINE")
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    assert R.offline_bypass() is True


def test_router_log_cost_redacts(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "COST_LOG", tmp_path / "cost.jsonl")
    usage = types.SimpleNamespace(prompt_tokens=10, completion_tokens=20)
    R.log_cost("task hf_abcdefghijklmnop tail", usage)
    R.log_cost("plain", None)
    body = (tmp_path / "cost.jsonl").read_text(encoding="utf-8")
    import forge_obs as O
    assert "hf_abcdefghijklmnop" not in body and O.dashboard()["calls"] >= 0


def _run_legacy(monkeypatch, tmp_path, reply):
    import forge as F
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(F, "get_client", lambda: _fake_client([reply]))
    return F.run_task_loop("write fib-ish demo with done criteria exact",
                           work_file="sandbox_task.py")


def test_legacy_loop_success(monkeypatch, tmp_path):
    out = _run_legacy(monkeypatch, tmp_path, "```python\nprint('ok-legacy')\n```")
    assert out["status"] == "success" and "ok-legacy" in out["output"]


def test_legacy_loop_needs_code_blocked_failed(monkeypatch, tmp_path):
    out = _run_legacy(monkeypatch, tmp_path, "no code here, just prose")
    assert out["status"] == "needs-code"
    out = _run_legacy(monkeypatch, tmp_path, "```python\nimport os\n```")
    assert out["status"] == "blocked"
    big = "```python\nx='" + "y" * 200_001 + "'\n```"
    out = _run_legacy(monkeypatch, tmp_path, big)
    assert out["status"] == "blocked" and "too large" in str(out.get("reasons"))
    out = _run_legacy(monkeypatch, tmp_path, "```python\nraise ValueError('x')\n```")
    assert out["status"] == "failed" and out["attempts"] == 5


def test_router_client_and_corrupt_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cache")
    (tmp_path / "cache").mkdir(parents=True, exist_ok=True)
    (tmp_path / "cache" / "bad.json").write_text("{not json", encoding="utf-8")
    assert R.cache_get("bad") is None
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    monkeypatch.delenv("FORGE_OFFLINE", raising=False)
    try:
        R.get_client()
        assert False, "missing key must raise"
    except RuntimeError:
        pass
    import forge_loop as L
    monkeypatch.setenv("FORGE_OFFLINE", "1")
    try:
        L.default_provider("t", "s", "", 1)
        assert False, "offline provider must raise"
    except RuntimeError:
        pass


def test_execute_farm_caps():
    import pytest as _pytest
    import forge_sandbox as SB
    with _pytest.raises(ValueError):
        SB.execute_farm("x=" + "1" * 200_001)
    r = SB.execute_farm("print('cap-ok')")
    assert r.exit == 0 and "cap-ok" in r.stdout
    assert forge.extract_python_blocks("a ```py\nprint(1)\n``` b") == ["print(1)"]
    assert forge.extract_python_blocks("bare ```\nprint(2)\n``` tail") == ["print(2)"]
