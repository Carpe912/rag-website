# 智能问答平台

基于 **Claude + RAG（检索增强生成）** 的企业内部知识库问答系统。支持上传文档（Excel、PDF、TXT、Markdown），自动向量化后用于问答检索，回答有据可查。

**线上地址**：https://sunlingyue.cn/chat/

---

## 文档导航

- 📖 [快速开始](docs/quickstart.md) - 5分钟快速上手指南
- 🏗️ [系统架构](docs/architecture.md) - 技术架构和模块说明
- ✨ [功能说明](docs/features.md) - 详细功能介绍和使用指南
- 🚀 [部署指南](docs/deployment.md) - 生产环境部署和运维

## 目录

- [功能特性](#功能特性)
- [技术架构](#技术架构)
- [快速开始](#快速开始)
- [API 接口](#api-接口)
- [环境变量](#环境变量)

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

## 快速开始

### 本地开发

```bash
# 1. 克隆项目
git clone <仓库地址>
cd rag-website

# 2. 安装依赖
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
vim .env  # 填写必要配置

# 4. 启动服务
./run.sh
```

访问：http://localhost:8000

详细说明请查看 [快速开始文档](docs/quickstart.md)

---

## API 接口

### 核心接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/chat` | 流式对话 |
| `GET/POST/DELETE` | `/api/documents` | 文档管理 |
| `GET/POST/DELETE` | `/api/sources` | API数据源管理 |
| `GET/POST` | `/api/rag/config` | RAG配置管理 |
| `GET` | `/api/health` | 健康检查 |

完整 API 文档请查看 [功能说明](docs/features.md)

---

## 环境变量

```bash
# Claude API（必需）
ANTHROPIC_AUTH_TOKEN=your_token
CLAUDE_MODEL=claude-opus-4-6

# Embedding API（可选，用于 RAG）
EMBED_API_KEY=your_dashscope_key
EMBED_MODEL=text-embedding-v3
EMBED_DIMENSIONS=1024

# 高级 RAG 功能
ENABLE_HYBRID_SEARCH=true
ENABLE_QUERY_REWRITE=true
ENABLE_RERANKER=true
```

完整配置说明请查看 [部署指南](docs/deployment.md)
