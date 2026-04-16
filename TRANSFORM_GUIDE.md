# 数据转换功能使用指南

## 功能概述

数据转换功能允许你在获取API列表数据后，使用Python脚本对数据进行自定义处理。这对于处理**树形结构**、**嵌套数据**或需要**过滤/转换**的复杂数据特别有用。

## 使用场景

### 1. 树形结构扁平化

**问题**：API返回的是树形结构，但你需要提取所有节点的ID

**示例数据**：
```json
[
  {
    "id": "1",
    "name": "根节点1",
    "children": [
      {
        "id": "1-1",
        "name": "子节点1-1",
        "children": [
          {"id": "1-1-1", "name": "孙节点1-1-1"}
        ]
      }
    ]
  }
]
```

**转换脚本**：
```python
def flatten_tree(node, result_list):
    result_list.append(node)
    if 'children' in node and node['children']:
        for child in node['children']:
            flatten_tree(child, result_list)

result = []
if isinstance(data, list):
    for item in data:
        flatten_tree(item, result)
else:
    flatten_tree(data, result)
```

**结果**：扁平化后的列表包含所有节点

### 2. 数据过滤

**问题**：只需要特定状态的数据

**转换脚本**：
```python
result = [item for item in data if item.get('status') == 'active']
```

### 3. 字段提取

**问题**：只需要提取特定字段

**转换脚本**：
```python
result = [{'id': item['id'], 'name': item['name']} for item in data]
```

### 4. 数据合并

**问题**：需要合并多个数组

**转换脚本**：
```python
result = []
for category in data:
    if 'items' in category:
        result.extend(category['items'])
```

## 配置方法

### 在界面中配置

1. 选择"列表+详情模式"
2. 填写列表接口地址
3. 在"数据转换脚本（可选）"文本框中输入Python脚本
4. 填写其他必要字段
5. 保存配置

### 脚本规范

#### 可用变量

- `data` - 原始API返回的数据
- `result` - 转换后的结果（**必须设置**）

#### 可用函数

脚本中可以使用以下Python内置函数：

- 类型：`isinstance`, `list`, `dict`, `str`, `int`, `float`
- 操作：`len`, `range`, `enumerate`, `zip`
- 函数式：`map`, `filter`, `sorted`
- 聚合：`sum`, `min`, `max`, `any`, `all`
- 调试：`print`（输出到服务器日志）

#### 注意事项

1. **必须设置 result 变量**
   ```python
   # ✓ 正确
   result = [item for item in data]
   
   # ✗ 错误（未设置result）
   filtered = [item for item in data]
   ```

2. **函数定义在脚本内**
   ```python
   # ✓ 正确
   def my_function(x):
       return x * 2
   
   result = [my_function(item) for item in data]
   ```

3. **处理异常**
   ```python
   # 建议添加容错处理
   result = []
   for item in data:
       if 'id' in item:
           result.append(item)
   ```

## 完整示例

### 示例1：帮助中心树形目录

**场景**：帮助中心返回树形目录结构，需要提取所有文档ID

**API返回**：
```json
{
  "results": [
    {
      "id": "cat1",
      "name": "分类1",
      "children": [
        {"id": "doc1", "name": "文档1", "children": []},
        {"id": "doc2", "name": "文档2", "children": []}
      ]
    }
  ]
}
```

**配置**：
- 列表接口地址：`https://api.example.com/help/tree`
- 数据转换脚本：
  ```python
  def flatten_tree(node, result_list):
      # 只添加文档节点（没有children或children为空）
      if not node.get('children') or len(node['children']) == 0:
          result_list.append(node)
      else:
          # 递归处理子节点
          for child in node['children']:
              flatten_tree(child, result_list)
  
  result = []
  tree = data.get('results', [])
  for item in tree:
      flatten_tree(item, result)
  ```
- ID字段路径：`[].id`
- 详情接口地址：`https://api.example.com/help/doc/{id}`
- 详情内容字段路径：`content`

### 示例2：多级分类商品

**场景**：商品按多级分类组织，需要提取所有商品ID

**API返回**：
```json
{
  "categories": [
    {
      "name": "电子产品",
      "subcategories": [
        {
          "name": "手机",
          "products": [
            {"id": "p1", "name": "iPhone"},
            {"id": "p2", "name": "Samsung"}
          ]
        }
      ]
    }
  ]
}
```

**转换脚本**：
```python
result = []
for category in data.get('categories', []):
    for subcategory in category.get('subcategories', []):
        for product in subcategory.get('products', []):
            result.append(product)
```

### 示例3：过滤已发布文章

**场景**：只同步已发布的文章

**转换脚本**：
```python
result = [
    item for item in data 
    if item.get('status') == 'published' and item.get('visible', True)
]
```

## 调试技巧

### 1. 使用 print 调试

```python
print(f"原始数据类型: {type(data)}")
print(f"数据长度: {len(data) if isinstance(data, list) else 'N/A'}")

# 处理数据...
result = []

print(f"结果数量: {len(result)}")
```

输出会显示在服务器日志中。

### 2. 分步验证

```python
# 第一步：提取数据
items = data.get('items', [])
print(f"提取到 {len(items)} 项")

# 第二步：过滤
filtered = [item for item in items if item.get('active')]
print(f"过滤后 {len(filtered)} 项")

# 第三步：转换
result = [{'id': item['id']} for item in filtered]
print(f"最终 {len(result)} 项")
```

### 3. 容错处理

```python
result = []
for item in data:
    try:
        # 确保必要字段存在
        if 'id' in item and 'name' in item:
            result.append(item)
    except Exception as e:
        print(f"处理项目失败: {e}")
        continue
```

## 性能考虑

1. **避免过度复杂的脚本**
   - 转换脚本在每次同步时执行
   - 复杂的递归可能影响性能

2. **大数据量处理**
   - 如果列表很大（>1000项），考虑优化算法
   - 避免嵌套循环

3. **内存使用**
   - 转换过程会创建新的数据结构
   - 注意不要创建过大的中间结果

## 安全说明

1. **沙箱环境**
   - 脚本在受限的Python环境中执行
   - 只能使用白名单中的函数
   - 无法访问文件系统或网络

2. **不支持的操作**
   - 不能导入模块（`import`）
   - 不能执行系统命令
   - 不能访问全局变量

## 故障排查

### 错误：未设置 result 变量

**原因**：脚本没有设置 `result` 变量

**解决**：确保脚本最后设置了 `result`
```python
result = processed_data  # 必须有这一行
```

### 错误：name 'xxx' is not defined

**原因**：使用了不支持的函数或模块

**解决**：只使用文档中列出的内置函数

### 错误：数据转换失败

**原因**：脚本执行出错

**解决**：
1. 检查数据结构是否匹配
2. 添加容错处理
3. 使用 `print` 调试

## 测试脚本

运行测试验证转换功能：

```bash
.venv/bin/python test_transform.py
```

## 总结

数据转换功能让你能够：

✅ 处理树形结构数据  
✅ 过滤和筛选数据  
✅ 提取和重组字段  
✅ 合并多个数据源  
✅ 自定义数据处理逻辑  

通过灵活的Python脚本，你可以处理几乎任何复杂的数据结构！
