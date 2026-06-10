"""Knowledge base ingestion with FAISS vector index and metadata tracking."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _kb_root() -> Path:
    root = Path(os.getenv("KNOWLEDGE_BASE_DIR", "knowledge_base"))
    root.mkdir(parents=True, exist_ok=True)
    (root / "books").mkdir(parents=True, exist_ok=True)
    return root


def _index_dir() -> Path:
    d = _kb_root() / "index"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _meta_path() -> Path:
    return _kb_root() / "metadata.json"


def _load_metadata() -> dict[str, Any]:
    path = _meta_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_docs_from_books() -> list[tuple[str, str]]:
    docs: list[tuple[str, str]] = []
    roots = [_kb_root(), _kb_root() / "books"]
    seen: set[str] = set()
    for root in roots:
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if str(p) in seen:
                continue
            seen.add(str(p))
            ext = p.suffix.lower()
            text = ""
            try:
                if ext in {".txt", ".md", ".csv", ".json", ".jsonl"}:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                elif ext == ".pdf":
                    try:
                        from pypdf import PdfReader

                        reader = PdfReader(str(p))
                        text = "\n".join((page.extract_text() or "") for page in reader.pages)
                    except Exception:
                        import pdfplumber

                        with pdfplumber.open(str(p)) as pdf:
                            text = "\n".join((page.extract_text() or "") for page in pdf.pages)
                else:
                    continue
            except Exception:
                continue

            if text.strip():
                docs.append((str(p), text))
    return docs


def _load_path_text(path: Path) -> str:
    ext = path.suffix.lower()
    try:
        if ext in {".txt", ".md", ".csv", ".json", ".jsonl"}:
            return path.read_text(encoding="utf-8", errors="ignore")
        if ext == ".pdf":
            try:
                from pypdf import PdfReader

                reader = PdfReader(str(path))
                return "\n".join((page.extract_text() or "") for page in reader.pages)
            except Exception:
                import pdfplumber

                with pdfplumber.open(str(path)) as pdf:
                    return "\n".join((page.extract_text() or "") for page in pdf.pages)
    except Exception:
        return ""
    return ""


def _resolve_input_paths(paths: list[str] | None = None) -> list[tuple[str, str]]:
    if not paths:
        return _load_docs_from_books()

    docs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            continue
        candidates = [path]
        if path.is_dir():
            candidates = [candidate for candidate in path.rglob("*") if candidate.is_file()]
        for candidate in candidates:
            candidate_key = str(candidate.resolve())
            if candidate_key in seen:
                continue
            seen.add(candidate_key)
            text = _load_path_text(candidate)
            if text.strip():
                docs.append((candidate_key, text))
    return docs


def _chunk_text(text: str, size: int = 500, overlap: int = 80) -> list[str]:
    t = text.strip()
    if not t:
        return []
    words = t.split()
    if not words:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + size, len(words))
        chunks.append(" ".join(words[start:end]).strip())
        if end == len(words):
            break
        start = max(end - overlap, start + 1)
    return chunks


@dataclass
class IngestResult:
    status: str
    chunks: int
    files: int
    index_path: str
    added_chunks: int = 0


def build_vector_index(paths: list[str] | None = None) -> IngestResult:
    docs = _resolve_input_paths(paths)
    if not docs:
        return IngestResult(status="empty", chunks=0, files=0, index_path=str(_index_dir()), added_chunks=0)

    try:
        from langchain_community.vectorstores import FAISS
        from langchain_community.docstore.document import Document
        from langchain_community.embeddings import HuggingFaceEmbeddings
    except Exception as exc:
        return IngestResult(status=f"missing_dependencies: {exc}", chunks=0, files=len(docs), index_path=str(_index_dir()), added_chunks=0)

    model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    embeddings = HuggingFaceEmbeddings(model_name=model_name)
    metadata = _load_metadata()
    existing_chunk_ids = set(metadata.get("chunk_ids") or [])

    lc_docs = []
    discovered_chunk_ids: set[str] = set(existing_chunk_ids)
    for file_path, text in docs:
        chunks = _chunk_text(text)
        for idx, chunk in enumerate(chunks):
            digest = hashlib.sha1(f"{file_path}:{chunk}".encode("utf-8")).hexdigest()
            discovered_chunk_ids.add(digest)
            if digest in existing_chunk_ids:
                continue
            lc_docs.append(
                Document(
                    page_content=chunk,
                    metadata={
                        "source": file_path,
                        "chunk_index": idx,
                        "chunk_id": digest,
                    },
                )
            )

    if not lc_docs:
        return IngestResult(
            status="ok",
            chunks=int(metadata.get("chunks", 0) or 0),
            files=len(docs),
            index_path=str(_index_dir()),
            added_chunks=0,
        )

    index_dir = _index_dir()
    if (index_dir / "index.faiss").exists():
        try:
            vs = FAISS.load_local(str(index_dir), embeddings, allow_dangerous_deserialization=False)
        except Exception:
            vs = FAISS.load_local(str(index_dir), embeddings, allow_dangerous_deserialization=True)
        vs.add_documents(lc_docs)
    else:
        vs = FAISS.from_documents(lc_docs, embeddings)
    vs.save_local(str(_index_dir()))

    meta = {
        "files": [f for f, _ in docs],
        "chunks": int(metadata.get("chunks", 0) or 0) + len(lc_docs),
        "added_chunks": len(lc_docs),
        "embedding_model": model_name,
        "chunk_ids": sorted(discovered_chunk_ids),
    }
    _meta_path().write_text(json.dumps(meta, indent=2), encoding="utf-8")

    return IngestResult(status="ok", chunks=meta["chunks"], files=len(docs), index_path=str(_index_dir()), added_chunks=len(lc_docs))


def ingest_knowledge_base(paths: list[str] | None = None) -> dict[str, Any]:
    result = build_vector_index(paths=paths)
    return {
        "status": result.status,
        "chunks": result.chunks,
        "files": result.files,
        "added_chunks": result.added_chunks,
        "index_path": result.index_path,
        "metadata_path": str(_meta_path()),
    }
