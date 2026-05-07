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

# --- Advanced RAG ---
ENABLE_HYBRID_SEARCH = os.getenv("ENABLE_HYBRID_SEARCH", "true").lower() == "true"
ENABLE_QUERY_REWRITE = os.getenv("ENABLE_QUERY_REWRITE", "true").lower() == "true"
ENABLE_RERANKER = os.getenv("ENABLE_RERANKER", "true").lower() == "true"
ENABLE_PARENT_CHILD = os.getenv("ENABLE_PARENT_CHILD", "false").lower() == "true"
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
RERANKER_TOP_K = int(os.getenv("RERANKER_TOP_K", "5"))
PARENT_CHUNK_SIZE = 1500  # 父块大小
CHILD_CHUNK_SIZE = 500    # 子块大小（用于检索）

# --- Embedding ---
EMBED_API_KEY  = os.getenv("EMBED_API_KEY", "")
EMBED_BASE_URL = os.getenv("EMBED_BASE_URL", "")
EMBED_MODEL    = os.getenv("EMBED_MODEL", "qwen3-vl-embedding")
EMBED_DIMS     = int(os.getenv("EMBED_DIMENSIONS", "2048"))
EMBED_BATCH    = 10  # DashScope text-embedding-v3 单批上限为 10

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
    source_url: str = ""  # 数据来源URL
    parent_id:  str = ""  # 父块ID（用于父子chunk策略）
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
    source_url:     str = ""  # 数据来源URL（API数据源有值，上传文件为空）
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
            {
                "doc_id": c.doc_id,
                "doc_name": c.doc_name,
                "char_start": c.char_start,
                "parent_id": c.parent_id or "",
            }
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
            {
                "doc_id": c.doc_id,
                "doc_name": c.doc_name,
                "char_start": c.char_start,
                "parent_id": c.parent_id or "",
            }
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
    total_batches = (len(texts) + EMBED_BATCH - 1) // EMBED_BATCH
    for batch_idx, i in enumerate(range(0, len(texts), EMBED_BATCH)):
        batch = texts[i: i + EMBED_BATCH]
        retry = 0
        while retry < 3:
            try:
                resp = client.embeddings.create(
                    model=EMBED_MODEL,
                    input=batch,
                    dimensions=EMBED_DIMS,   # text-embedding-v3 支持指定维度
                )
                sorted_data = sorted(resp.data, key=lambda x: x.index)
                all_embeddings.extend([item.embedding for item in sorted_data])
                break
            except Exception as e:
                retry += 1
                if retry >= 3:
                    raise RuntimeError(f"Embedding API 调用失败（已重试3次）: {e}") from e
                time.sleep(1.0 * retry)
        # 批次间限速：每 10 批暂停一次，避免触发 DashScope QPS 限流
        if (batch_idx + 1) % 10 == 0:
            logger.info(f"[Embed] 进度 {batch_idx + 1}/{total_batches} 批")
            time.sleep(0.5)
    return all_embeddings


def embed_query(query: str) -> list[float]:
    results = embed_texts([query])
    return results[0] if results else []


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def _clean_markdown(text: str) -> str:
    """
    清理 Markdown 中无法被 RAG 利用的媒体引用，保留语义信息：
      - 图片 ![alt](url)         → [图片: alt]（保留 alt 作为语义锚点）
      - 视频 <video ...>         → [视频内容]
      - HTML <img alt="...">     → [图片: alt]
      - 行内 HTML 标签           → 去除标签，保留内容
    """
    # HTML <img> 标签 → 提取 alt
    def img_tag_replace(m: re.Match) -> str:
        alt = re.search(r'alt=["\']([^"\']*)["\']', m.group(0))
        label = alt.group(1).strip() if alt else ""
        return f"[图片: {label}]" if label else "[图片]"

    text = re.sub(r'<img\b[^>]*/?>',        img_tag_replace,   text, flags=re.IGNORECASE)

    # HTML <video> / <audio> 块 → 占位符
    text = re.sub(r'<video\b[^>]*>.*?</video>', "[视频内容]", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<video\b[^>]*/?>',          "[视频内容]", text, flags=re.IGNORECASE)
    text = re.sub(r'<audio\b[^>]*>.*?</audio>', "[音频内容]", text, flags=re.IGNORECASE | re.DOTALL)

    # Markdown 图片 ![alt](url) → [图片: alt]
    def md_img_replace(m: re.Match) -> str:
        alt = m.group(1).strip()
        return f"[图片: {alt}]" if alt else "[图片]"

    text = re.sub(r'!\[([^\]]*)\]\([^)]*\)', md_img_replace, text)

    # Markdown 链接 [text](url) → 保留 text
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)

    # 剩余行内 HTML 标签（<span>、<div> 等）→ 去标签保留内容
    text = re.sub(r'<[^>]+>', '', text)

    return text


def extract_text(file_bytes: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext in ("txt", "md"):
        try:
            raw = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            raw = file_bytes.decode("latin-1", errors="replace")
        # Markdown 文件额外清理媒体标签，避免噪声进入分块
        return _clean_markdown(raw) if ext == "md" else raw
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
            # 用双换行连接，使分块算法能按行切割（单换行会导致整表被视为一个巨型段落）
            return "\n\n".join(parts)
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
                # 用双换行连接，使分块算法能按行切割
                return "\n\n".join(parts)
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

def ingest_document(file_bytes: bytes, filename: str, embed: bool = True) -> Document:
    """
    解析 → 分块 → 向量化 → 写入 Chroma（或 JSON 降级） → 持久化元数据
    embed=False 时只做分块和持久化，跳过向量化（供后台异步调用）。
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

    if embed and _embedding_available() and chunks:
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
# BM25 Retrieval
# ---------------------------------------------------------------------------

_bm25_index = None
_bm25_chunks = []


def _build_bm25_index(chunks: list[Chunk]) -> None:
    """构建 BM25 索引"""
    global _bm25_index, _bm25_chunks
    try:
        from rank_bm25 import BM25Okapi
        import jieba

        _bm25_chunks = chunks
        # 对中文进行分词，英文按空格分割
        tokenized_corpus = []
        for chunk in chunks:
            # 简单的中英文混合分词
            words = []
            for char in chunk.text:
                if '一' <= char <= '鿿':  # 中文字符
                    words.extend(jieba.cut(char))
                else:
                    words.append(char)
            # 也保留原始的空格分词
            words.extend(chunk.text.lower().split())
            tokenized_corpus.append(words)

        _bm25_index = BM25Okapi(tokenized_corpus)
        logger.info(f"[BM25] 索引构建完成，共 {len(chunks)} 个文档块")
    except ImportError:
        logger.warning("[BM25] rank-bm25 未安装，BM25检索不可用")
        _bm25_index = None


def _bm25_search(query: str, top_k: int = 10) -> list[dict]:
    """使用 BM25 检索"""
    global _bm25_index, _bm25_chunks

    if _bm25_index is None or not _bm25_chunks:
        return []

    try:
        import jieba
        # 对查询进行分词
        query_words = []
        for char in query:
            if '一' <= char <= '鿿':
                query_words.extend(jieba.cut(char))
            else:
                query_words.append(char)
        query_words.extend(query.lower().split())

        scores = _bm25_index.get_scores(query_words)
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                chunk = _bm25_chunks[idx]
                results.append({
                    "text": chunk.text,
                    "doc_name": chunk.doc_name,
                    "doc_id": chunk.doc_id,
                    "char_start": chunk.char_start,
                    "score": float(scores[idx]),
                    "chunk_id": chunk.chunk_id,
                })

        return results
    except Exception as e:
        logger.warning(f"[BM25] 检索失败: {e}")
        return []


# ---------------------------------------------------------------------------
# RRF (Reciprocal Rank Fusion)
# ---------------------------------------------------------------------------

def _reciprocal_rank_fusion(
    rankings: list[list[dict]],
    k: int = 60
) -> list[dict]:
    """
    RRF 融合多个排序结果

    Args:
        rankings: 多个检索结果列表，每个结果是 dict，必须包含唯一标识字段
        k: RRF 参数，默认 60

    Returns:
        融合后的排序结果
    """
    rrf_scores = {}
    chunk_data = {}

    for ranking in rankings:
        for rank, item in enumerate(ranking, 1):
            # 使用 chunk_id 或 text 作为唯一标识
            item_id = item.get("chunk_id", item.get("text", ""))
            if not item_id:
                continue

            # RRF 公式: 1 / (k + rank)
            if item_id not in rrf_scores:
                rrf_scores[item_id] = 0
                chunk_data[item_id] = item

            rrf_scores[item_id] += 1.0 / (k + rank)

    # 按 RRF 分数排序
    sorted_items = sorted(
        rrf_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    results = []
    for item_id, score in sorted_items:
        item = chunk_data[item_id].copy()
        item["rrf_score"] = score
        results.append(item)

    return results


# ---------------------------------------------------------------------------
# Query Rewriting with Claude Haiku
# ---------------------------------------------------------------------------

def _rewrite_query(query: str) -> list[str]:
    """
    使用 Claude Haiku 对查询进行多角度改写

    Returns:
        包含原始查询和改写查询的列表
    """
    if not ENABLE_QUERY_REWRITE:
        return [query]

    try:
        from openai import OpenAI

        # 检查是否配置了 Claude API
        api_key = os.getenv("ANTHROPIC_AUTH_TOKEN") or os.getenv("ANTHROPIC_API_KEY")
        base_url = os.getenv("ANTHROPIC_BASE_URL")

        if not api_key:
            logger.warning("[QueryRewrite] Claude API 未配置，跳过查询改写")
            return [query]

        # 使用 OpenAI 兼容格式调用 Claude
        client = OpenAI(api_key=api_key, base_url=base_url) if base_url else None

        if not client:
            # 如果没有自定义 base_url，使用 anthropic SDK
            import anthropic
            client_anthropic = anthropic.Anthropic(api_key=api_key)

            prompt = f"""请将以下用户查询改写为3个不同角度的问题，以提高检索召回率。

原始查询：{query}

要求：
1. 保持原意，但从不同角度表达
2. 使用不同的关键词和表述方式
3. 每个改写查询单独一行
4. 不要添加编号或其他标记
5. 直接输出改写结果，不要解释

改写查询："""

            response = client_anthropic.messages.create(
                model="claude-haiku-4-5",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )

            rewritten = response.content[0].text.strip().split('\n')
            rewritten = [q.strip() for q in rewritten if q.strip()]

            # 返回原始查询 + 改写查询
            return [query] + rewritten[:3]

    except Exception as e:
        logger.warning(f"[QueryRewrite] 查询改写失败: {e}")
        return [query]


# ---------------------------------------------------------------------------
# Reranker with bge-reranker-v2-m3
# ---------------------------------------------------------------------------

_reranker_model = None


def _get_reranker():
    """获取或初始化 Reranker 模型"""
    global _reranker_model

    if not ENABLE_RERANKER:
        return None

    if _reranker_model is None:
        try:
            from FlagEmbedding import FlagReranker
            _reranker_model = FlagReranker(RERANKER_MODEL, use_fp16=True)
            logger.info(f"[Reranker] 模型加载成功: {RERANKER_MODEL}")
        except Exception as e:
            logger.warning(f"[Reranker] 模型加载失败: {e}")
            _reranker_model = False  # 标记为失败，避免重复尝试

    return _reranker_model if _reranker_model is not False else None


def _rerank_results(query: str, results: list[dict], top_k: int = None) -> list[dict]:
    """
    使用 Reranker 对检索结果进行精排

    Args:
        query: 用户查询
        results: 初排结果列表
        top_k: 返回前 k 个结果，默认使用 RERANKER_TOP_K

    Returns:
        重排序后的结果
    """
    if not results:
        return results

    reranker = _get_reranker()
    if reranker is None:
        return results

    if top_k is None:
        top_k = RERANKER_TOP_K

    try:
        # 准备输入对
        pairs = [[query, item["text"]] for item in results]

        # 计算相关性分数
        scores = reranker.compute_score(pairs, normalize=True)

        # 如果只有一个结果，scores 是单个值而不是列表
        if not isinstance(scores, list):
            scores = [scores]

        # 添加 rerank 分数并排序
        for item, score in zip(results, scores):
            item["rerank_score"] = float(score)

        results.sort(key=lambda x: x["rerank_score"], reverse=True)

        logger.info(f"[Reranker] 重排序完成，top-{top_k} 分数: {[r['rerank_score'] for r in results[:top_k]]}")

        return results[:top_k]

    except Exception as e:
        logger.warning(f"[Reranker] 重排序失败: {e}")
        return results[:top_k]


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


def _expand_to_parent_chunks(results: list[dict], all_chunks: list[Chunk]) -> list[dict]:
    """
    父子 Chunk 策略：将检索到的子块扩展为父块

    Args:
        results: 检索结果列表
        all_chunks: 所有文档块

    Returns:
        扩展后的结果列表
    """
    if not ENABLE_PARENT_CHILD:
        return results

    # 构建 chunk_id 到 chunk 的映射
    chunk_map = {c.chunk_id: c for c in all_chunks}

    expanded_results = []
    seen_parents = set()

    for result in results:
        chunk_id = result.get("chunk_id", "")
        if not chunk_id or chunk_id not in chunk_map:
            expanded_results.append(result)
            continue

        chunk = chunk_map[chunk_id]
        parent_id = chunk.parent_id

        # 如果有父块且未处理过
        if parent_id and parent_id in chunk_map and parent_id not in seen_parents:
            parent_chunk = chunk_map[parent_id]
            expanded_results.append({
                "text": parent_chunk.text,
                "doc_name": parent_chunk.doc_name,
                "doc_id": parent_chunk.doc_id,
                "char_start": parent_chunk.char_start,
                "chunk_id": parent_id,
            })
            seen_parents.add(parent_id)
        elif not parent_id:
            # 没有父块，使用原始块
            if chunk_id not in seen_parents:
                expanded_results.append(result)
                seen_parents.add(chunk_id)

    return expanded_results


def retrieve_context(query: str, top_k: int = MAX_CONTEXT_CHUNKS) -> str:
    """
    检索最相关文本块。支持混合检索（BM25 + 向量 + RRF 融合）。
    优先级：
      混合检索（BM25 + Embedding + RRF） → Chroma + Embedding → NumPy + Embedding → TF-IDF
    """
    docs = load_documents()
    if not docs:
        return ""

    all_chunks: list[Chunk] = [c for d in docs for c in d.chunks]
    if not all_chunks:
        return ""

    method = "tfidf"
    results: list[dict] = []   # [{text, doc_name, doc_id, char_start, chunk_id}]

    # ── 查询改写（可选）──
    queries = [query]
    if ENABLE_QUERY_REWRITE:
        queries = _rewrite_query(query)
        logger.info(f"[QueryRewrite] 生成 {len(queries)} 个查询变体")

    # ── 方案 A: 混合检索（BM25 + 向量 + RRF）──
    if ENABLE_HYBRID_SEARCH and _embedding_available() and _chroma_available():
        try:
            col = _get_chroma_collection()
            if col.count() > 0:
                # 构建 BM25 索引
                _build_bm25_index(all_chunks)

                all_rankings = []

                # 对每个查询变体进行检索
                for q in queries:
                    # 1. 向量检索
                    q_vec = embed_query(q)
                    if q_vec:
                        vector_results = _chroma_query(q_vec, top_k * 3)
                        # 添加 chunk_id
                        for r in vector_results:
                            r["chunk_id"] = f"{r['doc_id']}_{r['char_start']}"
                        all_rankings.append(vector_results)

                    # 2. BM25 检索
                    bm25_results = _bm25_search(q, top_k * 3)
                    if bm25_results:
                        all_rankings.append(bm25_results)

                # 3. RRF 融合
                if all_rankings:
                    results = _reciprocal_rank_fusion(all_rankings)
                    results = results[:top_k * 2]  # 取前 2*top_k 送入 reranker
                    method = "hybrid(bm25+vector+rrf)"

                    # 4. Reranker 精排（可选）
                    if ENABLE_RERANKER and results:
                        results = _rerank_results(query, results, top_k)
                        method = "hybrid(bm25+vector+rrf+rerank)"

        except Exception as e:
            logger.warning(f"[RAG] 混合检索失败，降级: {e}")

    # ── 方案 B: Chroma + Embedding（单一向量检索）──
    if not results and _embedding_available() and _chroma_available():
        try:
            col = _get_chroma_collection()
            if col.count() > 0:
                q_vec = embed_query(query)
                if q_vec:
                    raw = _chroma_query(q_vec, top_k * 2)
                    # cosine distance < 0.6 才认为相关（余弦相似度 > 0.4）
                    results = [r for r in raw if r["distance"] < 0.6]

                    # Reranker 精排（可选）
                    if ENABLE_RERANKER and results:
                        for r in results:
                            r["chunk_id"] = f"{r['doc_id']}_{r['char_start']}"
                        results = _rerank_results(query, results, top_k)
                        method = "chroma+embedding+rerank"
                    else:
                        results = results[:top_k]
                        method = "chroma+embedding"
        except Exception as e:
            logger.warning(f"[RAG] Chroma 检索失败，降级: {e}")

    # ── 方案 C: NumPy + Embedding（JSON 中有向量）──
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
                    top_idx = np.argsort(scores)[::-1][:top_k * 2].tolist()
                    top_idx = [i for i in top_idx if scores[i] >= 0.10]
                    results = [
                        {
                            "text":       chunks_with_emb[i].text,
                            "doc_name":   chunks_with_emb[i].doc_name,
                            "doc_id":     chunks_with_emb[i].doc_id,
                            "char_start": chunks_with_emb[i].char_start,
                            "chunk_id":   chunks_with_emb[i].chunk_id,
                        }
                        for i in top_idx
                    ]

                    # Reranker 精排（可选）
                    if ENABLE_RERANKER and results:
                        results = _rerank_results(query, results, top_k)
                        method = "numpy+embedding+rerank"
                    else:
                        results = results[:top_k]
                        method = "numpy+embedding"
            except Exception as e:
                logger.warning(f"[RAG] NumPy embedding 检索失败，降级: {e}")

    # ── 方案 D: TF-IDF ──
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

    # 父子 Chunk 策略：如果启用，用父块替换子块
    if ENABLE_PARENT_CHILD:
        results = _expand_to_parent_chunks(results, all_chunks)

    # 按文档位置排序，保持上下文连贯性
    results.sort(key=lambda r: (r["doc_id"], r["char_start"]))

    parts = [f"[来源: {r['doc_name']}]\n{r['text']}" for r in results]
    return "\n\n---\n\n".join(parts)


def build_rag_system_prompt(base_system: str, query: str) -> str:
    context = retrieve_context(query)
    if not context:
        return base_system

    rag_block = f"""你可以访问以下与用户问题相关的内部知识库内容。

<knowledge_base>
{context}
</knowledge_base>

回答要求：
1. **综合分析**：结合内部知识库内容和你的外部知识，提供全面、准确的回答
2. **优先级**：内部知识库的信息优先级更高，是最权威的参考
3. **补充扩展**：如果知识库内容不完整，可以用你的外部知识补充背景、原理、最佳实践等
4. **明确来源**：
   - 引用知识库内容时，注明来源文档名称
   - 使用外部知识时，说明这是基于通用知识的补充，并提供相关参考链接（如维基百科、百度百科等搜索链接）
   - 参考链接格式示例：[维基百科 - Python](https://zh.wikipedia.org/wiki/Python)、[百度百科 - Python](https://baike.baidu.com/item/Python)
5. **深度结合**：不要只是罗列知识库内容，要分析、解释、关联，形成有洞察力的回答

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
