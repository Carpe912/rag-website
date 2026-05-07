# 高级 RAG 功能说明

本文档介绍项目中新增的高级 RAG（检索增强生成）功能。

## 功能概览

### ✅ 已实现功能

#### 1. 混合检索（Hybrid Search）
- **BM25 关键词检索**：基于词频的传统检索算法，对精确匹配和关键词查询效果好
- **向量语义检索**：使用 Embedding 模型进行语义相似度检索
- **RRF 融合**：Reciprocal Rank Fusion 算法融合多个检索结果，提升召回率和准确性

#### 2. 查询改写（Query Rewriting）
- 使用 Claude Haiku 将用户查询改写为 3 个不同角度的问题
- 多角度查询提升检索召回率
- 自动处理查询歧义和表达多样性

#### 3. Reranker 精排
- 使用 `bge-reranker-v2-m3` 模型对初排结果进行精排
- 基于深度学习的相关性评分
- 显著提升最终返回结果的质量

#### 4. 父子 Chunk 策略
- 使用小块（子块）进行检索，提高匹配精度
- 返回大块（父块）提供更完整的上下文
- 平衡检索精度和上下文完整性

## 配置说明

### 环境变量配置

在 `.env` 文件中添加以下配置：

```bash
# 混合检索（BM25 + 向量 + RRF 融合）
ENABLE_HYBRID_SEARCH=true

# 查询改写（Claude Haiku 多角度扩展）
ENABLE_QUERY_REWRITE=true

# Reranker 精排（bge-reranker-v2-m3）
ENABLE_RERANKER=true
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RERANKER_TOP_K=5

# 父子 Chunk 策略（检索子块，返回父块）
ENABLE_PARENT_CHILD=false
```

### 配置项说明

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `ENABLE_HYBRID_SEARCH` | `true` | 启用混合检索（BM25 + 向量 + RRF） |
| `ENABLE_QUERY_REWRITE` | `true` | 启用查询改写功能 |
| `ENABLE_RERANKER` | `true` | 启用 Reranker 精排 |
| `RERANKER_MODEL` | `BAAI/bge-reranker-v2-m3` | Reranker 模型名称 |
| `RERANKER_TOP_K` | `5` | Reranker 返回的最终结果数量 |
| `ENABLE_PARENT_CHILD` | `false` | 启用父子 Chunk 策略 |

## 依赖安装

新增功能需要以下依赖：

```bash
pip install rank-bm25>=0.2.2
pip install FlagEmbedding>=1.2.0
pip install jieba  # 中文分词（BM25 需要）
```

或直接安装更新后的 requirements.txt：

```bash
pip install -r requirements.txt
```

## API 端点

### 1. 获取 RAG 配置

```http
GET /api/rag/config
```

**响应示例：**
```json
{
  "hybrid_search": true,
  "query_rewrite": true,
  "reranker": true,
  "reranker_model": "BAAI/bge-reranker-v2-m3",
  "parent_child": false,
  "embedding_model": "text-embedding-v3",
  "embedding_dims": 1024
}
```

### 2. 更新 RAG 配置（运行时动态调整）

```http
POST /api/rag/config
Content-Type: application/json

{
  "hybrid_search": true,
  "query_rewrite": true,
  "reranker": true,
  "parent_child": false
}
```

**注意：** 运行时配置在服务重启后会恢复为环境变量中的默认值。

### 3. 健康检查（包含 RAG 配置）

```http
GET /api/health
```

**响应示例：**
```json
{
  "status": "ok",
  "model": "claude-opus-4-6",
  "embedding": "enabled (model=text-embedding-v3, dims=1024)",
  "chroma": {
    "available": true,
    "count": 150
  },
  "advanced_rag": {
    "hybrid_search": true,
    "query_rewrite": true,
    "reranker": true,
    "reranker_model": "BAAI/bge-reranker-v2-m3",
    "parent_child": false
  }
}
```

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
- **缺点**：首次加载模型较慢（约 1-2GB 内存）
- **建议**：
  - 生产环境推荐启用
  - 首次启动会下载模型，需要网络连接
  - 建议使用 GPU 加速（设置 `use_fp16=True`）

### 4. 父子 Chunk
- **优点**：平衡检索精度和上下文完整性
- **缺点**：需要重新处理文档分块
- **建议**：当前版本默认关闭，后续版本完善后再启用

## 监控和调试

### 日志输出

系统会输出详细的检索日志：

```
[QueryRewrite] 生成 3 个查询变体
[BM25] 索引构建完成，共 150 个文档块
[Reranker] 模型加载成功: BAAI/bge-reranker-v2-m3
[Reranker] 重排序完成，top-5 分数: [0.95, 0.87, 0.82, 0.76, 0.71]
[RAG] 方式=hybrid(bm25+vector+rrf+rerank), 命中=5 块
```

### 性能指标

- **检索方式**：日志中的 `方式=` 字段显示使用的检索策略
- **命中数量**：`命中=N 块` 显示最终返回的文档块数量
- **Reranker 分数**：显示精排后的相关性分数（0-1，越高越相关）

## 常见问题

### Q1: Reranker 模型下载失败？

**A:** 首次使用会从 HuggingFace 下载模型（约 1.5GB）。如果网络不稳定：

```bash
# 方法 1: 使用镜像站
export HF_ENDPOINT=https://hf-mirror.com

# 方法 2: 手动下载模型到本地
# 然后设置 RERANKER_MODEL=/path/to/local/model
```

### Q2: 混合检索比单一向量检索慢？

**A:** 是的，混合检索会执行多次检索并融合结果。如果对响应时间要求极高，可以：
- 关闭查询改写（`ENABLE_QUERY_REWRITE=false`）
- 减少 Reranker 候选数量（调整代码中的 `top_k * 2`）

### Q3: 查询改写需要额外的 API 费用吗？

**A:** 是的，每次查询会调用一次 Claude Haiku API。如果成本敏感，可以关闭此功能。

### Q4: 父子 Chunk 策略如何使用？

**A:** 当前版本的父子 Chunk 策略需要重新处理文档。建议等待后续版本完善后再启用。

## 技术细节

### RRF 融合算法

```python
# RRF 公式
score(item) = Σ (1 / (k + rank_i))

# k: 常数，默认 60
# rank_i: 该项在第 i 个排序列表中的排名
```

### BM25 分词策略

- **中文**：使用 jieba 分词
- **英文**：按空格分割
- **混合文本**：同时应用两种策略

### Reranker 工作原理

1. 将查询和每个候选文档组成 `[query, document]` 对
2. 使用 BERT 类模型计算相关性分数
3. 按分数重新排序

## 未来计划

- [ ] 完善父子 Chunk 策略的自动分块逻辑
- [ ] 支持自定义 Reranker 模型
- [ ] 添加检索结果缓存
- [ ] 支持多语言查询改写
- [ ] 添加检索性能分析工具

## 参考资料

- [BM25 算法](https://en.wikipedia.org/wiki/Okapi_BM25)
- [RRF 融合算法](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf)
- [BGE Reranker](https://github.com/FlagOpen/FlagEmbedding)
- [Claude API 文档](https://docs.anthropic.com/)
