# 快速开始 - 高级 RAG 功能

## 一键启动

### 1. 安装新依赖

```bash
pip install rank-bm25>=0.2.2 FlagEmbedding>=1.2.0 jieba
```

或者：

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

编辑 `.env` 文件，添加以下配置：

```bash
# 混合检索（推荐启用）
ENABLE_HYBRID_SEARCH=true

# 查询改写（可选，会增加 API 调用）
ENABLE_QUERY_REWRITE=true

# Reranker 精排（推荐启用）
ENABLE_RERANKER=true
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RERANKER_TOP_K=5

# 父子 Chunk（暂不推荐）
ENABLE_PARENT_CHILD=false
```

### 3. 启动服务

```bash
python main.py
```

**首次启动注意事项**：
- Reranker 模型会自动下载（约 1.5GB）
- 下载时间取决于网络速度
- 如果下载失败，可以设置镜像：`export HF_ENDPOINT=https://hf-mirror.com`

## 验证功能

### 检查配置

```bash
curl http://localhost:8000/api/rag/config
```

预期输出：
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

### 检查健康状态

```bash
curl http://localhost:8000/api/health
```

查看 `advanced_rag` 字段确认功能已启用。

## 测试检索效果

### 1. 上传测试文档

通过前端界面上传一些文档，或使用 API：

```bash
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@test.txt"
```

### 2. 进行查询

在前端聊天界面输入查询，观察日志输出：

```
[QueryRewrite] 生成 3 个查询变体
[BM25] 索引构建完成，共 150 个文档块
[Reranker] 重排序完成，top-5 分数: [0.95, 0.87, 0.82, 0.76, 0.71]
[RAG] 方式=hybrid(bm25+vector+rrf+rerank), 命中=5 块
```

## 性能调优

### 场景 1: 追求最佳效果

```bash
ENABLE_HYBRID_SEARCH=true
ENABLE_QUERY_REWRITE=true
ENABLE_RERANKER=true
```

**特点**: 召回率和准确率最高，但速度较慢，API 成本较高

### 场景 2: 平衡性能和效果（推荐）

```bash
ENABLE_HYBRID_SEARCH=true
ENABLE_QUERY_REWRITE=false
ENABLE_RERANKER=true
```

**特点**: 效果好，速度适中，节省 API 成本

### 场景 3: 追求速度

```bash
ENABLE_HYBRID_SEARCH=false
ENABLE_QUERY_REWRITE=false
ENABLE_RERANKER=false
```

**特点**: 使用传统向量检索，速度最快

## 常见问题

### Q: Reranker 模型下载失败？

```bash
# 使用镜像站
export HF_ENDPOINT=https://hf-mirror.com
python main.py
```

### Q: 内存不足？

关闭 Reranker：
```bash
ENABLE_RERANKER=false
```

### Q: 查询速度太慢？

1. 关闭查询改写：`ENABLE_QUERY_REWRITE=false`
2. 关闭混合检索：`ENABLE_HYBRID_SEARCH=false`

### Q: 如何查看检索使用的方法？

查看日志中的 `[RAG] 方式=` 字段：
- `hybrid(bm25+vector+rrf+rerank)` - 完整混合检索
- `hybrid(bm25+vector+rrf)` - 混合检索（无 Reranker）
- `chroma+embedding+rerank` - 向量检索 + Reranker
- `chroma+embedding` - 纯向量检索
- `tfidf` - TF-IDF 降级

## 动态调整配置

无需重启服务，可以动态调整配置：

```bash
curl -X POST http://localhost:8000/api/rag/config \
  -H "Content-Type: application/json" \
  -d '{
    "hybrid_search": true,
    "query_rewrite": false,
    "reranker": true
  }'
```

**注意**: 动态配置在服务重启后会恢复为 `.env` 中的默认值。

## 下一步

- 阅读 [ADVANCED_RAG_FEATURES.md](./ADVANCED_RAG_FEATURES.md) 了解详细功能
- 阅读 [IMPLEMENTATION_SUMMARY_RAG.md](./IMPLEMENTATION_SUMMARY_RAG.md) 了解实现细节
- 根据实际使用情况调整配置参数

## 技术支持

如遇问题，请查看：
1. 服务日志输出
2. `/api/health` 端点状态
3. `/api/rag/config` 配置信息
