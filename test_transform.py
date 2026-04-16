#!/usr/bin/env python3
"""
测试数据转换功能（树形结构扁平化）
"""

from api_source import _apply_transform


def test_tree_flatten():
    """测试树形结构扁平化"""
    print("=== 测试树形结构扁平化 ===\n")

    # 模拟树形数据
    tree_data = [
        {
            "id": "1",
            "name": "根节点1",
            "children": [
                {
                    "id": "1-1",
                    "name": "子节点1-1",
                    "children": [
                        {"id": "1-1-1", "name": "孙节点1-1-1", "children": []}
                    ]
                },
                {"id": "1-2", "name": "子节点1-2", "children": []}
            ]
        },
        {
            "id": "2",
            "name": "根节点2",
            "children": [
                {"id": "2-1", "name": "子节点2-1", "children": []}
            ]
        }
    ]

    # 转换脚本
    transform_script = """
def flatten_tree(node, result_list):
    # 添加当前节点
    result_list.append({
        'id': node.get('id'),
        'name': node.get('name')
    })
    # 递归处理子节点
    if 'children' in node and node['children']:
        for child in node['children']:
            flatten_tree(child, result_list)

result = []
if isinstance(data, list):
    for item in data:
        flatten_tree(item, result)
else:
    flatten_tree(data, result)
"""

    print("原始树形数据：")
    print(f"根节点数量: {len(tree_data)}")
    print(f"第一个根节点: {tree_data[0]['name']}")
    print(f"  子节点数量: {len(tree_data[0]['children'])}")
    print()

    # 应用转换
    try:
        flattened = _apply_transform(tree_data, transform_script)
        print("✓ 转换成功！")
        print(f"扁平化后节点数量: {len(flattened)}")
        print("\n扁平化结果：")
        for item in flattened:
            print(f"  - {item['id']}: {item['name']}")

        # 验证
        expected_count = 6  # 1 + 1-1 + 1-1-1 + 1-2 + 2 + 2-1
        if len(flattened) == expected_count:
            print(f"\n✓ 验证通过：扁平化后有 {expected_count} 个节点")
        else:
            print(f"\n✗ 验证失败：期望 {expected_count} 个节点，实际 {len(flattened)} 个")

    except Exception as e:
        print(f"✗ 转换失败: {e}")


def test_simple_transform():
    """测试简单数据转换"""
    print("\n=== 测试简单数据转换 ===\n")

    data = {
        "items": [
            {"id": 1, "value": 10},
            {"id": 2, "value": 20},
            {"id": 3, "value": 30}
        ]
    }

    # 提取ID列表
    script = """
result = [item['id'] for item in data['items']]
"""

    try:
        result = _apply_transform(data, script)
        print(f"原始数据: {data}")
        print(f"转换结果: {result}")
        if result == [1, 2, 3]:
            print("✓ 验证通过")
        else:
            print("✗ 验证失败")
    except Exception as e:
        print(f"✗ 转换失败: {e}")


def test_filter_transform():
    """测试过滤转换"""
    print("\n=== 测试过滤转换 ===\n")

    data = [
        {"id": 1, "status": "active"},
        {"id": 2, "status": "inactive"},
        {"id": 3, "status": "active"},
        {"id": 4, "status": "inactive"}
    ]

    # 只保留active状态的项
    script = """
result = [item for item in data if item['status'] == 'active']
"""

    try:
        result = _apply_transform(data, script)
        print(f"原始数据: {len(data)} 项")
        print(f"过滤后: {len(result)} 项")
        print(f"结果: {result}")
        if len(result) == 2:
            print("✓ 验证通过")
        else:
            print("✗ 验证失败")
    except Exception as e:
        print(f"✗ 转换失败: {e}")


if __name__ == "__main__":
    print("数据转换功能测试\n")
    test_tree_flatten()
    test_simple_transform()
    test_filter_transform()
    print("\n测试完成！")
