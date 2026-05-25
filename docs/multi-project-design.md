# 多项目知识库隔离设计方案

## 问题描述

当前系统所有文档混在一个知识库中，无法区分不同项目。需要实现：
- 每个项目有独立的知识库
- 用户可以拥有多个项目
- 用户有一个默认项目
- 查询时只检索当前项目的知识

## 核心设计

### 1. 数据模型

#### 1.1 Project（项目）
```python
@dataclass
class Project:
    project_id: str          # 项目唯一ID
    name: str                # 项目名称
    description: str = ""    # 项目描述
    owner_id: str = ""       # 项目所有者ID
    created_at: str = ""     # 创建时间
    updated_at: str = ""     # 更新时间
```

#### 1.2 User（用户）
```python
@dataclass
class User:
    user_id: str                    # 用户ID
    username: str                   # 用户名
    default_project_id: str = ""    # 默认项目ID
    project_ids: list[str] = []     # 用户可访问的项目列表
```

#### 1.3 修改现有模型

**Document 添加 project_id**：
```python
@dataclass
class Document:
    doc_id: str
    name: str
    file_type: str
    char_count: int
    chunk_count: int
    project_id: str = ""        # 🆕 所属项目ID
    has_embeddings: bool = False
    source_url: str = ""
    chunks: list[Chunk] = []
```

**Chunk 添加 project_id**：
```python
@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    doc_name: str
    text: str
    char_start: int
    project_id: str = ""        # 🆕 所属项目ID
    source_url: str = ""
    parent_id: str = ""
    embedding: list[float] = []
```

**ApiSourceConfig 添加 project_id**：
```python
@dataclass
class ApiSourceConfig:
    source_id: str
    name: str
    source_type: str
    project_id: str = ""        # 🆕 所属项目ID
    # ... 其他字段
```

### 2. ChromaDB 隔离策略

有两种方案可选：

#### 方案A：单 Collection + Metadata 过滤（推荐）

**优点**：
- 实现简单，改动最小
- 便于跨项目搜索（如果未来需要）
- 资源占用少

**实现**：
```python
# 写入时添加 project_id 到 metadata
def _chroma_add_chunks(chunks: list[Chunk], embeddings: list[list[float]]) -> None:
    col = _get_chroma_collection()
    col.add(
        ids=[c.chunk_id for c in chunks],
        embeddings=embeddings,
        documents=[c.text for c in chunks],
        metadatas=[
            {
                "doc_id": c.doc_id,
                "doc_name": c.doc_name,
                "project_id": c.project_id,  # 🆕 添加项目ID
                "char_start": c.char_start,
                "parent_id": c.parent_id or "",
            }
            for c in chunks
        ],
    )

# 查询时过滤 project_id
def retrieve_chunks(query: str, project_id: str, top_k: int = 5) -> list[Chunk]:
    col = _get_chroma_collection()
    results = col.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where={"project_id": project_id},  # 🆕 按项目过滤
        include=["documents", "metadatas", "distances"],
    )
    # ...
```

#### 方案B：多 Collection（每个项目一个）

**优点**：
- 物理隔离，更安全
- 性能更好（索引更小）

**缺点**：
- 管理复杂度高
- 资源占用多

**实现**：
```python
def _get_chroma_collection(project_id: str):
    collection_name = f"rag_chunks_{project_id}"
    return _chroma_client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )
```

**推荐使用方案A**，除非：
- 项目数量很少（<10个）且数据量很大
- 有严格的数据隔离要求（如多租户SaaS）

### 3. API 设计

#### 3.1 项目管理接口

```python
# 获取用户的项目列表
GET /api/projects
Response: [
    {
        "project_id": "proj_123",
        "name": "项目A",
        "description": "...",
        "is_default": true,
        "doc_count": 10
    }
]

# 创建项目
POST /api/projects
Body: {"name": "新项目", "description": "..."}

# 切换默认项目
PUT /api/users/me/default-project
Body: {"project_id": "proj_123"}

# 删除项目
DELETE /api/projects/{project_id}
```

#### 3.2 修改现有接口

**所有接口添加 project_id 参数**：

```python
# 对话接口 - 从 Header 或 Query 获取当前项目
POST /api/chat?project_id=proj_123
或
POST /api/chat
Headers: X-Project-ID: proj_123

# 文档上传 - 关联到指定项目
POST /api/documents?project_id=proj_123

# 文档列表 - 只返回当前项目的文档
GET /api/documents?project_id=proj_123

# API数据源 - 关联到项目
POST /api/sources?project_id=proj_123
```

### 4. 前端改造

#### 4.1 项目选择器

在页面顶部添加项目下拉选择器：

```html
<div class="project-selector">
    <select id="projectSelect">
        <option value="proj_123" selected>项目A（默认）</option>
        <option value="proj_456">项目B</option>
    </select>
    <button id="manageProjects">管理项目</button>
</div>
```

#### 4.2 localStorage 存储

```javascript
// 存储当前选中的项目
localStorage.setItem('currentProjectId', 'proj_123');

// 每次请求时带上 project_id
fetch('/api/chat', {
    method: 'POST',
    headers: {
        'X-Project-ID': localStorage.getItem('currentProjectId')
    },
    body: JSON.stringify({...})
});
```

### 5. 实现步骤

#### Phase 1: 数据模型迁移（1-2天）
1. 添加 `Project` 和 `User` 数据模型
2. 修改 `Document`、`Chunk`、`ApiSourceConfig` 添加 `project_id`
3. 编写数据迁移脚本，为现有数据添加默认项目

#### Phase 2: 后端改造（2-3天）
1. 实现项目管理 API（CRUD）
2. 修改 RAG 检索逻辑，添加 `project_id` 过滤
3. 修改文档上传、API数据源同步逻辑
4. 添加用户认证和项目权限校验

#### Phase 3: 前端改造（1-2天）
1. 添加项目选择器组件
2. 修改所有 API 调用，添加 `project_id` 参数
3. 添加项目管理页面

#### Phase 4: 测试和部署（1天）
1. 数据迁移测试
2. 跨项目隔离测试
3. 灰度发布

### 6. 数据迁移脚本示例

```python
# migrate_to_multi_project.py
import json
import uuid
from pathlib import Path

def migrate():
    # 1. 创建默认项目
    default_project = {
        "project_id": "proj_default",
        "name": "默认项目",
        "description": "系统自动创建的默认项目",
        "owner_id": "user_admin",
        "created_at": "2026-05-25T00:00:00Z"
    }
    
    # 2. 为所有现有文档添加 project_id
    docs_file = Path("data/documents.json")
    if docs_file.exists():
        data = json.loads(docs_file.read_text())
        for doc in data.get("documents", []):
            doc["project_id"] = "proj_default"
            for chunk in doc.get("chunks", []):
                chunk["project_id"] = "proj_default"
        docs_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    
    # 3. 更新 ChromaDB metadata
    import chromadb
    client = chromadb.PersistentClient(path="data/chroma")
    collection = client.get_collection("rag_chunks")
    
    # 获取所有现有数据
    all_data = collection.get()
    if all_data["ids"]:
        # 为每个 chunk 添加 project_id
        new_metadatas = []
        for meta in all_data["metadatas"]:
            meta["project_id"] = "proj_default"
            new_metadatas.append(meta)
        
        # 更新 metadata
        collection.update(
            ids=all_data["ids"],
            metadatas=new_metadatas
        )
    
    print("✅ 数据迁移完成")

if __name__ == "__main__":
    migrate()
```

### 7. 安全考虑

#### 7.1 权限校验

```python
def check_project_access(user_id: str, project_id: str) -> bool:
    """检查用户是否有权限访问项目"""
    user = get_user(user_id)
    return project_id in user.project_ids

# 在每个接口中校验
@app.post("/api/chat")
async def chat(request: ChatRequest, user_id: str = Depends(get_current_user)):
    if not check_project_access(user_id, request.project_id):
        raise HTTPException(403, "无权限访问该项目")
    # ...
```

#### 7.2 防止数据泄露

```python
# 确保查询时必须指定 project_id
def retrieve_chunks(query: str, project_id: str, top_k: int = 5):
    if not project_id:
        raise ValueError("必须指定 project_id")
    
    # 使用 where 过滤，而不是查询后过滤
    results = col.query(
        query_embeddings=[...],
        where={"project_id": project_id},  # 在数据库层面过滤
        n_results=top_k
    )
```

### 8. 性能优化

#### 8.1 索引优化

ChromaDB 会自动为 metadata 字段建立索引，但建议：
- 定期清理无用项目的数据
- 监控单个 Collection 的大小（建议 < 100万条）

#### 8.2 缓存策略

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def get_project(project_id: str) -> Project:
    """缓存项目信息"""
    # ...
```

## 总结

**推荐方案**：
- ✅ 使用单 Collection + Metadata 过滤（方案A）
- ✅ 在 Document、Chunk、ApiSourceConfig 中添加 `project_id`
- ✅ 前端添加项目选择器，所有请求带上 `project_id`
- ✅ 后端在检索时强制过滤 `project_id`

**预计工作量**：5-7 个工作日

**风险点**：
- 数据迁移需要停机或灰度
- 需要添加用户认证系统（如果还没有）
- 前端需要处理项目切换时的状态清理
