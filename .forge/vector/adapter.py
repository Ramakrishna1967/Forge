"""Vector adapter: file-backed default, optional faiss/chroma, never authoritative.

Read-through mirror only: episodic ledger + skill registry stay source of truth.
"""
from __future__ import annotations


def _mem():
    import forge_memory as _M
    return _M


class VectorAdapter:
    """File-backed vector mirror. Plug faiss/chroma via try-import when installed."""

    backend = "file"

    def __init__(self) -> None:
        import os
        want = os.environ.get("FORGE_VECTOR", "file")  # file default (8GB safe)
        if want == "faiss":
            try:
                import faiss  # noqa: F401 type: ignore
                self.backend = "faiss"
            except Exception:
                self.backend = "file"
        elif want == "chroma":
            try:
                import chromadb  # noqa: F401 type: ignore
                self.backend = "chroma"
            except Exception:
                self.backend = "file"
        else:
            self.backend = "file"

    def upsert(self, _id: str, _text: str, _meta: dict | None = None) -> None:
        if self.backend == "file":
            _mem().vector_mirror_put(_id, _text)
            return
        raise NotImplementedError(f"backend {self.backend}: wire native upsert here")

    def query(self, _text: str, _k: int = 5) -> list[dict]:
        if self.backend == "file":
            hit = _mem().vector_mirror_get(_text)
            return [{"id": _text, "text": hit}] if hit is not None else []
        raise NotImplementedError(f"backend {self.backend}: wire native query here")
