#!/usr/bin/env bash
set -e

# ─── 智能问答平台 — 一键启动 ───────────────────────

PYTHON=${PYTHON:-python3}
PORT=${PORT:-8000}

echo "🤖  智能问答平台（RAG 知识库版）"
echo "────────────────────────────────────────"

# 1. 检查 Python 版本（需要 3.9+）
PY_VERSION=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "🐍  Python $PY_VERSION"

# 2. 创建虚拟环境（如果不存在）
if [ ! -d ".venv" ]; then
  echo "📦  创建虚拟环境…"
  $PYTHON -m venv .venv
fi

# 3. 安装/更新依赖
echo "📦  检查依赖…"
.venv/bin/pip install -q -r requirements.txt

# 4. 检查 .env 配置
if [ ! -f ".env" ] && [ -z "$ANTHROPIC_AUTH_TOKEN" ]; then
  echo ""
  echo "⚠️   未找到 API 配置！"
  echo "     请创建 .env 文件："
  echo "       cp .env.example .env"
  echo "       # 编辑 .env，填入 ANTHROPIC_AUTH_TOKEN"
  echo ""
  exit 1
fi

# 5. 确保目录存在
mkdir -p data static

# 6. 启动
echo ""
echo "🚀  启动服务：http://localhost:${PORT}"
echo "    Ctrl+C 停止"
echo ""
.venv/bin/uvicorn main:app --host 0.0.0.0 --port "${PORT}" --reload
