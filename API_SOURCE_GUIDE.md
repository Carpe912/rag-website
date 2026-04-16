# API数据源配置指南

## 功能概述

API数据源功能允许你从外部API接口批量获取数据并自动向量化入库，无需手动上传文件。支持两种模式：

1. **单接口模式**：直接从一个API获取内容
2. **列表+详情模式**：先获取ID列表，再逐个调用详情接口

## 使用场景

- 从帮助中心API同步文档
- 从知识库系统批量导入内容
- 从CMS系统获取文章
- 从内部服务获取技术文档

## 配置示例

### 示例1：单接口模式

假设你有一个API返回单篇文档：

**API地址：**
```
https://coop.logwirecloud.com/rest/helper/help/center/691d35c4b9e9c20ba7e83f7d/help/6949f57bc64bef77a31839d7
```

**返回格式：**
```json
{
  "results": {
    "content": "这里是markdown格式的文档内容..."
  }
}
```

**配置：**
- 数据源名称：`帮助中心文档`
- 接口类型：`单接口模式`
- API地址：`https://coop.logwirecloud.com/rest/helper/help/center/691d35c4b9e9c20ba7e83f7d/help/6949f57bc64bef77a31839d7`
- 内容字段路径：`results.content`

### 示例2：列表+详情模式

假设你需要先获取文档列表，再逐个获取详情：

**列表接口：**
```
https://api.example.com/docs/list
```

**列表返回格式：**
```json
{
  "results": [
    {"id": "doc1", "title": "文档1"},
    {"id": "doc2", "title": "文档2"}
  ]
}
```

**详情接口模板：**
```
https://api.example.com/docs/{id}
```

**详情返回格式：**
```json
{
  "data": {
    "content": "这里是markdown格式的文档内容..."
  }
}
```

**配置：**
- 数据源名称：`API文档库`
- 接口类型：`列表+详情模式`
- 列表接口地址：`https://api.example.com/docs/list`
- ID字段路径：`results[].id`
- 详情接口地址模板：`https://api.example.com/docs/{id}`
- 详情内容字段路径：`data.content`

## 字段路径语法

支持以下路径格式：

- `field` - 简单字段
- `field.subfield` - 嵌套字段
- `field[].id` - 数组中的字段（提取所有元素的id）
- `field[0].id` - 数组索引（提取第一个元素的id）

### 示例

**数据结构：**
```json
{
  "data": {
    "items": [
      {"id": "1", "content": "内容1"},
      {"id": "2", "content": "内容2"}
    ]
  }
}
```

**路径示例：**
- `data.items[].id` → `["1", "2"]`
- `data.items[0].content` → `"内容1"`
- `data.items[].content` → `["内容1", "内容2"]`

## 使用流程

1. **添加数据源**
   - 点击侧边栏"API数据源"区域的"添加数据源"按钮
   - 填写配置信息
   - 点击"保存"

2. **同步数据**
   - 在数据源列表中找到对应的数据源
   - 点击"同步"按钮（刷新图标）
   - 系统会自动获取数据并向量化入库

3. **查看结果**
   - 同步完成后，文档会出现在"Knowledge"区域
   - 向量化完成后，可以在对话中使用这些知识

## 注意事项

1. **API访问权限**
   - 确保API地址可以从服务器访问
   - 如需认证，可以在后续版本中添加headers配置

2. **数据格式**
   - 内容应为markdown或纯文本格式
   - 系统会自动分块并向量化

3. **性能考虑**
   - 列表+详情模式会逐个调用详情接口
   - 如果列表很长，同步可能需要较长时间
   - 建议在低峰期进行大批量同步

4. **更新策略**
   - 每次同步都会创建新文档
   - 如需更新，建议先删除旧文档再同步

## 高级配置（未来版本）

计划支持的功能：

- [ ] 自定义HTTP请求头（用于认证）
- [ ] POST请求支持
- [ ] 请求参数配置
- [ ] 定时自动同步
- [ ] 增量更新（仅同步变更）
- [ ] 批量详情接口（一次获取多个ID）

## 故障排查

### 同步失败

1. 检查API地址是否正确
2. 检查字段路径是否匹配返回数据结构
3. 查看浏览器控制台的错误信息
4. 确认服务器可以访问目标API

### 未获取到内容

1. 使用浏览器或Postman测试API返回
2. 检查字段路径是否正确
3. 确认返回数据中确实包含内容

### 向量化失败

1. 检查Embedding API配置（.env文件）
2. 查看服务器日志
3. 确认内容格式正确（非空文本）

## API接口文档

### 获取数据源列表

```http
GET /api/sources
```

### 创建数据源

```http
POST /api/sources
Content-Type: application/json

{
  "name": "数据源名称",
  "source_type": "single",  // 或 "list_detail"
  "api_url": "https://...",
  "content_path": "results.content",
  "method": "GET",
  "timeout": 30
}
```

### 同步数据源

```http
POST /api/sources/{source_id}/sync
```

### 删除数据源

```http
DELETE /api/sources/{source_id}
```
