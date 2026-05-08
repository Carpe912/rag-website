# 系统架构

## 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         前端界面 (index.html)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  聊天界面    │  │  文档管理    │  │ API数据源    │          │
│  │              │  │              │  │              │          │
│  │  - 对话列表  │  │  - 上传文档  │  │  - 添加配置  │          │
│  │  - 消息流式  │  │  - 文档列表  │  │  - 同步数据  │          │
│  │  - RAG检索   │  │  - 向量化    │  │  - 状态显示  │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                   │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP/WebSocket
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      后端服务 (FastAPI)                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    main.py (路由层)                        │   │
│  ├──────────────────────────────────────────────────────────┤   │
│  │  /api/chat              - 流式对话                        │   │
│  │  /api/documents         - 文档管理                        │   │
│  │  /api/sources           - 数据源管理                      │   │
│  │  /api/sources/{id}/sync - 数据同步                        │   │
│  └──────────────────────────────────────────────────────────┘   │
│                            │                                      │
│  ┌─────────────────────────┼──────────────────────────────┐     │
│  │                         ▼                               │     │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  │     │
│  │  │   rag.py     │  │ api_source.py│  │  Anthropic  │  │     │
│  │  │              │  │              │  │   Claude    │  │     │
│  │  │ - 文档解析   │  │ - API配置    │  │   API       │  │     │
│  │  │ - 分块处理   │  │ - HTTP请求   │  │             │  │     │
│  │  │ - 向量检索   │  │ - 路径解析   │  │             │  │     │
│  │  │ - RAG增强    │  │ - 数据同步   │  │             │  │     │
│  │  └──────────────┘  └──────────────┘  └─────────────┘  │     │
│  │                                                          │     │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                        数据存储层                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │  documents.json  │  │ api_sources.json │  │   Chroma DB  │  │
│  │                  │  │                  │  │              │  │
│  │  - 文档元数据    │  │  - 数据源配置    │  │  - 向量索引  │  │
│  │  - 分块信息      │  │  - 同步状态      │  │  - 语义检索  │  │
│  └──────────────────┘  └──────────────────┘  └──────────────┘  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## 技术栈

### 前端
- HTML5
- CSS3 (CSS Variables)
- JavaScript (ES6+)
- Marked.js (Markdown渲染)

### 后端
- Python 3.14
- FastAPI (Web框架)
- httpx (HTTP客户端)
- Anthropic SDK (Claude API)
- ChromaDB (向量数据库)
- rank-bm25 (BM25检索)
- jieba (中文分词)

### 存储
- JSON (配置和元数据)
- ChromaDB (向量索引)

### 基础设施
- 阿里云 ECS
- Nginx 反向代理
- systemd 服务管理

## 核心模块

### main.py - 应用入口
FastAPI 应用主文件，包含所有 HTTP 路由：
- `/api/chat` - 流式对话
- `/api/documents` - 文档管理
- `/api/sources` - API数据源管理
- `/api/rag/config` - RAG配置管理
- `/api/health` - 健康检查

### rag.py - RAG引擎
核心功能：
- `ingest_document()` - 文档入库和分块
- `re_embed_document()` - 向量化
- `retrieve_context()` - 混合检索（BM25 + 向量 + RRF融合）
- `embed_texts()` - 调用Embedding API
- `rewrite_query()` - 查询改写
- `rerank_results()` - Reranker精排

### api_source.py - API数据源
API数据源核心模块：
- `ApiSourceConfig` - 数据源配置模型
- `fetch_api_data()` - HTTP请求
- `_get_nested_value()` - JSON路径解析
- `sync_api_source()` - 数据同步
- 配置管理（add/update/delete）

## 数据流程

### 1. 文档上传流程

```
用户上传文件
  → 解析文本（xlsx/pdf/txt/md）
  → 分块（CHUNK_SIZE=500字，重叠=60字）
  → 批量向量化（DashScope text-embedding-v3，1024维）
  → 写入 ChromaDB（余弦距离，HNSW索引）
  → 元数据写入 data/documents.json
```

### 2. API数据源同步流程

```
用户点击"同步"
  → POST /api/sources/{id}/sync
  → api_source.sync_api_source()
    → 加载配置
    → fetch_api_data()
      ├─ 单接口模式: HTTP GET → 提取内容
      └─ 列表+详情模式: 
         ├─ HTTP GET 列表接口
         ├─ 提取ID列表
         └─ 逐个调用详情接口
    → 遍历内容
      → rag.ingest_document()
        ├─ 文本分块
        └─ 保存元数据
    → 返回文档ID列表
  → 后台向量化
    → asyncio.create_task(_bg_embed())
      → rag.re_embed_document()
        ├─ 调用Embedding API
        └─ 写入Chroma DB
```

### 3. 对话检索流程

```
用户提问
  ↓
查询改写（生成 3 个查询变体）
  ↓
并行检索：
  ├─ BM25 关键词检索
  └─ 向量语义检索（每个查询变体）
  ↓
RRF 融合（合并所有检索结果）
  ↓
Reranker 精排（取 top-K）
  ↓
父子 Chunk 扩展（可选）
  ↓
注入 Claude 上下文
  ↓
流式返回回答
```

## 配置存储结构

### documents.json
```json
{
  "documents": [
    {
      "doc_id": "uuid-1234",
      "name": "产品手册.pdf",
      "file_type": "pdf",
      "upload_time": "2026-05-07T10:30:00",
      "chunks": 42,
      "embedded": true
    }
  ]
}
```

### api_sources.json
```json
{
  "sources": [
    {
      "source_id": "uuid-1234",
      "name": "帮助中心文档",
      "source_type": "single",
      "api_url": "https://api.example.com/content",
      "content_path": "results.content",
      "method": "GET",
      "headers": {},
      "timeout": 30,
      "enabled": true,
      "last_sync_time": "2026-04-16T10:30:00",
      "last_sync_count": 15
    }
  ]
}
```

## 检索降级策略

系统会根据可用资源自动降级：

| 优先级 | 方式 | 条件 | 说明 |
|--------|------|------|------|
| 1 | **混合检索（BM25 + 向量 + RRF）** | 所有功能启用 | 最佳效果 |
| 2 | **Chroma + Embedding** | chromadb 已安装 且 Embedding API 可用 | 语义向量检索 |
| 3 | **NumPy + Embedding** | Embedding API 可用 但 Chroma 不可用 | 向量存于 JSON |
| 4 | **TF-IDF** | Embedding API 不可用 | sklearn 离线关键词检索 |

## 项目结构

```
rag-website/
├── main.py              # FastAPI 应用入口
├── rag.py               # RAG 引擎核心
├── api_source.py        # API 数据源模块
├── requirements.txt     # Python 依赖
├── static/
│   └── index.html       # 前端单页应用
├── data/                # 运行时数据
│   ├── documents.json   # 文档元数据
│   ├── api_sources.json # API数据源配置
│   └── chroma/          # ChromaDB 持久化
├── docs/                # 项目文档
│   ├── architecture.md  # 系统架构（本文档）
│   ├── features.md      # 功能说明
│   ├── deployment.md    # 部署指南
│   └── quickstart.md    # 快速开始
├── .env                 # 环境变量
├── .env.example         # 环境变量模板
├── deploy.sh            # 一键部署脚本
├── update.sh            # 一键更新脚本
├── run.sh               # 本地启动脚本
├── qa-chat.service      # systemd 服务配置
└── nginx.conf           # Nginx 配置片段
```
