# 🎉 数据转换功能更新

## 新增功能

在原有API数据源功能基础上，新增了**数据转换脚本**功能，可以处理复杂的数据结构。

## 更新内容

### 1. 核心功能

✅ **树形结构扁平化** - 递归处理嵌套的children节点  
✅ **数据过滤** - 根据条件筛选数据  
✅ **字段提取** - 只保留需要的字段  
✅ **数据合并** - 合并多个数组  
✅ **自定义转换** - 使用Python脚本自由处理  

### 2. 代码更新

**api_source.py**
- 新增 `transform_script` 字段到 `ApiSourceConfig`
- 新增 `_apply_transform()` 函数处理数据转换
- 在 `fetch_api_data()` 中集成转换逻辑

**main.py**
- `ApiSourceCreateRequest` 新增 `transform_script` 字段
- 创建数据源时支持转换脚本配置

**static/index.html**
- 配置对话框新增"数据转换脚本"文本框
- 支持多行输入，使用等宽字体
- 提供示例和说明

### 3. 测试验证

新增测试文件：`test_transform.py`

测试覆盖：
- ✅ 树形结构扁平化
- ✅ 简单数据转换
- ✅ 数据过滤

所有测试通过！

## 使用示例

### 树形结构扁平化

**场景**：API返回树形目录，需要提取所有节点

**转换脚本**：
```python
def flatten_tree(node, result_list):
    result_list.append(node)
    if 'children' in node and node['children']:
        for child in node['children']:
            flatten_tree(child, result_list)

result = []
for item in data:
    flatten_tree(item, result)
```

**效果**：
- 输入：2个根节点，包含4个子节点
- 输出：6个扁平化节点

### 数据过滤

**转换脚本**：
```python
result = [item for item in data if item.get('status') == 'active']
```

### 字段提取

**转换脚本**：
```python
result = [{'id': item['id'], 'name': item['name']} for item in data]
```

## 配置方法

1. 在"列表+详情模式"中
2. 填写"数据转换脚本（可选）"
3. 脚本中：
   - `data` 是原始数据
   - 必须设置 `result` 变量

## 安全特性

- ✅ 沙箱环境执行
- ✅ 只允许白名单函数
- ✅ 无法访问文件系统
- ✅ 无法执行系统命令

## 文档

- 📖 [数据转换使用指南](./TRANSFORM_GUIDE.md) - 详细说明和示例
- 🧪 [测试脚本](./test_transform.py) - 功能验证

## 测试命令

```bash
# 测试数据转换功能
.venv/bin/python test_transform.py

# 完整功能测试
./test_api_feature.sh
```

## 更新文件

- ✅ `api_source.py` - 核心转换逻辑（+60行）
- ✅ `main.py` - API接口支持（+1行）
- ✅ `static/index.html` - UI界面（+20行）
- ✅ `test_transform.py` - 测试脚本（新增）
- ✅ `TRANSFORM_GUIDE.md` - 使用指南（新增）
- ✅ `QUICKSTART.md` - 更新快速上手（+15行）

## 兼容性

✅ 完全向后兼容  
✅ 转换脚本为可选功能  
✅ 不影响现有配置  

## 总结

现在你可以处理任何复杂的API数据结构了！

- 🌲 树形结构 → 扁平化
- 🔍 复杂数据 → 过滤提取
- 🔄 多级嵌套 → 自由转换

**完美解决了你提出的树形结构问题！** 🎊
