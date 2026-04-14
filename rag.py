"""
RAG Engine — Retrieval-Augmented Generation

检索层次（优先级从高到低）：
  1. Chroma + Embedding（向量数据库，最佳语义检索）
  2. NumPy + Embedding（无 Chroma 时，向量存 JSON）
  3. TF-IDF（Embedding API 不可用时的离线降级）

存储：
  - Chroma 持久化目录: data/chroma/
  - 文档元数据 JSON:   data/documents.json（不含向量，Chroma 存向量）
"""

from __future__ import annotations

# chromadb 要求 sqlite3 >= 3.35.0，旧系统（CentOS 等）自带版本不够。
# pysqlite3-binary 内置了新版 sqlite3，下面把标准库的 sqlite3 替换掉。
try:
    import pysqlite3 as _pysqlite3
    import sys as _sys
    _sys.modules["sqlite3"] = _pysqlite3
except ImportError:
    pass  # 本地开发环境 sqlite3 够新，无需替换

import json
import logging
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DATA_DIR   = Path("data")
DOCS_FILE  = DATA_DIR / "documents.json"
CHROMA_DIR = DATA_DIR / "chroma"

# --- Chunking ---
CHUNK_SIZE    = 500
CHUNK_OVERLAP = 60
MAX_CONTEXT_CHUNKS = 5

# --- Embedding ---
EMBED_API_KEY  = os.getenv("EMBED_API_KEY", "")
EMBED_BASE_URL = os.getenv("EMBED_BASE_URL", "")
EMBED_MODEL    = os.getenv("EMBED_MODEL", "text-embedding-v3")
EMBED_DIMS     = int(os.getenv("EMBED_DIMENSIONS", "1024"))
EMBED_BATCH    = 16

CHROMA_COLLECTION = "rag_chunks"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Chunk:
    chunk_id:   str
    doc_id:     str
    doc_name:   str
    text:       str
    char_start: int
    # embedding 仅在 Chroma 不可用时写入 JSON（NumPy 降级）
    embedding:  list[float] = field(default_factory=list)


@dataclass
class Document:
    doc_id:         str
    name:           str
    file_type:      str
    char_count:     int
    chunk_count:    int
    has_embeddings: bool = False
    chunks: list[Chunk] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Persistence（元数据）
# ---------------------------------------------------------------------------

def _load_store() -> dict:
    if DOCS_FILE.exists():
        try:
            return json.loads(DOCS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_store(store: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_FILE.write_text(
        json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_documents() -> list[Document]:
    store = _load_store()
    docs = []
    for raw in store.get("documents", []):
        chunks_raw = raw.pop("chunks", [])
        chunks = []
        for c in chunks_raw:
            c.setdefault("embedding", [])
            chunks.append(Chunk(**c))
        raw.setdefault("has_embeddings", False)
        docs.append(Document(**raw, chunks=chunks))
    return docs


def save_documents(docs: list[Document]) -> None:
    # 保存元数据时，不把向量写进 JSON（Chroma 负责存向量）
    rows = []
    for d in docs:
        d_dict = asdict(d)
        for c in d_dict["chunks"]:
            c["embedding"] = []   # 不持久化到 JSON
        rows.append(d_dict)
    _save_store({"documents": rows})


def get_document_list() -> list[dict]:
    docs = load_documents()
    return [
        {
            "doc_id":         d.doc_id,
            "name":           d.name,
            "file_type":      d.file_type,
            "char_count":     d.char_count,
            "chunk_count":    d.chunk_count,
            "has_embeddings": d.has_embeddings,
        }
        for d in docs
    ]


def delete_document(doc_id: str) -> bool:
    docs = load_documents()
    new_docs = [d for d in docs if d.doc_id != doc_id]
    if len(new_docs) == len(docs):
        return False
    save_documents(new_docs)
    # 同时从 Chroma 删除
    try:
        col = _get_chroma_collection()
        col.delete(where={"doc_id": doc_id})
    except Exception as e:
        logger.warning(f"[Chroma] 删除失败（不影响主流程）: {e}")
    return True


# ---------------------------------------------------------------------------
# Chroma
# ---------------------------------------------------------------------------

_chroma_client = None
_chroma_collection = None


def _chroma_available() -> bool:
    try:
        import chromadb  # noqa: F401
        return True
    except ImportError:
        return False


def _get_chroma_collection():
    """获取（或创建）Chroma collection，使用持久化存储。"""
    global _chroma_client, _chroma_collection
    if _chroma_collection is not None:
        return _chroma_collection

    import chromadb
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    _chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    _chroma_collection = _chroma_client.get_or_create_collection(
        name=CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},   # 使用余弦距离
    )
    return _chroma_collection


def _chroma_add_chunks(chunks: list[Chunk], embeddings: list[list[float]]) -> None:
    """批量写入 Chroma。"""
    col = _get_chroma_collection()
    col.add(
        ids=[c.chunk_id for c in chunks],
        embeddings=embeddings,
        documents=[c.text for c in chunks],
        metadatas=[
            {"doc_id": c.doc_id, "doc_name": c.doc_name, "char_start": c.char_start}
            for c in chunks
        ],
    )


def _chroma_upsert_chunks(chunks: list[Chunk], embeddings: list[list[float]]) -> None:
    """批量 upsert（存在则更新，不存在则插入）。"""
    col = _get_chroma_collection()
    col.upsert(
        ids=[c.chunk_id for c in chunks],
        embeddings=embeddings,
        documents=[c.text for c in chunks],
        metadatas=[
            {"doc_id": c.doc_id, "doc_name": c.doc_name, "char_start": c.char_start}
            for c in chunks
        ],
    )


def _chroma_get_by_ids(chunk_ids: list[str]) -> list[dict]:
    """
    按 chunk_id 精确获取，返回列表。
    每个结果: {chunk_id, text, doc_id, doc_name, char_start}
    """
    col = _get_chroma_collection()
    results = col.get(
        ids=chunk_ids,
        include=["documents", "metadatas"],
    )
    items = []
    for cid, text, meta in zip(
        results["ids"],
        results["documents"],
        results["metadatas"],
    ):
        items.append({
            "chunk_id":  cid,
            "text":       text,
            "doc_id":     meta["doc_id"],
            "doc_name":   meta["doc_name"],
            "char_start": meta.get("char_start", 0),
        })
    return items


def _chroma_get_by_doc(doc_id: str) -> list[dict]:
    """
    获取某文档在 Chroma 中的所有 chunks，按 char_start 排序。
    每个结果: {chunk_id, text, doc_id, doc_name, char_start}
    """
    col = _get_chroma_collection()
    results = col.get(
        where={"doc_id": doc_id},
        include=["documents", "metadatas"],
    )
    items = []
    for cid, text, meta in zip(
        results["ids"],
        results["documents"],
        results["metadatas"],
    ):
        items.append({
            "chunk_id":  cid,
            "text":       text,
            "doc_id":     meta["doc_id"],
            "doc_name":   meta["doc_name"],
            "char_start": meta.get("char_start", 0),
        })
    items.sort(key=lambda x: x["char_start"])
    return items


def _chroma_peek(limit: int = 5) -> list[dict]:
    """
    抽样返回集合前 N 条记录，用于调试/预览。
    每个结果: {chunk_id, text, doc_id, doc_name, char_start}
    """
    col = _get_chroma_collection()
    results = col.peek(limit=limit)
    items = []
    for cid, text, meta in zip(
        results["ids"],
        results["documents"],
        results["metadatas"],
    ):
        items.append({
            "chunk_id":  cid,
            "text":       text,
            "doc_id":     meta["doc_id"],
            "doc_name":   meta["doc_name"],
            "char_start": meta.get("char_start", 0),
        })
    return items


def _chroma_reset_collection() -> int:
    """
    清空整个集合（删除所有 chunks），返回清空前的记录数。
    注意：此操作不可逆，仅用于管理目的。
    """
    global _chroma_collection
    col = _get_chroma_collection()
    count_before = col.count()
    if count_before > 0:
        # 获取所有 id 后批量删除（Chroma 不支持 delete all，需先 get ids）
        all_ids = col.get(include=[])["ids"]
        if all_ids:
            col.delete(ids=all_ids)
    # 重置缓存引用，确保下次 get_or_create 拿到最新状态
    _chroma_collection = None
    return count_before


def _chroma_query(query_embedding: list[float], top_k: int) -> list[dict]:
    """
    查询 Chroma，返回 top-k 结果列表。
    每个结果: {text, doc_name, doc_id, char_start, distance}
    """
    col = _get_chroma_collection()
    if col.count() == 0:
        return []
    results = col.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, col.count()),
        include=["documents", "metadatas", "distances"],
    )
    items = []
    for text, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        items.append({
            "text":       text,
            "doc_name":   meta["doc_name"],
            "doc_id":     meta["doc_id"],
            "char_start": meta.get("char_start", 0),
            "distance":   dist,           # cosine distance: 0=完全相同, 2=完全相反
        })
    return items


# ---------------------------------------------------------------------------
# Embedding API（阿里云 DashScope，OpenAI 兼容格式）
# ---------------------------------------------------------------------------

def _embedding_available() -> bool:
    return bool(EMBED_API_KEY and EMBED_BASE_URL)


def _get_openai_client():
    from openai import OpenAI
    return OpenAI(api_key=EMBED_API_KEY, base_url=EMBED_BASE_URL)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量向量化，返回等长向量列表。失败抛出异常。"""
    if not texts:
        return []
    client = _get_openai_client()
    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH):
        batch = texts[i: i + EMBED_BATCH]
        retry = 0
        while retry < 3:
            try:
                resp = client.embeddings.create(
                    model=EMBED_MODEL,
                    input=batch,
                )
                sorted_data = sorted(resp.data, key=lambda x: x.index)
                all_embeddings.extend([item.embedding for item in sorted_data])
                break
            except Exception as e:
                retry += 1
                if retry >= 3:
                    raise RuntimeError(f"Embedding API 调用失败（已重试3次）: {e}") from e
                time.sleep(1.0 * retry)
    return all_embeddings


def embed_query(query: str) -> list[float]:
    results = embed_texts([query])
    return results[0] if results else []


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def extract_text(file_bytes: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext in ("txt", "md"):
        try:
            return file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return file_bytes.decode("latin-1", errors="replace")
    elif ext == "pdf":
        try:
            import fitz
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            return "\n".join(page.get_text() for page in doc)
        except Exception as exc:
            raise ValueError(f"PDF 解析失败: {exc}") from exc
    elif ext in ("xlsx", "xls"):
        try:
            import io
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
            parts: list[str] = []
            for sheet in wb.worksheets:
                parts.append(f"【Sheet: {sheet.title}】")
                for row in sheet.iter_rows(values_only=True):
                    # 过滤空行，把每格转为字符串后用制表符拼接
                    cells = [str(c) if c is not None else "" for c in row]
                    if any(c.strip() for c in cells):
                        parts.append("\t".join(cells))
            return "\n".join(parts)
        except Exception:
            # openpyxl 无法解析旧格式 .xls，降级用 xlrd
            try:
                import io
                import xlrd
                wb = xlrd.open_workbook(file_contents=file_bytes)
                parts = []
                for sheet in wb.sheets():
                    parts.append(f"【Sheet: {sheet.name}】")
                    for row_idx in range(sheet.nrows):
                        cells = [str(sheet.cell_value(row_idx, col)) for col in range(sheet.ncols)]
                        if any(c.strip() for c in cells):
                            parts.append("\t".join(cells))
                return "\n".join(parts)
            except Exception as exc:
                raise ValueError(f"Excel 解析失败: {exc}") from exc
    else:
        raise ValueError(f"不支持的文件类型: .{ext}")


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def _split_into_chunks(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[tuple[str, int]]:
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    paragraphs: list[tuple[str, int]] = []
    pos = 0
    for para in re.split(r"\n\n+", text):
        para = para.strip()
        if para:
            idx = text.index(para, pos)
            paragraphs.append((para, idx))
            pos = idx + len(para)

    chunks: list[tuple[str, int]] = []
    current: list[str] = []
    current_len = 0
    current_start = 0

    def flush(start: int) -> None:
        combined = " ".join(current).strip()
        if combined:
            chunks.append((combined, start))

    for para_text, para_start in paragraphs:
        if len(para_text) > chunk_size * 4:
            sentences = re.split(r"(?<=[.!?。！？])\s*", para_text)
            for sent in sentences:
                if not sent.strip():
                    continue
                if current_len + len(sent) > chunk_size and current:
                    flush(current_start)
                    tail = " ".join(current).split()
                    keep = " ".join(tail[-overlap // 6:]) if tail else ""
                    current = [keep, sent] if keep else [sent]
                    current_len = len(" ".join(current))
                    current_start = para_start
                else:
                    current.append(sent)
                    current_len += len(sent)
                    if not current_start:
                        current_start = para_start
        else:
            if current_len + len(para_text) > chunk_size and current:
                flush(current_start)
                tail = " ".join(current).split()
                keep = " ".join(tail[-overlap // 6:]) if tail else ""
                current = [keep, para_text] if keep else [para_text]
                current_len = len(" ".join(current))
                current_start = para_start
            else:
                if not current:
                    current_start = para_start
                current.append(para_text)
                current_len += len(para_text)

    flush(current_start)
    return [(t, s) for t, s in chunks if t.strip()]


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

def ingest_document(file_bytes: bytes, filename: str) -> Document:
    """
    解析 → 分块 → 向量化 → 写入 Chroma（或 JSON 降级） → 持久化元数据
    """
    text = extract_text(file_bytes, filename)
    raw_chunks = _split_into_chunks(text)

    doc_id = str(uuid.uuid4())
    ext = Path(filename).suffix.lower().lstrip(".")

    chunks = [
        Chunk(
            chunk_id=f"{doc_id}_{i}",
            doc_id=doc_id,
            doc_name=filename,
            text=chunk_text,
            char_start=char_start,
        )
        for i, (chunk_text, char_start) in enumerate(raw_chunks)
    ]

    has_embeddings = False

    if _embedding_available() and chunks:
        try:
            logger.info(f"[RAG] 向量化 {len(chunks)} 块（{filename}）…")
            texts = [c.text for c in chunks]
            embeddings = embed_texts(texts)

            if _chroma_available():
                # ── 方案 A: Chroma ──
                _chroma_add_chunks(chunks, embeddings)
                logger.info(f"[RAG] 已写入 Chroma，集合大小={_get_chroma_collection().count()}")
            else:
                # ── 方案 B: 向量写入 JSON（NumPy 检索）──
                for chunk, emb in zip(chunks, embeddings):
                    chunk.embedding = emb
                logger.info("[RAG] Chroma 不可用，向量存入 JSON")

            has_embeddings = True
        except Exception as e:
            logger.warning(f"[RAG] 向量化失败，使用 TF-IDF 降级: {e}")

    doc = Document(
        doc_id=doc_id,
        name=filename,
        file_type=ext,
        char_count=len(text),
        chunk_count=len(chunks),
        has_embeddings=has_embeddings,
        chunks=chunks,
    )

    existing = load_documents()
    existing.append(doc)
    save_documents(existing)
    return doc


def re_embed_document(doc_id: str) -> bool:
    """对已存在的文档重新向量化并写入 Chroma。"""
    if not _embedding_available():
        return False
    docs = load_documents()
    target = next((d for d in docs if d.doc_id == doc_id), None)
    if not target:
        return False
    try:
        texts = [c.text for c in target.chunks]
        embeddings = embed_texts(texts)
        if _chroma_available():
            # 先删旧数据再写入
            try:
                _get_chroma_collection().delete(where={"doc_id": doc_id})
            except Exception:
                pass
            _chroma_add_chunks(target.chunks, embeddings)
        else:
            for chunk, emb in zip(target.chunks, embeddings):
                chunk.embedding = emb
        target.has_embeddings = True
        save_documents(docs)
        return True
    except Exception as e:
        logger.error(f"[RAG] re_embed_document 失败: {e}")
        return False


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def _cosine_similarity_batch(query_vec: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    query_norm = np.linalg.norm(query_vec)
    if query_norm == 0:
        return np.zeros(len(matrix))
    matrix_norms = np.linalg.norm(matrix, axis=1)
    matrix_norms[matrix_norms == 0] = 1e-10
    return (matrix @ query_vec) / (matrix_norms * query_norm)


def retrieve_context(query: str, top_k: int = MAX_CONTEXT_CHUNKS) -> str:
    """
    检索最相关文本块。优先级：
      Chroma + Embedding → NumPy + Embedding → TF-IDF
    """
    docs = load_documents()
    if not docs:
        return ""

    all_chunks: list[Chunk] = [c for d in docs for c in d.chunks]
    if not all_chunks:
        return ""

    method = "tfidf"
    results: list[dict] = []   # [{text, doc_name, doc_id, char_start}]

    # ── 方案 A: Chroma ──
    if _embedding_available() and _chroma_available():
        try:
            col = _get_chroma_collection()
            if col.count() > 0:
                q_vec = embed_query(query)
                if q_vec:
                    raw = _chroma_query(q_vec, top_k)
                    # cosine distance < 0.6 才认为相关（余弦相似度 > 0.4）
                    results = [r for r in raw if r["distance"] < 0.6]
                    method = "chroma+embedding"
        except Exception as e:
            logger.warning(f"[RAG] Chroma 检索失败，降级: {e}")

    # ── 方案 B: NumPy + Embedding（JSON 中有向量）──
    if not results and _embedding_available():
        chunks_with_emb = [c for c in all_chunks if c.embedding]
        if chunks_with_emb:
            try:
                q_vec = embed_query(query)
                if q_vec:
                    matrix = np.array(
                        [c.embedding for c in chunks_with_emb], dtype=np.float32
                    )
                    scores = _cosine_similarity_batch(
                        np.array(q_vec, dtype=np.float32), matrix
                    )
                    top_idx = np.argsort(scores)[::-1][:top_k].tolist()
                    top_idx = [i for i in top_idx if scores[i] >= 0.10]
                    results = [
                        {
                            "text":       chunks_with_emb[i].text,
                            "doc_name":   chunks_with_emb[i].doc_name,
                            "doc_id":     chunks_with_emb[i].doc_id,
                            "char_start": chunks_with_emb[i].char_start,
                        }
                        for i in top_idx
                    ]
                    method = "numpy+embedding"
            except Exception as e:
                logger.warning(f"[RAG] NumPy embedding 检索失败，降级: {e}")

    # ── 方案 C: TF-IDF ──
    if not results:
        corpus = [c.text for c in all_chunks]
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity

            vectorizer = TfidfVectorizer(
                ngram_range=(1, 2),
                max_features=20_000,
                sublinear_tf=True,
                strip_accents="unicode",
            )
            tfidf_matrix = vectorizer.fit_transform(corpus)
            q_vec = vectorizer.transform([query])
            scores = cosine_similarity(q_vec, tfidf_matrix)[0]
            top_idx = np.argsort(scores)[::-1][:top_k].tolist()
            top_idx = [i for i in top_idx if scores[i] > 0.01]
            results = [
                {
                    "text":       all_chunks[i].text,
                    "doc_name":   all_chunks[i].doc_name,
                    "doc_id":     all_chunks[i].doc_id,
                    "char_start": all_chunks[i].char_start,
                }
                for i in top_idx
            ]
            method = "tfidf"
        except ImportError:
            results = [
                {
                    "text":       c.text,
                    "doc_name":   c.doc_name,
                    "doc_id":     c.doc_id,
                    "char_start": c.char_start,
                }
                for c in all_chunks[:top_k]
            ]

    if not results:
        return ""

    logger.info(f"[RAG] 方式={method}, 命中={len(results)} 块")

    # 按文档位置排序，保持上下文连贯性
    results.sort(key=lambda r: (r["doc_id"], r["char_start"]))

    parts = [f"[来源: {r['doc_name']}]\n{r['text']}" for r in results]
    return "\n\n---\n\n".join(parts)


def build_rag_system_prompt(base_system: str, query: str) -> str:
    context = retrieve_context(query)
    if not context:
        return base_system

    rag_block = f"""你可以访问以下与用户问题相关的内部知识库内容。请使用这些信息提供准确、有依据的回答，并在引用具体信息时注明来源文档名称。

<knowledge_base>
{context}
</knowledge_base>

"""
    return rag_block + base_system


# ---------------------------------------------------------------------------
# 状态查询（供 health 接口使用）
# ---------------------------------------------------------------------------

def get_chroma_status() -> dict:
    if not _chroma_available():
        return {"available": False, "reason": "chromadb 未安装"}
    try:
        col = _get_chroma_collection()
        count = col.count()
        peek_items = _chroma_peek(limit=3) if count > 0 else []
        return {
            "available":  True,
            "collection": CHROMA_COLLECTION,
            "count":      count,
            "path":       str(CHROMA_DIR),
            "peek":       peek_items,
        }
    except Exception as e:
        return {"available": False, "reason": str(e)}


def chroma_get_doc_chunks(doc_id: str) -> list[dict]:
    """对外暴露：获取某文档在 Chroma 中的全部 chunks（按位置排序）。"""
    if not _chroma_available():
        return []
    try:
        return _chroma_get_by_doc(doc_id)
    except Exception as e:
        logger.warning(f"[Chroma] get_doc_chunks 失败: {e}")
        return []


def chroma_peek(limit: int = 5) -> list[dict]:
    """对外暴露：抽样预览集合中的 chunks。"""
    if not _chroma_available():
        return []
    try:
        return _chroma_peek(limit=limit)
    except Exception as e:
        logger.warning(f"[Chroma] peek 失败: {e}")
        return []


def chroma_reset() -> int:
    """对外暴露：清空 Chroma 集合，返回删除前的记录数。"""
    if not _chroma_available():
        return 0
    try:
        return _chroma_reset_collection()
    except Exception as e:
        logger.error(f"[Chroma] reset 失败: {e}")
        return 0
