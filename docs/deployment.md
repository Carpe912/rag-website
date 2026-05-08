# 部署指南

## 环境要求

- Python 3.10+
- Nginx（已有服务）
- systemd
- 服务器可访问 DashScope API（`dashscope.aliyuncs.com`）

---

## 环境变量配置

创建 `.env` 文件（参考 `.env.example`）：

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

> ⚠️ **注意**：切换 Embedding 模型后，旧向量维度不兼容，需清空重建：
> ```bash
> curl -X DELETE http://localhost:8000/api/chroma/reset
> # 然后重新上传文档或调用 re-embed
> ```

---

## 首次部署

### 方法1：一键部署脚本（推荐）

```bash
# 1. 克隆代码
git clone <仓库地址> /opt/qa-chat
cd /opt/qa-chat

# 2. 创建 .env
cp .env.example .env
vim .env  # 填写实际配置

# 3. 一键部署（创建虚拟环境 + 安装依赖 + 启动 systemd 服务）
chmod +x deploy.sh
bash deploy.sh

# 4. 配置 Nginx（将 nginx.conf 内容合并到现有 server{} 块）
nginx -t && systemctl reload nginx

# 5. 验证
curl http://localhost:8000/api/health
```

### 方法2：手动部署

```bash
# 1. 克隆代码
git clone <仓库地址> /opt/qa-chat
cd /opt/qa-chat

# 2. 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 创建 .env
cp .env.example .env
vim .env

# 5. 创建数据目录
mkdir -p data

# 6. 配置 systemd 服务
sudo cp qa-chat.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable qa-chat
sudo systemctl start qa-chat

# 7. 配置 Nginx
# 将 nginx.conf 内容合并到现有配置
sudo nginx -t && sudo systemctl reload nginx

# 8. 验证
systemctl status qa-chat
curl http://localhost:8000/api/health
```

---

## 日常更新

### 方法1：使用更新脚本

```bash
bash /opt/qa-chat/update.sh
```

### 方法2：手动更新

```bash
cd /opt/qa-chat
git pull origin master
.venv/bin/pip install -q -r requirements.txt
systemctl restart qa-chat
systemctl status qa-chat
```

---

## GitHub Actions 自动部署

每次 push 到 `master` 自动触发部署。

### 配置步骤

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

### 工作流程

1. 推送代码到 master 分支
2. GitHub Actions 自动执行：
   - SSH 连接到服务器
   - 拉取最新代码
   - 安装/更新依赖
   - 重启服务
   - 验证服务状态

---

## 部署包方式（适用于 Git 访问受限）

### 步骤1：创建部署包（本地执行）

```bash
cd /Users/coopwire-test/remote-project/rag-website
./create_deploy_package.sh
```

会生成：`api-source-deploy-YYYYMMDD-HHMMSS.tar.gz` (约60KB)

### 步骤2：上传到服务器

```bash
scp api-source-deploy-*.tar.gz user@your-server:/tmp/
```

### 步骤3：在服务器上部署

```bash
# SSH登录服务器
ssh user@your-server

# 进入项目目录
cd /opt/qa-chat

# 备份现有文件
cp main.py main.py.backup
cp static/index.html static/index.html.backup

# 解压部署包
tar -xzf /tmp/api-source-deploy-*.tar.gz --strip-components=1

# 设置权限
chmod +x test_*.sh deploy_with_retry.sh

# 安装依赖
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

# 重启服务
sudo systemctl restart qa-chat

# 验证
sudo systemctl status qa-chat
```

---

## 常用运维命令

```bash
# 查看服务状态
systemctl status qa-chat

# 重启服务
systemctl restart qa-chat

# 停止服务
systemctl stop qa-chat

# 启动服务
systemctl start qa-chat

# 实时日志
journalctl -u qa-chat -f

# 最近 100 条日志
journalctl -u qa-chat -n 100

# 健康检查
curl localhost:8000/api/health

# 查看 RAG 配置
curl localhost:8000/api/rag/config

# 查看 Chroma 状态
curl localhost:8000/api/chroma/status
```

---

## Nginx 配置

将以下内容添加到 Nginx 配置的 `server {}` 块中：

```nginx
location /chat/ {
    proxy_pass http://127.0.0.1:8000/;
    proxy_http_version 1.1;
    
    # SSE 流式输出必需配置
    proxy_buffering off;
    proxy_cache off;
    proxy_set_header Connection '';
    chunked_transfer_encoding off;
    
    # 超时设置
    proxy_read_timeout 300s;
    proxy_connect_timeout 75s;
    
    # 请求头转发
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

重载 Nginx：
```bash
nginx -t && systemctl reload nginx
```

---

## 验证部署

### 1. 检查服务状态

```bash
systemctl status qa-chat
```

预期输出：
```
● qa-chat.service - QA Chat Service
   Loaded: loaded (/etc/systemd/system/qa-chat.service; enabled)
   Active: active (running) since ...
```

### 2. 检查健康状态

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

### 3. 检查日志

```bash
journalctl -u qa-chat -f
```

成功启用后会看到：
```
[BM25] 索引构建完成，共 0 个文档块
[Reranker] 重排序完成（API），top-5 分数: [...]
[RAG] 方式=hybrid(bm25+vector+rrf+rerank), 命中=5 块
```

---

## 常见问题排查

### 问题1：文档上传显示「TF-IDF 模式，未向量化」

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

### 问题2：Chroma 可用但 count 始终为 0

说明向量写入时抛出了异常（被静默降级）。开启 INFO 日志查看：
```bash
journalctl -u qa-chat -n 200 | grep -E "RAG|向量化|WARNING|ERROR"
```

### 问题3：流式输出不实时（等很久才一次性出现）

Nginx 缓冲未关闭。检查配置中是否有：
```nginx
proxy_buffering off;
proxy_cache off;
```

### 问题4：Reranker API 调用失败

**症状**：日志显示 `[Reranker] API 调用失败，使用降级评分`

**原因**：
- Rerank API 端点配置错误
- API 密钥无效
- 网络连接问题

**解决方案**：
1. 检查 `EMBED_BASE_URL` 和 `EMBED_API_KEY` 配置
2. 确认阿里百炼账户已开通 Rerank 服务
3. 测试网络连接：`curl -H "Authorization: Bearer $EMBED_API_KEY" $EMBED_BASE_URL/rerank`

### 问题5：BM25 检索不工作

**症状**：日志显示 `[BM25] rank-bm25 未安装`

**解决方案**：
```bash
.venv/bin/pip install rank-bm25 jieba
systemctl restart qa-chat
```

### 问题6：查询改写失败

**症状**：日志显示 `[QueryRewrite] Claude API 未配置`

**解决方案**：
1. 检查 `.env` 文件中的 `ANTHROPIC_AUTH_TOKEN` 和 `ANTHROPIC_BASE_URL`
2. 确认 Claude API 可访问：`curl $ANTHROPIC_BASE_URL/health`

### 问题7：Git 访问失败

**症状**：
```
fatal: unable to access 'https://github.com/...': Empty reply from server
```

**解决方案**：

1. **使用部署包方式**（推荐）- 见上文"部署包方式"章节

2. **使用改进的部署脚本**：
```bash
cd /opt/qa-chat
./deploy_with_retry.sh
```

3. **修复 Git 访问**：
```bash
# 测试 GitHub 连接
curl -I https://github.com

# 配置代理（如果需要）
git config --global http.proxy http://proxy:port
git config --global https.proxy https://proxy:port

# 或取消代理
git config --global --unset http.proxy
git config --global --unset https.proxy

# 切换到 SSH
git remote set-url origin git@github.com:user/repo.git
```

---

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

---

## 数据备份

### 备份内容

```bash
# 备份文档元数据
cp data/documents.json data/documents.json.backup

# 备份 API 数据源配置
cp data/api_sources.json data/api_sources.json.backup

# 备份向量数据库
tar -czf chroma-backup-$(date +%Y%m%d).tar.gz data/chroma/

# 备份环境配置
cp .env .env.backup
```

### 恢复数据

```bash
# 恢复元数据
cp data/documents.json.backup data/documents.json
cp data/api_sources.json.backup data/api_sources.json

# 恢复向量数据库
tar -xzf chroma-backup-YYYYMMDD.tar.gz

# 重启服务
systemctl restart qa-chat
```

---

## 性能优化

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

### 资源占用

| 组件 | 内存占用 | 磁盘占用 | 说明 |
|------|---------|---------|------|
| FastAPI 服务 | ~200MB | - | 基础服务 |
| ChromaDB | ~100MB | 视文档量 | 向量数据库 |
| BM25 索引 | ~50MB | - | 关键词检索 |
| Reranker (API) | 0 | 0 | 使用远程 API |

---

## 安全建议

1. **环境变量保护**：`.env` 文件权限设置为 600
```bash
chmod 600 .env
```

2. **API 密钥管理**：定期轮换 API 密钥

3. **Nginx 配置**：启用 HTTPS
```nginx
listen 443 ssl http2;
ssl_certificate /path/to/cert.pem;
ssl_certificate_key /path/to/key.pem;
```

4. **防火墙规则**：只开放必要端口
```bash
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

---

## 更新日志

- **2026-05-07**：添加高级 RAG 功能（混合检索、查询改写、Reranker）
- **2026-04-16**：添加 API 数据源功能
- **2026-04-14**：初始版本发布
