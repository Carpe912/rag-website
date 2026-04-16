#!/usr/bin/env python3
"""
API数据源功能测试脚本
"""

import asyncio
import sys
from api_source import (
    ApiSourceConfig,
    add_api_source,
    get_api_sources,
    fetch_api_data,
    _get_nested_value,
)


def test_nested_value_extraction():
    """测试嵌套值提取"""
    print("=== 测试嵌套值提取 ===")

    # 测试数据
    data = {
        "results": {
            "content": "这是内容",
            "items": [
                {"id": "1", "name": "项目1"},
                {"id": "2", "name": "项目2"},
            ]
        }
    }

    tests = [
        ("results.content", "这是内容"),
        ("results.items[].id", ["1", "2"]),
        ("results.items[0].name", "项目1"),
    ]

    for path, expected in tests:
        result = _get_nested_value(data, path)
        status = "✓" if result == expected else "✗"
        print(f"{status} {path} -> {result}")


async def test_api_fetch():
    """测试API获取（需要真实API）"""
    print("\n=== 测试API获取 ===")

    # 示例配置（单接口模式）
    config = ApiSourceConfig(
        source_id="test-1",
        name="测试数据源",
        source_type="single",
        api_url="https://jsonplaceholder.typicode.com/posts/1",
        content_path="body",
        method="GET",
        timeout=10,
    )

    try:
        results = await fetch_api_data(config)
        print(f"✓ 成功获取 {len(results)} 条内容")
        if results:
            print(f"  内容预览: {results[0][:100]}...")
    except Exception as e:
        print(f"✗ 获取失败: {e}")


def test_config_management():
    """测试配置管理"""
    print("\n=== 测试配置管理 ===")

    # 创建测试配置
    config = ApiSourceConfig(
        source_id="test-source-1",
        name="测试API数据源",
        source_type="single",
        api_url="https://api.example.com/content",
        content_path="data.content",
    )

    try:
        add_api_source(config)
        print("✓ 配置创建成功")

        sources = get_api_sources()
        print(f"✓ 当前有 {len(sources)} 个数据源")

        # 清理测试数据
        from api_source import delete_api_source
        delete_api_source(config.source_id)
        print("✓ 测试数据已清理")

    except ValueError as e:
        print(f"✗ 配置管理失败: {e}")


async def main():
    """主测试函数"""
    print("API数据源功能测试\n")

    # 运行测试
    test_nested_value_extraction()
    await test_api_fetch()
    test_config_management()

    print("\n测试完成！")


if __name__ == "__main__":
    asyncio.run(main())
