#!/usr/bin/env bash
# ===========================================================
# 服务器部署脚本 — 智能问答平台
# 目标服务器: 47.116.6.132 | 域名: sunlingyue.cn
# 访问路径: http://sunlingyue.cn/chat/
# 使用方式: bash deploy.sh
# ===========================================================
set -e

APP_DIR="/opt/qa-chat"
SERVICE_NAME="qa-chat"

echo "🚀 开始部署智能问答平台..."
echo "================================================"

# ── 1. 安装系统依赖 ──
echo "📦 安装系统依赖..."
if command -v apt-get &>/dev/null; then
    apt-get update -qq
    apt-get install -y -qq python3 python3-pip python3-venv curl
elif command -v dnf &>/dev/null; then
    dnf install -y python3 python3-pip curl
elif command -v yum &>/dev/null; then
    yum install -y python3 python3-pip curl
else
    echo "❌ 未找到支持的包管理器（apt/dnf/yum），请手动安装 python3、pip、curl"
    exit 1
fi

# ── 2. 创建应用目录并复制代码 ──
echo "📁 准备应用目录: $APP_DIR"
mkdir -p "$APP_DIR"
cp -r . "$APP_DIR/"
cd "$APP_DIR"

# ── 3. 创建虚拟环境并安装依赖 ──
echo "🐍 安装 Python 依赖..."
python3 -m venv .venv
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q

# ── 4. 确保 .env 存在 ──
if [ ! -f "$APP_DIR/.env" ]; then
  echo "⚠️  未找到 .env 文件，请手动创建："
  echo "     vim $APP_DIR/.env"
  echo "   并填入以下内容："
  echo "     ANTHROPIC_BASE_URL=https://cursor.scihub.edu.kg/api"
  echo "     ANTHROPIC_AUTH_TOKEN=your_token"
  echo "     CLAUDE_MODEL=claude-opus-4-6"
fi

mkdir -p "$APP_DIR/data"
chmod 755 "$APP_DIR/data"

# ── 5. 配置 systemd 服务 ──
echo "⚙️  配置 systemd 服务..."
cp "$APP_DIR/qa-chat.service" "/etc/systemd/system/${SERVICE_NAME}.service"
sed -i "s|WorkingDirectory=.*|WorkingDirectory=$APP_DIR|g" "/etc/systemd/system/${SERVICE_NAME}.service"
sed -i "s|ExecStart=.*|ExecStart=$APP_DIR/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 2|g" "/etc/systemd/system/${SERVICE_NAME}.service"
sed -i "s|EnvironmentFile=.*|EnvironmentFile=$APP_DIR/.env|g" "/etc/systemd/system/${SERVICE_NAME}.service"

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

echo "✅ 服务已启动"
systemctl status "$SERVICE_NAME" --no-pager

# ── 6. 更新 Nginx 配置（只添加 /chat/ 块，不覆盖现有配置）──
echo ""
echo "🌐 Nginx 配置提示："
echo "   请手动将以下内容添加到你现有 server{} 块中（/api/ 和 / 之前）："
echo ""
cat << 'NGINX_SNIPPET'
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
        client_max_body_size   25M;
    }
NGINX_SNIPPET

echo ""
echo "   添加完毕后执行: nginx -t && systemctl reload nginx"
echo ""
echo "================================================"
echo "✅ 部署完成！"
echo ""
echo "🌍 访问地址:"
echo "   http://47.116.6.132/chat/"
echo "   http://sunlingyue.cn/chat/"
echo ""
echo "📋 常用命令:"
echo "   查看日志:    journalctl -u $SERVICE_NAME -f"
echo "   重启服务:    systemctl restart $SERVICE_NAME"
echo "   服务状态:    systemctl status $SERVICE_NAME"
echo "================================================"

