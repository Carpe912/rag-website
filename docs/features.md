# 功能说明

## 核心功能

### 1. 智能对话
- **流式输出**：基于 Claude API，Server-Sent Events 实时输出
- **多轮上下文**：同一对话内保留完整历史，跨对话相互隔离
- **对话历史**：保存在浏览器 localStorage，刷新不丢失
- **RAG 开关**：前端可随时切换是否启用知识库检索

### 2. 文档管理
- **多格式支持**：`.xlsx`、`.xls`、`.pdf`、`.txt`、`.md`，单文件最大 20MB
- **自动分块**：智能分段，保留上下文重叠
- **向量化**：自动调用 Embedding API 生成向量
- **文档操作**：上传、删除、重新向量化（re-embed）

### 3. API 数据源
从外部 API 接口批量获取数据并自动向量化入库，无需手动上传文件。

#### 支持模式
1. **单接口模式**：直接从一个 API 获取内容
2. **列表+详情模式**：先获取 ID 列表，再逐个调用详情接口

#### 使用场景
- 从帮助中心 API 同步文档
- 从知识库系统批量导入内容
- 从 CMS 系统获取文章
- 从内部服务获取技术文档

---

## 高级 RAG 功能

### 1. 混合检索（Hybrid Search）
结合 BM25 关键词检索和向量语义检索，使用 RRF 算法融合结果。

**优势**：
- 对精确数字、编号、专有名词匹配效果好
- 语义理解能力强
- 召回率高

**配置**：
```bash
ENABLE_HYBRID_SEARCH=true
```

### 2. 查询改写（Query Rewriting）
使用 Claude Haiku 将用户查询改写为 3 个不同角度的问题，提升检索召回率。

**优势**：
- 处理查询歧义
- 多角度查询
- 提升召回率 20-40%

**配置**：
```bash
ENABLE_QUERY_REWRITE=true
```

### 3. Reranker 精排
使用阿里百炼 `qwen3-rerank` API 模型对初排结果进行精排。

**优势**：
- 基于深度学习的相关性评分
- 显著提升最终返回结果的质量
- 无需下载大型模型文件
- 与 Embedding API 使用相同的密钥

**配置**：
```bash
ENABLE_RERANKER=true
RERANKER_MODEL=qwen3-rerank
RERANKER_TOP_K=5
```

### 4. 父子 Chunk 策略

使用小块（子块）进行检索，返回大块（父块）提供更完整的上下文。

**工作原理**：
1. **创建父块**：大块（1500 字符），包含完整的上下文信息
2. **创建子块**：在每个父块内创建小块（500 字符），用于精确检索
3. **建立映射**：每个子块记录其所属的父块 ID
4. **检索流程**：
   - 使用子块进行向量检索（匹配精度高）
   - 检索到子块后，自动替换为对应的父块
   - 返回父块给模型（上下文完整）

**优势**：
- 检索精度高（小块匹配更精确）
- 上下文完整（大块提供完整信息）
- 平衡精度和完整性

**配置**：
```bash
ENABLE_PARENT_CHILD=true
PARENT_CHUNK_SIZE=1500  # 父块大小（可选，默认 1500）
CHILD_CHUNK_SIZE=500    # 子块大小（可选，默认 500）
```

**示例**：

假设有一篇 3000 字的文档：

```
原始文档（3000 字）
    ↓
创建 2 个父块（每个 1500 字）
    ↓
父块 1（1500 字）
  ├─ 子块 1.1（500 字）
  ├─ 子块 1.2（500 字）
  └─ 子块 1.3（500 字）
    
父块 2（1500 字）
  ├─ 子块 2.1（500 字）
  ├─ 子块 2.2（500 字）
  └─ 子块 2.3（500 字）
```

检索时：
- 用户查询匹配到"子块 1.2"
- 系统自动返回"父块 1"（包含完整上下文）
- 模型获得更完整的信息进行回答

**注意事项**：
- 启用后会增加存储空间（父块 + 子块都会存储）
- 向量化时间会增加（需要为所有块生成向量）
- 建议在文档较长、需要完整上下文时启用

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
| 1 | **混合检索（BM25 + 向量 + RRF）** | 所有功能启用 | 最佳效果，召回率最高 |
| 2 | **Chroma + Embedding** | chromadb 已安装 且 Embedding API 可用 | 语义向量检索，余弦距离 < 0.6 才采用 |
| 3 | **NumPy + Embedding** | Embedding API 可用 但 Chroma 不可用 | 向量存于 JSON，NumPy 计算余弦相似度 |
| 4 | **TF-IDF** | Embedding API 不可用 | sklearn 离线关键词检索，无需网络 |

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

## API 数据源详细说明

### 配置示例

#### 示例1：单接口模式

假设你有一个 API 返回单篇文档：

**API地址：**
```
https://api.example.com/content
```

**返回格式：**
```json
{
  "results": {
    "title": "如何创建议题",
    "content": "这里是markdown格式的文档内容..."
  }
}
```

**配置：**
- 数据源名称：`帮助中心文档`
- 接口类型：`单接口模式`
- API地址：`https://api.example.com/content`
- 标题字段路径：`results.title`（可选）
- 内容字段路径：`results.content`

#### 示例2：列表+详情模式

假设你需要先获取文档列表，再逐个获取详情：

**列表接口：**
```
https://api.example.com/docs/list
```

**列表返回格式：**
```json
{
  "results": [
    {"id": "doc1", "title": "如何创建议题"},
    {"id": "doc2", "title": "如何删除议题"}
  ]
}
```

**详情接口模板：**
```
https://api.example.com/docs/{id}
```

**详情返回格式：**
```json
{
  "data": {
    "content": "这里是markdown格式的文档内容..."
  }
}
```

**配置：**
- 数据源名称：`API文档库`
- 接口类型：`列表+详情模式`
- 列表接口地址：`https://api.example.com/docs/list`
- ID字段路径：`results[].id`
- 标题字段路径：`results[].title`（可选）
- 详情接口地址模板：`https://api.example.com/docs/{id}`
- 详情内容字段路径：`data.content`

### 字段路径语法

支持以下路径格式：

- `field` - 简单字段
- `field.subfield` - 嵌套字段
- `field[].id` - 数组中的字段（提取所有元素的id）
- `field[0].id` - 数组索引（提取第一个元素的id）

**示例：**

数据结构：
```json
{
  "data": {
    "items": [
      {"id": "1", "content": "内容1"},
      {"id": "2", "content": "内容2"}
    ]
  }
}
```

路径示例：
- `data.items[].id` → `["1", "2"]`
- `data.items[0].content` → `"内容1"`
- `data.items[].content` → `["内容1", "内容2"]`

### 使用流程

1. **添加数据源**
   - 点击侧边栏"API数据源"区域的"添加数据源"按钮
   - 填写配置信息
   - 点击"保存"

2. **同步数据**
   - 在数据源列表中找到对应的数据源
   - 点击"同步"按钮（刷新图标）
   - 系统会自动获取数据并向量化入库

3. **查看结果**
   - 同步完成后，文档会出现在"Knowledge"区域
   - 向量化完成后，可以在对话中使用这些知识

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

### API 数据源管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/sources` | 获取数据源列表 |
| `POST` | `/api/sources` | 创建数据源 |
| `PUT` | `/api/sources/{source_id}` | 更新数据源 |
| `DELETE` | `/api/sources/{source_id}` | 删除数据源 |
| `POST` | `/api/sources/{source_id}/sync` | 同步数据源 |

### RAG 配置管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/rag/config` | 获取 RAG 配置 |
| `POST` | `/api/rag/config` | 更新 RAG 配置（运行时动态调整） |

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
| `GET` | `/api/health` | 返回服务状态、Embedding 配置、Chroma 状态、RAG 配置 |

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
  },
  "advanced_rag": {
    "hybrid_search": true,
    "query_rewrite": true,
    "reranker": true,
    "reranker_model": "qwen3-rerank",
    "parent_child": false
  }
}
```

---

## 工作流程

### 标准检索流程（所有功能启用）

```
用户查询
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
返回最终结果
```

### 降级策略

系统会根据可用资源自动降级：

1. **混合检索** → Chroma 向量检索 → NumPy 向量检索 → TF-IDF
2. **查询改写失败** → 使用原始查询
3. **Reranker 失败** → 跳过精排，直接返回初排结果

---

## 性能优化建议

### 1. 混合检索
- **优点**：召回率高，对关键词和语义查询都有效
- **缺点**：计算开销较大
- **建议**：生产环境推荐启用

### 2. 查询改写
- **优点**：提升召回率，处理查询歧义
- **缺点**：增加 API 调用（Claude Haiku）
- **建议**：对查询质量要求高时启用

### 3. Reranker
- **优点**：显著提升结果质量
- **缺点**：增加 API 调用延迟
- **建议**：生产环境推荐启用

### 4. 父子 Chunk
- **优点**：平衡检索精度和上下文完整性
- **缺点**：增加存储空间和向量化时间
- **建议**：文档较长、需要完整上下文时启用

---

## 监控和调试

### 日志输出

系统会输出详细的检索日志：

```
[QueryRewrite] 生成 3 个查询变体
[BM25] 索引构建完成，共 150 个文档块
[Reranker] 重排序完成（API），top-5 分数: [0.95, 0.87, 0.82, 0.76, 0.71]
[RAG] 方式=hybrid(bm25+vector+rrf+rerank), 命中=5 块
```

### 性能指标

- **检索方式**：日志中的 `方式=` 字段显示使用的检索策略
- **命中数量**：`命中=N 块` 显示最终返回的文档块数量
- **Reranker 分数**：显示精排后的相关性分数（0-1，越高越相关）

---

## 注意事项

### API 数据源
1. **API访问权限**：确保API地址可以从服务器访问
2. **数据格式**：内容应为markdown或纯文本格式
3. **性能考虑**：列表+详情模式会逐个调用详情接口，如果列表很长，同步可能需要较长时间
4. **更新策略**：每次同步都会创建新文档，如需更新，建议先删除旧文档再同步

### RAG 配置
1. **运行时配置**：通过 `/api/rag/config` 更新的配置在服务重启后会恢复为环境变量中的默认值
2. **模型切换**：切换 Embedding 模型后，旧向量维度不兼容，需清空重建
3. **Reranker API**：确认阿里百炼账户已开通 Rerank 服务

---

## 未来计划

- [ ] 完善父子 Chunk 策略的自动分块逻辑
- [ ] 支持自定义 Reranker 模型
- [ ] 添加检索结果缓存
- [ ] 支持多语言查询改写
- [ ] 添加检索性能分析工具
- [ ] API 数据源支持自定义 HTTP 请求头（用于认证）
- [ ] API 数据源支持 POST 请求
- [ ] API 数据源定时自动同步
- [ ] API 数据源增量更新（仅同步变更）
