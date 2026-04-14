# 智能问答平台

基于 **Claude + RAG（检索增强生成）** 的企业内部知识库问答系统。支持上传文档（Excel、PDF、TXT、Markdown），自动向量化后用于问答检索，回答有据可查。

**线上地址**：https://sunlingyue.cn/chat/

---

## 目录

- [功能特性](#功能特性)
- [技术架构](#技术架构)
- [项目结构](#项目结构)
- [RAG 检索机制](#rag-检索机制)
- [API 接口文档](#api-接口文档)
- [部署指南](#部署指南)
- [环境变量说明](#环境变量说明)
- [常见问题排查](#常见问题排查)
- [后续优化方案](#后续优化方案)

---

## 功能特性

- **流式对话**：基于 Claude API，Server-Sent Events 实时输出
- **多轮上下文**：同一对话内保留完整历史，跨对话相互隔离
- **RAG 知识库**：上传文档后自动分块向量化，问答时自动检索相关内容注入上下文
- **多格式支持**：`.xlsx`、`.xls`、`.pdf`、`.txt`、`.md`，单文件最大 20MB
- **三级检索降级**：Chroma 向量检索 → NumPy 向量检索 → TF-IDF 关键词检索
- **对话历史**：保存在浏览器 localStorage，刷新不丢失
- **文档管理**：支持上传、删除、重新向量化（re-embed）
- **RAG 开关**：前端可随时切换是否启用知识库检索

---

## 技术架构

```
┌─────────────────────────────────────────────────────┐
│                    前端（单页应用）                    │
│  纯 HTML + CSS + JS，无框架依赖                       │
│  对话历史 → localStorage                             │
│  文档列表 → 实时请求服务端 /api/documents             │
└───────────────────┬─────────────────────────────────┘
                    │ HTTP / SSE
┌───────────────────▼─────────────────────────────────┐
│              后端（FastAPI + Uvicorn）                │
│  main.py — 路由、Claude 流式调用、文件上传            │
│  rag.py  — RAG 引擎（分块、向量化、检索）             │
└──────┬───────────────────────────┬───────────────────┘
       │                           │
┌──────▼──────┐           ┌────────▼────────┐
│  Anthropic  │           │  DashScope      │
│  Claude API │           │  Embedding API  │
│  (对话生成) │           │  (文本向量化)    │
└─────────────┘           └────────┬────────┘
                                   │
                          ┌────────▼────────┐
                          │   ChromaDB      │
                          │  (向量持久化)   │
                          │  data/chroma/   │
                          └─────────────────┘
```

**基础设施**：阿里云 ECS + Nginx 反向代理 + systemd 服务管理

---

## 项目结构

```
qa-chat/
├── main.py              # FastAPI 应用入口，所有 HTTP 路由
├── rag.py               # RAG 引擎核心（分块 / 向量化 / 检索）
├── requirements.txt     # Python 依赖
├── static/
│   └── index.html       # 前端单页应用（纯 HTML）
├── data/                # 运行时数据（git 忽略）
│   ├── documents.json   # 文档元数据（不含向量）
│   └── chroma/          # ChromaDB 持久化向量数据
├── .env                 # 环境变量（git 忽略，需手动创建）
├── .env.example         # 环境变量模板
├── deploy.sh            # 一键部署脚本
├── update.sh            # 一键更新脚本
├── run.sh               # 本地启动脚本
├── qa-chat.service      # systemd 服务配置
├── nginx.conf           # Nginx 配置片段
└── deploy.md            # 部署操作文档
```

---

## RAG 检索机制

### 文档处理流程

```
上传文件
  → 解析文本（xlsx/pdf/txt/md）
  → 分块（CHUNK_SIZE=500字，重叠=60字）
  → 批量向量化（DashScope text-embedding-v3，1024维，每批16条）
  → 写入 ChromaDB（余弦距离，HNSW索引）
  → 元数据写入 data/documents.json
```

### 检索优先级（三级降级）

| 优先级 | 方式 | 条件 | 说明 |
|--------|------|------|------|
| 1 | **Chroma + Embedding** | chromadb 已安装 且 Embedding API 可用 | 语义向量检索，余弦距离 < 0.6 才采用 |
| 2 | **NumPy + Embedding** | Embedding API 可用 但 Chroma 不可用 | 向量存于 JSON，NumPy 计算余弦相似度 |
| 3 | **TF-IDF** | Embedding API 不可用 | sklearn 离线关键词检索，无需网络 |

### 分块策略

- 先按双换行（`\n\n`）切段落
- 超过 2000 字的段落按句子（`.!?。！？`）再切
- 每块上限 500 字，相邻块有 60 字重叠保留上下文
- Excel 文件：每行作为独立段落（用 `\n\n` 连接），避免整表被视为一个巨型段落

### 重要参数（rag.py）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `CHUNK_SIZE` | 500 | 单块最大字符数 |
| `CHUNK_OVERLAP` | 60 | 块间重叠字符数 |
| `MAX_CONTEXT_CHUNKS` | 5 | 检索返回最多块数 |
| `EMBED_BATCH` | 16 | 向量化批次大小 |
| `EMBED_DIMS` | 1024 | 向量维度 |

---

## API 接口文档

### 对话

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/chat` | 流式对话（SSE），body: `{messages, use_rag}` |

### 文档管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/documents` | 获取所有文档列表 |
| `POST` | `/api/documents/upload` | 上传文档（multipart/form-data） |
| `DELETE` | `/api/documents/{doc_id}` | 删除文档（同时删除 Chroma 向量） |
| `POST` | `/api/documents/{doc_id}/re-embed` | 对已有文档重新向量化 |

### Chroma 管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/chroma/status` | 查看 Chroma 集合状态（count、路径、预览） |
| `GET` | `/api/chroma/peek?limit=5` | 抽样预览集合中的 chunks |
| `GET` | `/api/chroma/docs/{doc_id}` | 查看某文档在 Chroma 中的所有 chunks |
| `DELETE` | `/api/chroma/reset` | 清空 Chroma 全部向量（不影响元数据） |

### 健康检查

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/health` | 返回服务状态、Embedding 配置、Chroma 状态 |

#### health 返回示例
```json
{
  "status": "ok",
  "model": "claude-opus-4-6",
  "embedding": "enabled (model=text-embedding-v3, dims=1024)",
  "chroma": {
    "available": true,
    "collection": "rag_chunks",
    "count": 42,
    "path": "data/chroma"
  }
}
```

---

## 部署指南

### 环境要求

- Python 3.10+
- Nginx（已有服务）
- systemd
- 服务器可访问 DashScope API（`dashscope.aliyuncs.com`）

### 首次部署

```bash
# 1. 克隆代码
git clone <仓库地址> /opt/qa-chat
cd /opt/qa-chat

# 2. 创建 .env（参考环境变量说明）
cp .env.example .env
vim .env

# 3. 一键部署（创建虚拟环境 + 安装依赖 + 启动 systemd 服务）
chmod +x deploy.sh
bash deploy.sh

# 4. 配置 Nginx（将 nginx.conf 内容合并到现有 server{} 块）
nginx -t && systemctl reload nginx

# 5. 验证
curl http://localhost:8000/api/health
```

### 日常更新

```bash
# 手动更新
bash /opt/qa-chat/update.sh

# 或手动操作
cd /opt/qa-chat
git pull origin master
.venv/bin/pip install -q -r requirements.txt
systemctl restart qa-chat
```

### GitHub Actions 自动部署

每次 push 到 `master` 自动触发部署。配置步骤：

1. 进入仓库 → Settings → Secrets → Actions，添加：

| Secret | 值 |
|--------|----|
| `SERVER_HOST` | 服务器 IP |
| `SERVER_USER` | `root` |
| `SERVER_SSH_KEY` | SSH 私钥完整内容 |
| `SERVER_PORT` | `22` |

2. 将 CI 公钥加入服务器授权：
```bash
echo "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGrpwCAHlxpX6jULPP3c/WH7g3zKizsROggaegLTpsgR github-actions" \
  >> ~/.ssh/authorized_keys
```

### 常用运维命令

```bash
systemctl status qa-chat          # 查看服务状态
systemctl restart qa-chat         # 重启服务
journalctl -u qa-chat -f          # 实时日志
journalctl -u qa-chat -n 100      # 最近 100 条日志
curl localhost:8000/api/health    # 健康检查
```

---

## 环境变量说明

```bash
# ── Claude 大模型（对话生成）──
ANTHROPIC_BASE_URL=https://cursor.scihub.edu.kg/api   # 自定义代理地址（没有则删除）
ANTHROPIC_AUTH_TOKEN=your_token                        # Claude API Token
CLAUDE_MODEL=claude-opus-4-6                           # 使用的模型

# ── 阿里云 DashScope Embedding（向量检索）──
EMBED_API_KEY=sk-your_dashscope_key                    # DashScope API Key
EMBED_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBED_MODEL=text-embedding-v3                          # 向量模型
EMBED_DIMENSIONS=1024                                  # 向量维度（与模型对应）

# ── 服务端口 ──
PORT=8000
```

> ⚠️ **注意**：切换 Embedding 模型后，旧向量维度不兼容，需清空重建：
> ```bash
> curl -X DELETE http://localhost:8000/api/chroma/reset
> # 然后重新上传文档或调用 re-embed
> ```

---

## 常见问题排查

### 文档上传显示「TF-IDF 模式，未向量化」

按以下顺序排查：

**第一步：检查 health 接口**
```bash
curl https://你的域名/api/health
```

**第二步：根据返回结果判断**

| 现象 | 原因 | 解决方法 |
|------|------|---------|
| `embedding: disabled` | `.env` 缺少 `EMBED_API_KEY` 或 `EMBED_BASE_URL` | 补充环境变量后重启 |
| `chroma.available: false`，含 `HNSW` 错误 | ChromaDB 索引文件损坏 | 删除 `data/chroma/` 目录后重启 |
| `chroma.count: 0` 且 embedding enabled | 向量化时 API 调用异常被静默捕获 | 查看服务日志定位具体错误 |
| xlsx 文件 chunk 数量极少（如 5 个） | 行间缺少双换行，整表被视为一个段落，chunk 过大超过 API token 限制 | 已修复（行间改用 `\n\n`） |

**修复损坏的 Chroma**
```bash
systemctl stop qa-chat
rm -rf /opt/qa-chat/data/chroma
systemctl start qa-chat
# 重新向量化已有文档
curl -X POST http://localhost:8000/api/documents/{doc_id}/re-embed
```

**手动测试 Embedding API 是否可用**
```bash
cd /opt/qa-chat && source .venv/bin/activate
python -c "
from rag import embed_texts
result = embed_texts(['测试文本'])
print('✅ 成功，维度:', len(result[0]))
"
```

### Chroma 可用但 count 始终为 0

说明向量写入时抛出了异常（被静默降级）。开启 INFO 日志查看：
```bash
journalctl -u qa-chat -n 200 | grep -E "RAG|向量化|WARNING|ERROR"
```

### 流式输出不实时（等很久才一次性出现）

Nginx 缓冲未关闭。检查配置中是否有：
```nginx
proxy_buffering off;
proxy_cache off;
```

---

## 后续优化方案

当前实现为基础 Naive RAG，以下是按优先级排列的进阶方向：

---

### ⭐⭐⭐ 优先级一：混合检索（BM25 + 向量）

**背景**：当前只有向量检索，对精确数字、编号、专有名词匹配效果差。Excel 数据中大量存在订单号、客户名、金额等精确值，向量语义检索无法准确命中。

**方案**：向量检索（语义）+ BM25（关键词）结果用 RRF 算法融合排序。

```python
from rank_bm25 import BM25Okapi

def hybrid_retrieve(query, top_k=5):
    # 向量检索（语义相似）
    vec_results = chroma_query(embed_query(query), top_k * 2)

    # BM25 检索（关键词精确匹配）
    corpus = [c.text.split() for c in all_chunks]
    bm25 = BM25Okapi(corpus)
    bm25_scores = bm25.get_scores(query.split())
    bm25_top = sorted(enumerate(bm25_scores), key=lambda x: -x[1])[:top_k * 2]

    # RRF 融合（k=60 为经验值）
    return reciprocal_rank_fusion(vec_results, bm25_top, k=60, top_k=top_k)
```

**依赖**：`pip install rank-bm25`

**预期效果**：对 Excel 精确查询准确率大幅提升，尤其是数字/编号类问题。

---

### ⭐⭐⭐ 优先级二：查询改写（Query Rewriting）

**背景**：用户提问往往口语化、模糊，直接用原始问题检索效果不稳定。

**方案**：用 Claude Haiku（成本极低）把用户问题扩展为多个检索角度，多路召回后去重合并。

```python
async def rewrite_query(user_query: str) -> list[str]:
    resp = await claude.messages.create(
        model="claude-haiku-4-5",
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": f"""把以下问题改写为3个不同角度的检索查询，用于搜索知识库。
只输出3行查询，不要其他内容。

原始问题：{user_query}"""
        }]
    )
    queries = resp.content[0].text.strip().split("\n")
    return [user_query] + queries  # 原始 + 改写版本都检索
```

**实现方式**：对多个 query 并行检索，结果去重后合并传给模型。

**预期效果**：模糊/口语化问题的召回率提升 20-40%。

---

### ⭐⭐ 优先级三：父子 Chunk 策略

**背景**：当前 500 字 chunk 在检索时精度够，但传给模型时上下文不完整；增大 chunk 则检索精度下降——两难。

**方案**：维护两个粒度的 chunk，小 chunk 用于检索，检索命中后取对应的父 chunk 传给模型。

```python
# 存储阶段
small_chunks = split(text, size=150)   # 检索用（精准定位）
parent_chunks = split(text, size=800)  # 回答用（上下文完整）

# 检索阶段
small_hit = chroma_query(q_vec, top_k)           # 用小 chunk 检索
parent_ids = [map_to_parent(c) for c in small_hit]  # 映射到父 chunk
context = fetch_parent_chunks(parent_ids)         # 取完整上下文
```

**预期效果**：在不降低检索精度的前提下，模型获得更完整的上下文，回答质量提升。

---

### ⭐⭐ 优先级四：Reranker 精排

**背景**：向量检索召回 top-20，但排序不够准确，相关性最高的结果未必排第一。

**方案**：召回阶段扩大范围（top-20），再用 Cross-Encoder 模型精排取 top-5。

```python
from sentence_transformers import CrossEncoder

reranker = CrossEncoder("BAAI/bge-reranker-v2-m3")

def rerank(query: str, candidates: list[dict], top_k: int = 5) -> list[dict]:
    pairs = [(query, c["text"]) for c in candidates]
    scores = reranker.predict(pairs)
    ranked = sorted(zip(scores, candidates), key=lambda x: -x[0])
    return [c for _, c in ranked[:top_k]]
```

**依赖**：需服务器额外部署 Reranker 模型（~500MB），对内存有一定要求。

**预期效果**：检索准确率提升 15-30%，尤其对长文档效果明显。

---

### ⭐ 优先级五：Self-RAG（按需检索）

**背景**：并非所有问题都需要检索知识库（如「帮我写一首诗」），无谓检索浪费资源且可能干扰回答。

**方案**：先用小模型判断是否需要检索，再决定是否调用 RAG 流程。

```python
async def need_retrieval(query: str) -> bool:
    """判断问题是否需要查阅知识库"""
    resp = await claude.messages.create(
        model="claude-haiku-4-5",
        max_tokens=10,
        messages=[{
            "role": "user",
            "content": f"以下问题是否需要查阅企业内部文档才能回答？只回答 yes 或 no。\n问题：{query}"
        }]
    )
    return "yes" in resp.content[0].text.lower()
```

---

### ⭐ 优先级六：结构化元数据过滤

**背景**：知识库文档较多时，检索前先按文档类型/时间范围过滤，缩小检索范围，提升精度和速度。

**方案**：上传文档时打标签，检索时支持条件过滤。

```python
# 存储时加元数据
col.add(
    embeddings=embeddings,
    metadatas=[{
        "doc_id":    c.doc_id,
        "doc_name":  c.doc_name,
        "file_type": "xlsx",
        "upload_date": "2024-01",
        "department": "销售部",
    }]
)

# 检索时过滤（只搜特定部门的文档）
col.query(
    query_embeddings=[q_vec],
    where={"department": {"$eq": "销售部"}},
    n_results=5
)
```

---

### 优化路线图

```
现状（已完成）
  ✅ 向量检索（ChromaDB + text-embedding-v3）
  ✅ 三级降级（Chroma → NumPy → TF-IDF）
  ✅ xlsx 分块修复（行间双换行）
  ✅ Chroma HNSW 索引损坏修复

近期（推荐优先实施）
  🔲 混合检索（BM25 + 向量 + RRF 融合）
  🔲 查询改写（Claude Haiku 多角度扩展）

中期
  🔲 父子 Chunk 策略
  🔲 Reranker 精排（bge-reranker-v2-m3）

远期
  🔲 Self-RAG（按需检索判断）
  🔲 结构化元数据过滤
  🔲 对话历史迁移至服务端（当前存 localStorage）
  🔲 多用户隔离（当前知识库全局共享）
```

---

## 数据存储说明

| 数据 | 存储位置 | 说明 |
|------|---------|------|
| 文档元数据 | `data/documents.json` | 文档名、chunk数、是否向量化等，不含向量 |
| 向量数据 | `data/chroma/` | ChromaDB 持久化，含 HNSW 索引 |
| 对话历史 | 浏览器 localStorage | 仅存于用户本地，服务端无记录 |
| 环境配置 | `.env` | 不纳入 git 版本管理 |
