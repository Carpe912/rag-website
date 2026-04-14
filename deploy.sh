#!/usr/bin/env bash
# ===========================================================
# 服务器部署脚本 — 智能问答平台
# 目标服务器: 47.116.6.132 | 域名: sunlingyue.cn
# 访问路径: http://sunlingyue.cn/chat/
# 使用方式: bash deploy.sh
# 1===========================================================
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

# ── 2. 确保在应用目录中 ──
echo "📁 准备应用目录: $APP_DIR"
mkdir -p "$APP_DIR"
# 若脚本已在目标目录内运行（如直接 git clone 到服务器），跳过复制
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ "$SCRIPT_DIR" != "$APP_DIR" ]; then
    cp -r . "$APP_DIR/"
fi
cd "$APP_DIR"

# ── 3. 创建虚拟环境并安装依赖 ──
echo "🐍 安装 Python 依赖..."

# 检查 Python 版本（需要 >= 3.8）
PY_VER=$(python3 -c "import sys; print(sys.version_info.minor)" 2>/dev/null || echo "0")
PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)" 2>/dev/null || echo "0")
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_VER" -lt 8 ]; }; then
    echo "❌ Python 版本过低（当前 $(python3 --version 2>&1)），需要 Python 3.8+，请先升级"
    echo "   CentOS/AlmaLinux 参考：dnf install python3.11 -y"
    exit 1
fi
echo "✅ Python 版本：$(python3 --version)"

# 国内镜像安装（阿里云 → 清华 兜底）
PIP_MIRRORS=(
    "https://mirrors.aliyun.com/pypi/simple/"
    "https://pypi.tuna.tsinghua.edu.cn/simple/"
    "https://pypi.mirrors.ustc.edu.cn/simple/"
)

python3 -m venv .venv

echo "  升级 pip..."
for mirror in "${PIP_MIRRORS[@]}"; do
    if .venv/bin/pip install --upgrade pip \
        -i "$mirror" \
        --trusted-host "$(echo $mirror | awk -F/ '{print $3}')" \
        -q 2>/dev/null; then
        echo "  ✅ pip 升级成功（$mirror）"
        break
    fi
done

echo "  安装项目依赖..."
for mirror in "${PIP_MIRRORS[@]}"; do
    if .venv/bin/pip install -r requirements.txt \
        -i "$mirror" \
        --trusted-host "$(echo $mirror | awk -F/ '{print $3}')" \
        -q 2>/dev/null; then
        echo "  ✅ 依赖安装成功（$mirror）"
        break
    fi
    echo "  ⚠️  镜像 $mirror 失败，尝试下一个..."
done

# 验证关键包
echo "  验证关键包..."
for pkg in anthropic fastapi openai sklearn; do
    if .venv/bin/python -c "import $pkg" 2>/dev/null; then
        echo "  ✅ $pkg"
    else
        echo "  ❌ $pkg 导入失败："
        .venv/bin/python -c "import $pkg"
    fi
done

# chromadb 单独验证（需先打 pysqlite3 patch）
if .venv/bin/python - 2>/dev/null <<'PYEOF'
try:
    import pysqlite3, sys
    sys.modules["sqlite3"] = pysqlite3
except ImportError:
    pass
import chromadb
PYEOF
then
    echo "  ✅ chromadb"
else
    echo "  ❌ chromadb 导入失败："
    .venv/bin/python - <<'PYEOF'
try:
    import pysqlite3, sys
    sys.modules["sqlite3"] = pysqlite3
except ImportError:
    pass
import chromadb
PYEOF
fi

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

