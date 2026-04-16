#!/bin/bash
# API数据源功能快速测试脚本

echo "==================================="
echo "API数据源功能 - 快速测试"
echo "==================================="
echo ""

# 1. 测试核心功能
echo "1. 测试核心功能..."
.venv/bin/python test_api_source.py
if [ $? -eq 0 ]; then
    echo "✓ 核心功能测试通过"
else
    echo "✗ 核心功能测试失败"
    exit 1
fi

echo ""
echo "2. 检查Python语法..."
.venv/bin/python -m py_compile api_source.py
.venv/bin/python -m py_compile main.py
echo "✓ Python语法检查通过"

echo ""
echo "==================================="
echo "测试完成！"
echo "==================================="
echo ""
echo "下一步："
echo "1. 启动服务器: ./run.sh"
echo "2. 访问: http://localhost:8000"
echo "3. 在侧边栏找到'API数据源'区域"
echo "4. 点击'添加数据源'按钮配置"
echo ""
echo "示例配置（测试用）："
echo "-----------------------------------"
echo "数据源名称: 测试API"
echo "接口类型: 单接口模式"
echo "API地址: https://jsonplaceholder.typicode.com/posts/1"
echo "内容字段路径: body"
echo "-----------------------------------"
echo ""
echo "配置完成后，点击'同步'按钮即可导入数据！"
