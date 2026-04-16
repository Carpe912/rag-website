"""
智能问答平台后端
FastAPI + Anthropic Claude API（自定义代理） + Embedding RAG
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from typing import AsyncGenerator

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from rag import (
    build_rag_system_prompt,
    delete_document,
    get_document_list,
    get_chroma_status,
    chroma_get_doc_chunks,
    chroma_peek,
    chroma_reset,
    ingest_document,
    re_embed_document,
    _embedding_available,
    EMBED_MODEL,
    EMBED_DIMS,
    Document,
)

from api_source import (
    ApiSourceConfig,
    get_api_sources,
    add_api_source,
    update_api_source,
    delete_api_source,
    sync_api_source,
)

load_dotenv()

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 后台向量化任务（asyncio，运行在同一进程，无环境隔离问题）
# ---------------------------------------------------------------------------

async def _bg_embed(doc_id: str) -> None:
    """在 asyncio 线程池中执行向量化，不阻塞 event loop。"""
    loop = asyncio.get_running_loop()
    try:
        ok = await loop.run_in_executor(None, re_embed_document, doc_id)
        if ok:
            logger.info(f"[Embed] 文档 {doc_id} 向量化完成")
        else:
            logger.warning(f"[Embed] 文档 {doc_id} 向量化失败（re_embed_document 返回 False）")
    except Exception as exc:
        logger.error(f"[Embed] 文档 {doc_id} 向量化异常: {exc}")

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="智能问答平台", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the frontend from ./static/
app.mount("/static", StaticFiles(directory="static"), name="static")

# Anthropic client — 支持自定义代理地址和 token
_anthropic_client: anthropic.AsyncAnthropic | None = None


def get_client() -> anthropic.AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        # 优先使用 ANTHROPIC_AUTH_TOKEN（自定义代理），其次用标准 ANTHROPIC_API_KEY
        api_key = os.getenv("ANTHROPIC_AUTH_TOKEN") or os.getenv("ANTHROPIC_API_KEY")
        base_url = os.getenv("ANTHROPIC_BASE_URL")  # 自定义代理地址

        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="未配置 API 密钥，请检查 .env 文件中的 ANTHROPIC_AUTH_TOKEN。",
            )

        kwargs: dict = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url

        _anthropic_client = anthropic.AsyncAnthropic(**kwargs)
    return _anthropic_client


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_SYSTEM_PROMPT = """你是一个智能、专业的问答助手，能够回答各种问题，包括编程、技术、知识性问题等。

回答规范：
- 代码块始终指定语言，以便语法高亮
- 引用内部知识库信息时，注明来源文档名称
- 使用 Markdown 格式化回答
- 回答清晰、简洁、准确
- 如果不确定，请如实说明而非编造"""

# 使用支持的模型名称
MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-6")
MAX_TOKENS = 8000

# Allowed upload types
ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".xlsx", ".xls"}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class Message(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]
    use_rag: bool = True


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the single-page frontend."""
    html_path = "static/index.html"
    try:
        with open(html_path, encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="前端文件未找到")


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    流式聊天接口。
    返回 Server-Sent Events (SSE) 格式的文本增量。
    """
    if not request.messages:
        raise HTTPException(status_code=400, detail="消息不能为空")

    # 构建 API 消息列表
    api_messages = [
        {"role": m.role, "content": m.content}
        for m in request.messages
    ]

    # RAG：用最新用户消息检索相关知识并注入 system prompt
    last_user_content = next(
        (m.content for m in reversed(request.messages) if m.role == "user"),
        "",
    )

    if request.use_rag and last_user_content:
        system_prompt = build_rag_system_prompt(BASE_SYSTEM_PROMPT, last_user_content)
    else:
        system_prompt = BASE_SYSTEM_PROMPT

    client = get_client()

    async def event_stream() -> AsyncGenerator[str, None]:
        """生成 SSE 格式的文本增量流。"""
        try:
            async with client.messages.stream(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                messages=api_messages,
            ) as stream:
                async for event in stream:
                    if event.type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            payload = json.dumps(
                                {"type": "text", "text": event.delta.text},
                                ensure_ascii=False,
                            )
                            yield f"data: {payload}\n\n"

                # 发送完成信号
                final = await stream.get_final_message()
                done_payload = json.dumps({
                    "type": "done",
                    "input_tokens": final.usage.input_tokens,
                    "output_tokens": final.usage.output_tokens,
                })
                yield f"data: {done_payload}\n\n"

        except anthropic.AuthenticationError:
            err = json.dumps(
                {"type": "error", "message": "API 认证失败，请检查 ANTHROPIC_AUTH_TOKEN 配置。"},
                ensure_ascii=False,
            )
            yield f"data: {err}\n\n"
        except anthropic.RateLimitError:
            err = json.dumps(
                {"type": "error", "message": "请求频率超限，请稍候再试。"},
                ensure_ascii=False,
            )
            yield f"data: {err}\n\n"
        except anthropic.APIStatusError as exc:
            err = json.dumps(
                {"type": "error", "message": f"API 错误 {exc.status_code}: {exc.message}"},
                ensure_ascii=False,
            )
            yield f"data: {err}\n\n"
        except Exception as exc:
            err = json.dumps(
                {"type": "error", "message": str(exc)},
                ensure_ascii=False,
            )
            yield f"data: {err}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # 禁用 nginx 缓冲，保证流式输出
        },
    )


# ---------------------------------------------------------------------------
# Document management endpoints
# ---------------------------------------------------------------------------

@app.get("/api/documents")
async def list_documents():
    """返回所有已上传文档的元数据。"""
    return {"documents": get_document_list()}


@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    上传 .txt、.md、.pdf、.xlsx 或 .xls 文件。
    自动分块并存入知识库，用于 RAG 检索。
    大文件（chunk 数 > 200）向量化在后台异步进行，上传立即返回。
    """
    filename = file.filename or "unknown"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型 '{ext}'，支持：{', '.join(ALLOWED_EXTENSIONS)}",
        )

    file_bytes = await file.read()
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"文件过大（{len(file_bytes) // 1024} KB），最大 {MAX_UPLOAD_BYTES // 1024} KB",
        )

    if not file_bytes:
        raise HTTPException(status_code=400, detail="上传的文件为空")

    try:
        doc = ingest_document(file_bytes, filename, embed=False)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"文件处理失败: {exc}") from exc

    if _embedding_available() and doc.chunk_count > 0:
        # 立即返回，向量化在后台异步执行，前端轮询 has_embeddings 感知完成
        asyncio.create_task(_bg_embed(doc.doc_id))
        embed_hint = f"（后台向量化中，共 {doc.chunk_count} 块，请稍候…）"
    else:
        embed_hint = "（TF-IDF 模式，未配置 Embedding API）"

    return {
        "doc_id": doc.doc_id,
        "name": doc.name,
        "file_type": doc.file_type,
        "char_count": doc.char_count,
        "chunk_count": doc.chunk_count,
        "has_embeddings": doc.has_embeddings,
        "message": f"'{filename}' 已成功导入，共 {doc.chunk_count} 个文本块 {embed_hint}。",
    }


@app.delete("/api/documents/{doc_id}")
async def remove_document(doc_id: str):
    """删除指定文档及其所有文本块。"""
    if not delete_document(doc_id):
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"message": "文档已删除", "doc_id": doc_id}


@app.post("/api/documents/{doc_id}/re-embed")
async def reembed_document(doc_id: str):
    """
    对已导入的文档重新生成向量索引（子进程后台执行，立即返回）。
    适用场景：初次导入时 Embedding API 不可用，之后补做向量化。
    """
    if not _embedding_available():
        raise HTTPException(
            status_code=503,
            detail="Embedding API 未配置，请检查 EMBED_API_KEY 和 EMBED_BASE_URL。",
        )
    # 确认文档存在
    docs = get_document_list()
    target = next((d for d in docs if d["doc_id"] == doc_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="文档不存在。")

    # asyncio 后台任务执行，不阻塞服务
    asyncio.create_task(_bg_embed(doc_id))
    return {"message": f"向量化已在后台启动，共 {target['chunk_count']} 块，请稍候查看状态。", "doc_id": doc_id}


# ---------------------------------------------------------------------------
# 诊断接口：同步测试 Embedding API 是否可用，直接返回错误原因
# ---------------------------------------------------------------------------

@app.get("/api/embed-test")
async def embed_test():
    """
    同步测试向量化整条链路，直接返回成功或详细报错。
    用于排查 has_embeddings 始终为 false 的问题。
    """
    from rag import embed_texts, _embedding_available, _chroma_available, _get_chroma_collection

    result: dict = {
        "embedding_api_configured": _embedding_available(),
        "embed_model": EMBED_MODEL,
        "embed_base_url": os.getenv("EMBED_BASE_URL", ""),
        "chroma_available": _chroma_available(),
        "embed_api_ok": False,
        "chroma_write_ok": False,
        "error": None,
    }

    if not result["embedding_api_configured"]:
        result["error"] = "EMBED_API_KEY 或 EMBED_BASE_URL 未配置"
        return result

    # 测试 Embedding API
    loop = asyncio.get_running_loop()
    try:
        vecs = await loop.run_in_executor(None, embed_texts, ["诊断测试文本"])
        result["embed_api_ok"] = True
        result["vector_dim"] = len(vecs[0]) if vecs else 0
    except Exception as exc:
        result["error"] = f"Embedding API 调用失败: {exc}"
        return result

    # 测试 Chroma 写入
    if result["chroma_available"]:
        try:
            col = _get_chroma_collection()
            result["chroma_count_before"] = col.count()
            result["chroma_write_ok"] = True
        except Exception as exc:
            result["error"] = f"Chroma 初始化失败: {exc}"

    return result


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    embed_status = (
        f"enabled (model={EMBED_MODEL}, dims={EMBED_DIMS})"
        if _embedding_available()
        else "disabled (fallback: TF-IDF)"
    )
    return {
        "status": "ok",
        "model": MODEL,
        "base_url": os.getenv("ANTHROPIC_BASE_URL", "default"),
        "embedding": embed_status,
        "chroma": get_chroma_status(),
    }


# ---------------------------------------------------------------------------
# Chroma management endpoints
# ---------------------------------------------------------------------------

@app.get("/api/chroma/status")
async def chroma_status():
    """返回 Chroma 集合的详细状态（可用性、记录数、路径、预览）。"""
    return get_chroma_status()


@app.get("/api/chroma/peek")
async def chroma_peek_endpoint(limit: int = 5):
    """
    抽样预览 Chroma 集合中的前 N 条 chunks。
    可通过 ?limit=N 指定数量（默认 5，最大 20）。
    """
    limit = max(1, min(limit, 20))
    return {"chunks": chroma_peek(limit=limit)}


@app.get("/api/chroma/docs/{doc_id}")
async def chroma_doc_chunks(doc_id: str):
    """查询某文档在 Chroma 中存储的所有 chunks（按字符位置排序）。"""
    chunks = chroma_get_doc_chunks(doc_id)
    if not chunks:
        raise HTTPException(
            status_code=404,
            detail="该文档在 Chroma 中没有找到任何 chunks，可能未向量化或 doc_id 有误。",
        )
    return {"doc_id": doc_id, "count": len(chunks), "chunks": chunks}


@app.delete("/api/chroma/reset")
async def chroma_reset_endpoint():
    """
    清空 Chroma 集合中的所有 chunks（不影响 documents.json 元数据）。
    用于调试或数据迁移，操作不可逆，请谨慎使用。
    """
    deleted = chroma_reset()
    return {"message": f"已清空 Chroma 集合，共删除 {deleted} 条记录。", "deleted": deleted}


# ---------------------------------------------------------------------------
# API数据源管理接口
# ---------------------------------------------------------------------------

@app.get("/api/sources")
async def list_api_sources():
    """获取所有API数据源配置"""
    return {"sources": get_api_sources()}


class ApiSourceCreateRequest(BaseModel):
    name: str
    source_type: str
    api_url: str = ""
    content_path: str = ""
    list_api_url: str = ""
    list_id_path: str = ""
    detail_api_url: str = ""
    detail_content_path: str = ""
    method: str = "GET"
    headers: dict[str, str] = {}
    timeout: int = 30


@app.post("/api/sources")
async def create_api_source(request: ApiSourceCreateRequest):
    """
    创建新的API数据源配置

    source_type:
    - "single": 单接口模式，直接从api_url获取内容
    - "list_detail": 列表+详情模式，先从list_api_url获取ID列表，再逐个调用detail_api_url
    """
    import uuid

    if request.source_type not in ["single", "list_detail"]:
        raise HTTPException(status_code=400, detail="source_type 必须是 'single' 或 'list_detail'")

    if request.source_type == "single" and (not request.api_url or not request.content_path):
        raise HTTPException(status_code=400, detail="单接口模式需要提供 api_url 和 content_path")

    if request.source_type == "list_detail" and (not request.list_api_url or not request.list_id_path or not request.detail_api_url or not request.detail_content_path):
        raise HTTPException(status_code=400, detail="列表+详情模式需要提供 list_api_url, list_id_path, detail_api_url, detail_content_path")

    config = ApiSourceConfig(
        source_id=str(uuid.uuid4()),
        name=request.name,
        source_type=request.source_type,
        api_url=request.api_url,
        content_path=request.content_path,
        list_api_url=request.list_api_url,
        list_id_path=request.list_id_path,
        detail_api_url=request.detail_api_url,
        detail_content_path=request.detail_content_path,
        method=request.method,
        headers=request.headers,
        timeout=request.timeout,
    )

    try:
        add_api_source(config)
        return {"message": "API数据源创建成功", "source_id": config.source_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/sources/{source_id}")
async def update_api_source_endpoint(source_id: str, updates: dict):
    """更新API数据源配置"""
    if not update_api_source(source_id, updates):
        raise HTTPException(status_code=404, detail="数据源不存在")
    return {"message": "更新成功", "source_id": source_id}


@app.delete("/api/sources/{source_id}")
async def delete_api_source_endpoint(source_id: str):
    """删除API数据源"""
    if not delete_api_source(source_id):
        raise HTTPException(status_code=404, detail="数据源不存在")
    return {"message": "删除成功", "source_id": source_id}


@app.post("/api/sources/{source_id}/sync")
async def sync_api_source_endpoint(source_id: str):
    """
    同步API数据源，获取数据并向量化入库
    返回后台异步执行，前端可轮询文档列表查看进度
    """
    result = await sync_api_source(source_id)

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])

    # 对所有新文档启动后台向量化
    if _embedding_available():
        for doc_id in result["doc_ids"]:
            asyncio.create_task(_bg_embed(doc_id))

    return {
        "message": f"成功导入 {result['count']} 条内容，向量化进行中…",
        "count": result["count"],
        "doc_ids": result["doc_ids"],
    }

