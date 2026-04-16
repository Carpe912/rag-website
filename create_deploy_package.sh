#!/bin/bash
# 创建部署包 - 用于手动上传到服务器

echo "=========================================="
echo "创建API数据源功能部署包"
echo "=========================================="
echo ""

PACKAGE_NAME="api-source-deploy-$(date +%Y%m%d-%H%M%S).tar.gz"

echo "打包文件..."

# 创建临时目录
TEMP_DIR=$(mktemp -d)
mkdir -p "$TEMP_DIR/rag-website"

# 复制核心文件
echo "  - 核心代码"
cp api_source.py "$TEMP_DIR/rag-website/"
cp main.py "$TEMP_DIR/rag-website/"
cp -r static "$TEMP_DIR/rag-website/"

# 复制测试文件
echo "  - 测试脚本"
cp test_api_source.py "$TEMP_DIR/rag-website/"
cp test_transform.py "$TEMP_DIR/rag-website/"
cp test_api_feature.sh "$TEMP_DIR/rag-website/"
cp test_all_features.sh "$TEMP_DIR/rag-website/"

# 复制文档
echo "  - 文档"
cp *.md "$TEMP_DIR/rag-website/" 2>/dev/null || true

# 复制部署脚本
echo "  - 部署脚本"
cp deploy_with_retry.sh "$TEMP_DIR/rag-website/" 2>/dev/null || true

# 创建部署说明
cat > "$TEMP_DIR/rag-website/DEPLOY_README.txt" << 'EOF'
API数据源功能部署包
==================

部署步骤：
---------

1. 上传此压缩包到服务器
   scp api-source-deploy-*.tar.gz user@server:/path/to/

2. SSH登录服务器
   ssh user@server

3. 解压到项目目录
   cd /path/to/rag-website
   tar -xzf /path/to/api-source-deploy-*.tar.gz --strip-components=1

4. 备份现有文件（可选但推荐）
   cp main.py main.py.backup
   cp static/index.html static/index.html.backup

5. 设置执行权限
   chmod +x test_*.sh deploy_with_retry.sh

6. 安装依赖
   .venv/bin/pip install -q --upgrade pip
   .venv/bin/pip install -q -r requirements.txt

7. 测试功能（可选）
   .venv/bin/python test_api_source.py
   .venv/bin/python test_transform.py

8. 重启服务
   sudo systemctl restart qa-chat

9. 验证服务
   sudo systemctl status qa-chat
   journalctl -u qa-chat -n 20

10. 访问界面
    http://your-server:8000

新增功能：
---------
✓ API数据源管理
✓ 单接口模式
✓ 列表+详情模式
✓ 树形结构扁平化
✓ 数据转换脚本

文档：
-----
- QUICKSTART.md - 快速上手
- API_SOURCE_GUIDE.md - 详细指南
- TRANSFORM_GUIDE.md - 转换功能
- MANUAL_DEPLOY.md - 手动部署指南

问题排查：
---------
如遇问题，查看：
- journalctl -u qa-chat -n 50
- MANUAL_DEPLOY.md

EOF

# 打包
echo ""
echo "创建压缩包..."
cd "$TEMP_DIR"
tar -czf "$PACKAGE_NAME" rag-website/

# 移动到原始目录
ORIGINAL_DIR="$OLDPWD"
mv "$PACKAGE_NAME" "$ORIGINAL_DIR/"

# 清理临时目录
cd "$ORIGINAL_DIR"
rm -rf "$TEMP_DIR"

echo ""
echo "=========================================="
echo "✅ 部署包创建成功！"
echo "=========================================="
echo ""
echo "文件名: $PACKAGE_NAME"
echo "大小: $(du -h "$PACKAGE_NAME" | cut -f1)"
echo ""
echo "包含文件："
tar -tzf "$PACKAGE_NAME" | head -n 20
echo "..."
echo ""
echo "上传到服务器："
echo "  scp $PACKAGE_NAME user@server:/path/to/"
echo ""
echo "详细部署步骤请查看压缩包内的 DEPLOY_README.txt"
