#!/bin/bash
# 部署脚本 - 带错误处理和重试机制

set -e  # 遇到错误立即退出

SERVICE="qa-chat"
REPO_URL="https://github.com/Carpe912/rag-website.git"
MAX_RETRIES=3

echo "=========================================="
echo "RAG网站部署脚本"
echo "=========================================="
echo ""

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 函数：带重试的Git操作
git_pull_with_retry() {
    local retries=0
    while [ $retries -lt $MAX_RETRIES ]; do
        echo "尝试拉取代码 (${retries}/${MAX_RETRIES})..."

        if git pull origin master; then
            echo -e "${GREEN}✓ 代码拉取成功${NC}"
            return 0
        fi

        retries=$((retries + 1))
        if [ $retries -lt $MAX_RETRIES ]; then
            echo -e "${YELLOW}⚠ 拉取失败，5秒后重试...${NC}"
            sleep 5
        fi
    done

    echo -e "${RED}✗ Git拉取失败，已重试${MAX_RETRIES}次${NC}"
    return 1
}

# 步骤1: 拉取代码
echo "===== [1/4] 拉取最新代码 ====="
if git_pull_with_retry; then
    echo "代码更新完成"
else
    echo -e "${YELLOW}⚠ Git拉取失败，跳过代码更新（使用本地代码）${NC}"
    echo "如果是网络问题，可以稍后手动执行: git pull origin master"
fi
echo ""

# 步骤2: 安装依赖
echo "===== [2/4] 安装依赖 ====="
if [ -d ".venv" ]; then
    echo "虚拟环境已存在"
else
    echo "创建虚拟环境..."
    python3 -m venv .venv
fi

echo "升级pip..."
.venv/bin/pip install -q --upgrade pip

echo "安装依赖包..."
.venv/bin/pip install -q -r requirements.txt

echo -e "${GREEN}✓ 依赖安装完成${NC}"
echo ""

# 步骤3: 重启服务
echo "===== [3/4] 重启服务 ====="
if systemctl is-active --quiet "$SERVICE"; then
    echo "停止现有服务..."
    sudo systemctl stop "$SERVICE"
fi

echo "启动服务..."
sudo systemctl start "$SERVICE"
echo -e "${GREEN}✓ 服务已启动${NC}"
echo ""

# 步骤4: 验证服务
echo "===== [4/4] 验证服务状态 ====="
sleep 3

if systemctl is-active --quiet "$SERVICE"; then
    echo -e "${GREEN}✅ 服务运行正常${NC}"
    echo ""
    echo "服务状态："
    systemctl status "$SERVICE" --no-pager -l | head -n 10
    echo ""
    echo "最近日志："
    journalctl -u "$SERVICE" -n 10 --no-pager
else
    echo -e "${RED}❌ 服务启动失败${NC}"
    echo ""
    echo "错误日志："
    journalctl -u "$SERVICE" -n 30 --no-pager
    exit 1
fi

echo ""
echo "=========================================="
echo -e "${GREEN}✅ 部署完成！${NC}"
echo "=========================================="
echo ""
echo "访问地址: http://localhost:8000"
echo "查看日志: journalctl -u $SERVICE -f"
echo "重启服务: sudo systemctl restart $SERVICE"
