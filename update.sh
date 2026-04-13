#!/usr/bin/env bash
# ===========================================================
# 服务器端更新脚本 — 由 GitHub Actions 触发，也可手动执行
# 用法: bash update.sh
# ===========================================================
set -e

APP_DIR="/opt/qa-chat"
SERVICE="qa-chat"

echo "===== [1/4] 拉取最新代码 ====="
cd "$APP_DIR"
# 保留 .env 和 data/ 目录，强制拉取远程代码
git fetch origin master
git reset --hard origin/master

echo "===== [2/4] 安装/更新 Python 依赖 ====="
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

echo "===== [3/4] 重启服务 ====="
systemctl restart "$SERVICE"

echo "===== [4/4] 验证 ====="
sleep 3
if systemctl is-active --quiet "$SERVICE"; then
    echo "✅ 服务运行正常"
    systemctl status "$SERVICE" --no-pager -l
else
    echo "❌ 服务启动失败，最近日志："
    journalctl -u "$SERVICE" -n 50 --no-pager
    exit 1
fi
