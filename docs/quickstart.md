# 快速开始

## 5 分钟快速上手

### 1. 安装依赖

```bash
# 克隆项目
git clone <仓库地址>
cd rag-website

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填写必要配置
vim .env
```

最小配置：
```bash
# Claude API（必需）
ANTHROPIC_AUTH_TOKEN=your_claude_token
CLAUDE_MODEL=claude-opus-4-6

# Embedding API（可选，用于 RAG）
EMBED_API_KEY=your_dashscope_key
EMBED_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBED_MODEL=text-embedding-v3
EMBED_DIMENSIONS=1024
```

### 3. 启动服务

```bash
# 使用启动脚本
./run.sh

# 或手动启动
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 4. 访问应用

打开浏览器访问：http://localhost:8000

---

## 基础功能测试

### 测试对话功能

1. 在对话框输入：`你好，请介绍一下自己`
2. 系统会流式返回 Claude 的回答

### 测试文档上传

1. 点击侧边栏"Knowledge"区域的"上传文档"按钮
2. 选择一个文件（支持 `.xlsx`、`.pdf`、`.txt`、`.md`）
3. 等待上传和向量化完成
4. 在对话中询问文档相关内容

### 测试 API 数据源

1. 点击侧边栏"API数据源"区域的"添加数据源"按钮
2. 填写测试配置：
   ```
   数据源名称: 测试API
   接口类型: 单接口模式
   API地址: https://jsonplaceholder.typicode.com/posts/1
   内容字段路径: body
   ```
3. 点击"保存"
4. 点击"同步"按钮
5. 等待同步完成，文档会出现在"Knowledge"区域

---

## 使用你的 API

### 单接口模式

适用于直接返回内容的 API：

```
数据源名称: 帮助中心文档
接口类型: 单接口模式
API地址: https://api.example.com/content
标题字段路径: results.title（可选）
内容字段路径: results.content
```

### 列表+详情模式

适用于需要先获取列表，再逐个获取详情的 API：

```
数据源名称: 文档库
接口类型: 列表+详情模式
列表接口地址: https://api.example.com/list
ID字段路径: results[].id
标题字段路径: results[].title（可选）
详情接口地址模板: https://api.example.com/detail/{id}
详情内容字段路径: data.content
```

### 字段路径语法

| 路径 | 说明 | 示例 |
|------|------|------|
| `field` | 简单字段 | `content` |
| `field.subfield` | 嵌套字段 | `results.content` |
| `field[].id` | 数组所有元素 | `items[].id` |
| `field[0].id` | 数组指定索引 | `items[0].id` |

---

## 高级 RAG 功能

### 启用混合检索

在 `.env` 中添加：
```bash
ENABLE_HYBRID_SEARCH=true
```

混合检索结合 BM25 关键词检索和向量语义检索，提升召回率。

### 启用查询改写

在 `.env` 中添加：
```bash
ENABLE_QUERY_REWRITE=true
```

使用 Claude Haiku 将用户查询改写为多个角度，提升检索效果。

### 启用 Reranker 精排

在 `.env` 中添加：
```bash
ENABLE_RERANKER=true
RERANKER_MODEL=qwen3-rerank
RERANKER_TOP_K=5
```

使用阿里百炼 API 对检索结果进行精排，提升结果质量。

### 完整配置示例

```bash
# ── Claude 大模型 ──
ANTHROPIC_BASE_URL=http://118.89.81.103:8081
ANTHROPIC_AUTH_TOKEN=your_token
CLAUDE_MODEL=claude-opus-4-6

# ── Embedding API ──
EMBED_API_KEY=your_dashscope_key
EMBED_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBED_MODEL=text-embedding-v3
EMBED_DIMENSIONS=1024

# ── 高级 RAG 功能 ──
ENABLE_HYBRID_SEARCH=true
ENABLE_QUERY_REWRITE=true
ENABLE_RERANKER=true
RERANKER_MODEL=qwen3-rerank
RERANKER_TOP_K=5
ENABLE_PARENT_CHILD=false
```

---

## 运行测试

### 测试 API 数据源功能

```bash
./test_api_feature.sh
```

应该看到所有测试通过 ✓

### 测试所有功能

```bash
./test_all_features.sh
```

---

## 验证部署

### 检查健康状态

```bash
curl http://localhost:8000/api/health
```

预期输出：
```json
{
  "status": "ok",
  "model": "claude-opus-4-6",
  "embedding": "enabled (model=text-embedding-v3, dims=1024)",
  "chroma": {
    "available": true,
    "count": 0
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

### 检查 RAG 配置

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

---

## 常见问题

### Q: 文档上传后显示「TF-IDF 模式，未向量化」？

**A:** 检查 Embedding API 配置：
1. 确认 `.env` 中有 `EMBED_API_KEY` 和 `EMBED_BASE_URL`
2. 重启服务：`./run.sh`
3. 检查健康状态：`curl http://localhost:8000/api/health`

### Q: 如何测试 API 是否可用？

**A:** 使用浏览器或 curl 测试：
```bash
curl https://your-api.com/endpoint
```
确认返回的 JSON 结构，然后配置正确的字段路径。

### Q: 同步 API 数据源失败？

**A:** 检查以下几点：
1. API 地址是否正确
2. 字段路径是否匹配返回数据结构
3. 查看浏览器控制台的错误信息
4. 确认服务器可以访问目标 API

### Q: 如何知道字段路径？

**A:** 
1. 用浏览器访问 API 查看返回 JSON
2. 或使用 Postman 测试
3. 根据 JSON 结构配置路径

### Q: 支持认证吗？

**A:** 当前版本暂不支持，后续版本会添加自定义请求头功能。

### Q: 可以定时同步吗？

**A:** 当前需要手动点击同步，定时同步功能在规划中。

---

## 下一步

- 📖 查看 [功能说明](./features.md) 了解详细功能
- 🏗️ 查看 [系统架构](./architecture.md) 了解技术架构
- 🚀 查看 [部署指南](./deployment.md) 了解生产部署

---

## 功能特性

✅ 流式对话（Claude API）  
✅ 多轮上下文  
✅ RAG 知识库检索  
✅ 多格式文档支持（xlsx/pdf/txt/md）  
✅ API 数据源同步  
✅ 混合检索（BM25 + 向量）  
✅ 查询改写  
✅ Reranker 精排  
✅ 三级检索降级  
✅ 对话历史保存  

---

**祝使用愉快！** 🎉
