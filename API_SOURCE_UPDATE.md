# API数据源功能 - 更新说明

## 新增功能

本次更新为RAG知识库系统添加了**API数据源**功能，允许用户从外部API接口批量获取数据并自动向量化入库。

## 核心特性

### 1. 灵活的接口配置

支持两种数据获取模式：

- **单接口模式**：直接从一个API获取内容
- **列表+详情模式**：先获取ID列表，再逐个调用详情接口

### 2. 强大的字段路径解析

支持复杂的JSON路径提取：
- 简单字段：`field`
- 嵌套字段：`field.subfield`
- 数组提取：`field[].id`（提取所有元素）
- 数组索引：`field[0].id`（提取指定元素）

### 3. 自动向量化

- 获取的内容自动分块
- 后台异步向量化
- 前端实时显示进度

### 4. 用户友好的界面

- 可视化配置对话框
- 一键同步按钮
- 实时状态显示

## 文件结构

```
rag-website/
├── api_source.py              # API数据源核心模块
├── main.py                    # 后端API接口（已更新）
├── static/index.html          # 前端界面（已更新）
├── test_api_source.py         # 测试脚本
├── API_SOURCE_GUIDE.md        # 使用指南
└── data/
    └── api_sources.json       # 数据源配置存储
```

## 新增API接口

### 1. 获取数据源列表
```http
GET /api/sources
```

### 2. 创建数据源
```http
POST /api/sources
Content-Type: application/json

{
  "name": "数据源名称",
  "source_type": "single",
  "api_url": "https://...",
  "content_path": "results.content"
}
```

### 3. 同步数据源
```http
POST /api/sources/{source_id}/sync
```

### 4. 更新数据源
```http
PUT /api/sources/{source_id}
```

### 5. 删除数据��
```http
DELETE /api/sources/{source_id}
```

## 使用示例

### 示例1：从帮助中心同步文档

**场景**：你的帮助中心有一个API返回markdown文档

```json
配置：
{
  "name": "帮助中心文档",
  "source_type": "single",
  "api_url": "https://coop.logwirecloud.com/rest/helper/help/center/xxx/help/xxx",
  "content_path": "results.content"
}
```

点击"同步"按钮后，系统会：
1. 调用API获取内容
2. 将内容保存为markdown文档
3. 自动分块并向量化
4. 加入知识库供RAG检索

### 示例2：批量导入文档列表

**场景**：先获取文档ID列表，再逐个获取详情

```json
配置：
{
  "name": "API文档库",
  "source_type": "list_detail",
  "list_api_url": "https://api.example.com/docs/list",
  "list_id_path": "results[].id",
  "detail_api_url": "https://api.example.com/docs/{id}",
  "detail_content_path": "data.content"
}
```

系统会：
1. 调用列表接口获取所有ID
2. 逐个调用详情接口
3. 将每个文档内容向量化入库

## 技术实现

### 后端（Python）

- **api_source.py**：核心模块
  - `ApiSourceConfig`：数据源配置模型
  - `fetch_api_data()`：异步获取API数据
  - `_get_nested_value()`：JSON路径解析
  - `sync_api_source()`：同步数据并入库

- **main.py**：FastAPI路由
  - 新增5个API端点
  - 集成后台向量化任务

### 前端（JavaScript）

- 新增"API数据源"区域
- 配置对话框（支持两种模式切换）
- 同步按钮和状态显示
- 与现有文档管理集成

## 测试

运行测试脚本验证功能：

```bash
.venv/bin/python test_api_source.py
```

测试覆盖：
- ✓ 嵌套值提取
- ✓ API数据获取
- ✓ 配置管理

## 未来改进

计划支持的功能：

1. **认证支持**
   - 自定义HTTP请求头
   - Bearer Token
   - API Key

2. **高级配置**
   - POST请求支持
   - 请求参数配置
   - 批量详情接口

3. **自动化**
   - 定时自动同步
   - 增量更新
   - Webhook触发

4. **监控**
   - 同步历史记录
   - 错误日志
   - 性能统计

## 注意事项

1. **API访问**：确保服务器可以访问目标API
2. **数据格式**：内容应为markdown或纯文本
3. **性能**：列表+详情模式会逐个调用，大量数据需要时间
4. **更新策略**：每次同步创建新文档，如需更新建议先删除旧文档

## 兼容性

- 完全兼容现有文档上传功能
- 不影响现有知识库数据
- 可与文件上传混合使用

## 依赖

已包含在 requirements.txt 中：
- `httpx>=0.27.0` - HTTP客户端

## 贡献

欢迎提交Issue和PR改进此功能！

---

**详细使用指南**：请查看 [API_SOURCE_GUIDE.md](./API_SOURCE_GUIDE.md)
