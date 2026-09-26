
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import forge

def test_read_memory_returns_strings(tmp_path):
    m = tmp_path / "memory.md"
    s = tmp_path / "skills.md"
    m.write_text("mem!", encoding="utf-8")
    s.write_text("skill!", encoding="utf-8")
    mem, skills = forge.read_memory(m, s)
    assert mem == "mem!"
    assert skills == "skill!"

def test_read_memory_missing_files(tmp_path):
    mem, skills = forge.read_memory(tmp_path / "nope.md", tmp_path / "nope2.md")
    assert mem == ""
    assert skills == ""

def test_extract_python_blocks():
    txt = "hello"
    assert forge.extract_python_blocks(txt) == []

def test_extract_python_blocks_two():
    txt = "a ```python\nprint(1)\n``` b ```python\nprint(2)\n```"
    blocks = forge.extract_python_blocks(txt)
    assert blocks == ["print(1)", "print(2)"]


def test_execute_sandboxed_success(tmp_path):
    f = tmp_path / "ok.py"
    f.write_text("print(40 + 2)", encoding="utf-8")
    r = forge.execute_sandboxed(f)
    assert r.returncode == 0
    assert "42" in r.stdout

def test_execute_sandboxed_failure(tmp_path):
    f = tmp_path / "bad.py"
    f.write_text("raise ValueError(\"boom\")", encoding="utf-8")
    r = forge.execute_sandboxed(f)
    assert r.returncode != 0
    assert "boom" in r.stderr

def test_load_system_prompt():
    txt = forge.load_system_prompt()
    assert "Forge" in txt
    assert "Recall" in txt

def test_get_client_missing_key(monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    try:
        forge.get_client()
        raised = False
    except RuntimeError as e:
        raised = True
        assert "NEBIUS_API_KEY" in str(e)
    assert raised

def test_append_file(tmp_path):
    f = tmp_path / "a.md"
    f.write_text("head", encoding="utf-8")
    forge.append_file(f, "new entry")
    assert "new entry" in f.read_text(encoding="utf-8")
