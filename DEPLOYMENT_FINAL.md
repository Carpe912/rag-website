# 高级 RAG 功能 - 最终配置总结

## 已完成的功能

### ✅ 短期功能
1. **混合检索（BM25 + 向量 + RRF 融合）**
2. **查询改写（Claude Haiku 多角度扩展）**

### ✅ 中期功能
3. **父子 Chunk 策略**（数据结构已支持，待完善）
4. **Reranker 精排（阿里百炼 qwen3-rerank API）**

## 重要变更

### 1. Reranker 实现方式
- ❌ **已删除**：本地模型 `bge-reranker-v2-m3`（FlagEmbedding）
- ✅ **使用**：阿里百炼 API `qwen3-rerank`
- **优势**：
  - 无需下载大型模型文件（节省 1.5GB 磁盘空间）
  - 无需额外内存（节省 1-2GB RAM）
  - 部署更快，启动更快
  - 与 Embedding API 使用相同的密钥和配置

### 2. API 配置更新
- **Claude API**：
  - Base URL: `http://118.89.81.103:8081`
  - Token: `sk-f2582742d1626781374d8476763c987b32e85fd8e8911c0ed2f7eff7e9413058`
  - 环境变量：`ANTHROPIC_AUTH_TOKEN`（优先）或 `ANTHROPIC_API_KEY`

### 3. 依赖变更
**新增**：
- `rank-bm25>=0.2.2` - BM25 检索
- `jieba>=0.42.1` - 中文分词

**删除**：
- `FlagEmbedding>=1.2.0` - 不再需要本地 Reranker 模型

## 配置文件

### .env 配置示例

```bash
# ── Claude 大模型（对话和查询改写）──
ANTHROPIC_BASE_URL=http://118.89.81.103:8081
ANTHROPIC_AUTH_TOKEN=sk-f2582742d1626781374d8476763c987b32e85fd8e8911c0ed2f7eff7e9413058
CLAUDE_MODEL=claude-opus-4-6

# ── 阿里云 DashScope Embedding（向量检索和 Rerank）──
EMBED_API_KEY=sk-your_dashscope_key
EMBED_BASE_URL=https://your-host.maas.aliyuncs.com/compatible-mode/v1
EMBED_MODEL=text-embedding-v3
EMBED_DIMENSIONS=1024

# ── 高级 RAG 功能配置 ──
# 混合检索（BM25 + 向量 + RRF 融合）
ENABLE_HYBRID_SEARCH=true

# 查询改写（Claude Haiku 多角度扩展）
ENABLE_QUERY_REWRITE=true

# Reranker 精排（使用阿里百炼 API）
ENABLE_RERANKER=true
RERANKER_MODEL=qwen3-rerank
RERANKER_TOP_K=5

# 父子 Chunk 策略（检索子块，返回父块）
ENABLE_PARENT_CHILD=false

# ── 服务端口 ──
PORT=8000
```

## 部署流程

### 自动部署（推荐）

推送到 master 分支后，GitHub Actions 会自动：
1. 拉取最新代码
2. 安装/更新依赖（包括新增的 `rank-bm25` 和 `jieba`）
3. 重启服务
4. 验证服务状态

### 手动部署

```bash
# 1. 拉取代码
cd /opt/qa-chat
git pull origin master

# 2. 安装依赖
.venv/bin/pip install -r requirements.txt

# 3. 重启服务
systemctl restart qa-chat

# 4. 查看状态
systemctl status qa-chat
journalctl -u qa-chat -f
```

## 验证功能

### 1. 检查配置

```bash
curl http://localhost:8000/api/rag/config
```

预期输出：
```json
{
  "hybrid_search": true,
  "query_rewrite": true,
  "reranker": true,
  "reranker_model": "qwen3-rerank",
  "parent_child": false,
  "embedding_model": "text-embedding-v3",
  "embedding_dims": 1024
}
```

### 2. 检查健康状态

```bash
curl http://localhost:8000/api/health
```

查看 `advanced_rag` 字段确认功能已启用。

### 3. 查看日志

```bash
journalctl -u qa-chat -f
```

成功启用后会看到：
```
[BM25] 索引构建完成，共 150 个文档块
[Reranker] 重排序完成（API），top-5 分数: [0.95, 0.87, 0.82, 0.76, 0.71]
[RAG] 方式=hybrid(bm25+vector+rrf+rerank), 命中=5 块
```

## 性能对比

### 使用 API Reranker vs 本地模型

| 指标 | API 模式 | 本地模型 |
|------|---------|---------|
| 磁盘占用 | 0 | ~1.5GB |
| 内存占用 | 0 | ~1-2GB |
| 首次启动 | 快（秒级） | 慢（需下载模型） |
| 运行速度 | 取决于网络 | 快（本地计算） |
| 成本 | API 调用费用 | 服务器资源 |

### 推荐配置

**生产环境（全部启用，获得最佳效果）**：
```bash
ENABLE_HYBRID_SEARCH=true   # 提升召回率
ENABLE_QUERY_REWRITE=true   # 多角度查询
ENABLE_RERANKER=true        # 提升结果质量
```

**开发/测试环境（同样全部启用）**：
```bash
ENABLE_HYBRID_SEARCH=true
ENABLE_QUERY_REWRITE=true
ENABLE_RERANKER=true
```

## 故障排查

### 问题 1: Reranker API 调用失败

**症状**：日志显示 `[Reranker] API 调用失败，使用降级评分`

**原因**：
- Rerank API 端点配置错误
- API 密钥无效
- 网络连接问题

**解决方案**：
1. 检查 `EMBED_BASE_URL` 和 `EMBED_API_KEY` 配置
2. 确认阿里百炼账户已开通 Rerank 服务
3. 测试网络连接：`curl -H "Authorization: Bearer $EMBED_API_KEY" $EMBED_BASE_URL/rerank`

### 问题 2: BM25 检索不工作

**症状**：日志显示 `[BM25] rank-bm25 未安装`

**解决方案**：
```bash
.venv/bin/pip install rank-bm25 jieba
systemctl restart qa-chat
```

### 问题 3: 查询改写失败

**症状**：日志显示 `[QueryRewrite] Claude API 未配置`

**解决方案**：
1. 检查 `.env` 文件中的 `ANTHROPIC_AUTH_TOKEN` 和 `ANTHROPIC_BASE_URL`
2. 确认 Claude API 可访问：`curl $ANTHROPIC_BASE_URL/health`

## 监控指标

### 关键日志

- `[RAG] 方式=hybrid(bm25+vector+rrf+rerank)` - 使用完整混合检索
- `[QueryRewrite] 生成 3 个查询变体` - 查询改写成功
- `[Reranker] 重排序完成（API）` - Reranker 精排成功
- `[BM25] 索引构建完成` - BM25 索引就绪

### 性能指标

- **检索延迟**：混合检索约 200-500ms（取决于文档数量）
- **Reranker 延迟**：API 调用约 100-300ms
- **查询改写延迟**：Claude API 约 500-1000ms

## 后续优化

1. **缓存机制**：缓存查询改写和 Reranker 结果
2. **批量 Reranking**：优化批处理性能
3. **自定义分词**：支持领域专用词典
4. **A/B 测试**：对比不同检索策略效果

## 文档索引

- [ADVANCED_RAG_FEATURES.md](./ADVANCED_RAG_FEATURES.md) - 详细功能说明
- [QUICKSTART_RAG.md](./QUICKSTART_RAG.md) - 快速开始指南
- [IMPLEMENTATION_SUMMARY_RAG.md](./IMPLEMENTATION_SUMMARY_RAG.md) - 实现总结
- [README.md](./README.md) - 项目总体说明

## 更新日期

2026-05-07

## 版本信息

- 混合检索：v1.0
- 查询改写：v1.0
- Reranker：v1.0（API 模式）
- 父子 Chunk：v0.5（数据结构就绪，待完善）
