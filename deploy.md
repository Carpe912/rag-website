# 部署文档 — 智能问答平台

- **服务器 IP**：47.116.6.132
- **访问地址**：http://sunlingyue.cn/chat/
- **部署目录**：/opt/qa-chat
- **服务名称**：qa-chat（systemd）

---

## 一、首次部署（服务器干净环境）

### 第一步：SSH 登录服务器，拉取代码

```bash
# 安装 git（如果没有）
apt-get update && apt-get install -y git

# 克隆代码
git clone <你的仓库地址> /opt/qa-chat
cd /opt/qa-chat
```

### 第二步：写入 .env 配置

```bash
cat > /opt/qa-chat/.env << 'EOF'
# ── Claude 大模型 ──
ANTHROPIC_BASE_URL=https://cursor.scihub.edu.kg/api
ANTHROPIC_AUTH_TOKEN=你的token
CLAUDE_MODEL=claude-opus-4-6

# ── Embedding（qwen3-vl-embedding）──
EMBED_API_KEY=你的dashscope_key
EMBED_BASE_URL=https://ws-zdc9jg0izssetxwv.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
EMBED_MODEL=qwen3-vl-embedding
EMBED_DIMENSIONS=2048

# ── 服务端口 ──
PORT=8000
EOF
```

### 第三步：运行部署脚本

脚本会自动完成：安装系统依赖 → 创建虚拟环境 → 安装 Python 包 → 配置并启动 systemd 服务。

```bash
chmod +x /opt/qa-chat/deploy.sh
bash /opt/qa-chat/deploy.sh
```

### 第四步：配置 Nginx

查看当前 nginx 配置文件位置：

```bash
nginx -t
```

编辑对应的 server{} 配置文件（通常是 `/etc/nginx/sites-enabled/default`），在现有 `location` 块**之前**插入以下内容：

```nginx
# ── 智能问答平台 /chat/ ──
location = /chat {
    return 301 /chat/;
}
location /chat/ {
    rewrite ^/chat(/.*)$ $1 break;
    proxy_pass         http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header   Host              $host;
    proxy_set_header   X-Real-IP         $remote_addr;
    proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header   X-Forwarded-Proto $scheme;
    proxy_set_header   Upgrade           $http_upgrade;
    proxy_set_header   Connection        "upgrade";
    proxy_buffering        off;
    proxy_cache            off;
    proxy_read_timeout     300s;
    proxy_connect_timeout  10s;
    proxy_send_timeout     300s;
    client_max_body_size   25M;
}
```

验证并重载 nginx：

```bash
nginx -t && systemctl reload nginx
```

### 第五步：验证服务

```bash
# 查看服务状态
systemctl status qa-chat

# 实时日志
journalctl -u qa-chat -f

# 测试接口
curl http://localhost:8000/api/health
```

访问 http://sunlingyue.cn/chat/ 确认页面正常加载。

---

## 二、后续更新（手动）

```bash
cd /opt/qa-chat
git pull origin master
.venv/bin/pip install -q -r requirements.txt
systemctl restart qa-chat
```

---

## 三、后续更新（GitHub Actions 自动部署）

每次 push 到 `master` 分支会自动触发部署，无需手动操作。

### 首次配置 GitHub Secrets

进入 GitHub 仓库 → Settings → Secrets and variables → Actions，添加以下 4 个 Secret：

| Secret 名称 | 值 |
|---|---|
| `SERVER_HOST` | `47.116.6.132` |
| `SERVER_USER` | `root` |
| `SERVER_SSH_KEY` | 服务器 SSH 私钥内容（完整 PEM 文本） |
| `SERVER_PORT` | `22` |

### 服务器授权 CI 公钥

将 CI 使用的公钥追加到服务器的授权列表，否则 Actions 无法 SSH 登录：

```bash
echo "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGrpwCAHlxpX6jULPP3c/WH7g3zKizsROggaegLTpsgR github-actions" \
  >> ~/.ssh/authorized_keys
```

配置完成后，push 代码即可触发自动部署，在 GitHub Actions 页面可查看部署日志。

---

## 四、常用运维命令

```bash
# 查看服务状态
systemctl status qa-chat

# 启动 / 停止 / 重启
systemctl start qa-chat
systemctl stop qa-chat
systemctl restart qa-chat

# 实时日志
journalctl -u qa-chat -f

# 查看最近 100 条日志
journalctl -u qa-chat -n 100 --no-pager

# 健康检查接口
curl http://localhost:8000/api/health

# Nginx 重载（修改配置后）
nginx -t && systemctl reload nginx
```

---

## 五、注意事项

- **更换 Embedding 模型后需清空旧向量**：`text-embedding-v3`（1024 维）与 `qwen3-vl-embedding`（2048 维）维度不同，不可混用。切换后执行：
  ```bash
  curl -X DELETE http://localhost:8000/api/chroma/reset
  ```
  然后在页面重新上传文档，或调用 `/api/documents/{doc_id}/re-embed` 逐个重建索引。

- **.env 不会被 git 追踪**（已在 .gitignore 中），每次首次部署需手动写入。

- **SSE 流式输出**依赖 nginx 关闭缓冲（`proxy_buffering off`），配置缺失会导致回答无法实时显示。
