# 🚀 API数据源功能 - 快速上手

## 5分钟快速开始

### 1️⃣ 运行测试（验证功能）

```bash
./test_api_feature.sh
```

应该看到所有测试通过 ✓

### 2️⃣ 启动服务

```bash
./run.sh
```

### 3️⃣ 打开浏览器

访问：http://localhost:8000

### 4️⃣ 添加测试数据源

在侧边栏找到"API数据源"区域，点击"添加数据源"，填写：

```
数据源名称: 测试API
接口类型: 单接口模式
API地址: https://jsonplaceholder.typicode.com/posts/1
内容字段路径: body
```

点击"保存"

### 5️⃣ 同步数据

点击数据源旁边的"同步"按钮（刷新图标）

等待几秒，你会看到：
- ✅ 同步成功提示
- 📄 新文档出现在"Knowledge"区域
- 🔄 向量化进度显示

### 6️⃣ 测试对话

在对话框输入：
```
请总结一下我刚才导入的内容
```

系统会使用RAG检索刚导入的内容并回答！

## 🎯 使用你的API

### 单接口模式示例

你提供的帮助中心接口：

```
数据源名称: 帮助中心文档
接口类型: 单接口模式
API地址: https://coop.logwirecloud.com/rest/helper/help/center/691d35c4b9e9c20ba7e83f7d/help/6949f57bc64bef77a31839d7
内容字段路径: results.content
```

### 列表+详情模式示例

如果你有列表接口：

```
数据源名称: 文档库
接口类型: 列表+详情模式
列表接口地址: https://api.example.com/list
ID字段路径: results[].id
详情接口地址模板: https://api.example.com/detail/{id}
详情内容字段路径: data.content
```

## 📖 字段路径语法

| 路径 | 说明 | 示例 |
|------|------|------|
| `field` | 简单字段 | `content` |
| `field.subfield` | 嵌套字段 | `results.content` |
| `field[].id` | 数组所有元素 | `items[].id` |
| `field[0].id` | 数组指定索引 | `items[0].id` |

## 🔍 测试你的API

使用浏览器或curl测试API返回：

```bash
curl https://your-api.com/endpoint
```

确认返回的JSON结构，然后配置正确的字段路径。

## 📚 完整文档

- 📖 [详细使用指南](./API_SOURCE_GUIDE.md) - 完整功能说明
- 🏗️ [系统架构图](./ARCHITECTURE.md) - 技术架构
- 📋 [功能更新说明](./API_SOURCE_UPDATE.md) - 更新内容
- 📝 [实现总结](./IMPLEMENTATION_SUMMARY.md) - 实现细节
- 📦 [交付总结](./DELIVERY_SUMMARY.md) - 完整交付内容

## ❓ 常见问题

### Q: 同步失败怎么办？
A: 
1. 检查API地址是否正确
2. 验证字段路径是否匹配返回数据
3. 查看浏览器控制台错误信息

### Q: 如何知道字段路径？
A: 
1. 用浏览器访问API查看返回JSON
2. 或使用Postman测试
3. 根据JSON结构配置路径

### Q: 支持认证吗？
A: 当前版本暂不支持，后续版本会添加自定义请求头功能

### Q: 可以定时同步吗？
A: 当前需要手动点击同步，定时同步功能在规划中

## 🎉 功能特性

✅ 自定义API接口地址  
✅ 灵活的字段路径配置  
✅ 单接口和列表+详情两种模式  
✅ 手动触发批量同步  
✅ 自动向量化入库  
✅ 实时进度显示  

## 🛠️ 技术支持

如有问题，请查看：
1. [使用指南](./API_SOURCE_GUIDE.md) 中的故障排查章节
2. 浏览器控制台的错误信息
3. 服务器日志输出

---

**祝使用愉快！** 🎊
