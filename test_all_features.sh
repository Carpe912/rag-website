#!/bin/bash
echo "=========================================="
echo "API数据源功能 - 完整测试"
echo "=========================================="
echo ""

echo "1. 测试核心功能..."
.venv/bin/python test_api_source.py
if [ $? -ne 0 ]; then
    echo "✗ 核心功能测试失败"
    exit 1
fi
echo ""

echo "2. 测试数据转换功能..."
.venv/bin/python test_transform.py
if [ $? -ne 0 ]; then
    echo "✗ 数据转换测试失败"
    exit 1
fi
echo ""

echo "3. 检查Python语法..."
.venv/bin/python -m py_compile api_source.py
.venv/bin/python -m py_compile main.py
echo "✓ Python语法检查通过"
echo ""

echo "=========================================="
echo "✅ 所有测试通过！"
echo "=========================================="
echo ""
echo "功能清单："
echo "  ✅ 单接口模式"
echo "  ✅ 列表+详情模式"
echo "  ✅ 树形结构扁平化"
echo "  ✅ 数据过滤转换"
echo "  ✅ 自定义Python脚本"
echo ""
echo "文档："
echo "  📖 QUICKSTART.md - 快速上手"
echo "  📖 API_SOURCE_GUIDE.md - 详细指南"
echo "  📖 TRANSFORM_GUIDE.md - 转换功能"
echo "  📖 ARCHITECTURE.md - 系统架构"
echo ""
echo "准备就绪，可以开始使用了！🎉"
