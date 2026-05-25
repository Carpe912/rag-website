# 基于权限的智能问答设计方案

## 问题描述

### 场景举例

**用户A的权限**：
- ✅ 议题模块（可访问）
- ❌ 反馈模块（无权限）

**当前问题**：
```
用户A问："应该怎么创建反馈？"
系统回答："请进入反馈模块，点击'新建反馈'按钮..."  ❌ 错误！用户根本看不到这个模块
```

**期望效果**：
```
用户A问："应该怎么创建反馈？"
系统回答："您当前没有'反馈模块'的访问权限。如需开通，请联系管理员或访问权限申请页面。"  ✅ 正确
```

---

## 核心设计思路

### 方案对比

#### 方案A：检索时过滤（不推荐）
```
只检索用户有权限的模块文档
```
**问题**：用户问无权限的功能时，系统会说"不知道"，而不是"你没权限"

#### 方案B：检索后在 Prompt 中注入权限（推荐）
```
1. 正常检索所有相关文档
2. 获取用户权限列表
3. 在 Prompt 中告诉 Claude：用户有哪些权限
4. Claude 根据权限给出不同回答
```
**优点**：灵活、智能、用户体验好

---

## 详细设计

### 1. 数据模型

#### 1.1 权限定义（Permission）
```python
@dataclass
class Permission:
    """权限定义"""
    permission_id: str      # 权限ID，如 "perm_issue"
    name: str               # 权限名称，如 "议题模块"
    code: str               # 权限代码，如 "module:issue"
    description: str        # 权限描述
    module: str             # 所属模块
    actions: list[str]      # 可执行的操作，如 ["view", "create", "edit"]
```

#### 1.2 用户权限（UserPermission）
```python
@dataclass
class UserPermission:
    """用户权限"""
    user_id: str
    permission_codes: list[str]  # 用户拥有的权限代码列表
    # 例如：["module:issue:view", "module:issue:create"]
```

#### 1.3 文档权限标签（Document Metadata）
```python
@dataclass
class Document:
    doc_id: str
    name: str
    project_id: str
    required_permissions: list[str] = []  # 🆕 访问此文档需要的权限
    # 例如：["module:feedback:view"] 表示需要反馈模块权限才能看
```

### 2. 权限 API 集成

#### 2.1 获取用户权限
```python
# permission_service.py

import httpx
from typing import Optional

class PermissionService:
    """权限服务，从外部 API 获取权限数据"""
    
    def __init__(self, api_base_url: str, api_token: str):
        self.api_base_url = api_base_url
        self.api_token = api_token
        self._cache = {}  # 简单的内存缓存
    
    async def get_user_permissions(self, user_id: str) -> list[str]:
        """获取用户的权限列表"""
        cache_key = f"user_perms_{user_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_base_url}/users/{user_id}/permissions",
                headers={"Authorization": f"Bearer {self.api_token}"},
                timeout=5.0
            )
            response.raise_for_status()
            data = response.json()
            
            # 假设 API 返回格式：
            # {
            #   "permissions": [
            #     {"code": "module:issue:view", "name": "查看议题"},
            #     {"code": "module:issue:create", "name": "创建议题"}
            #   ]
            # }
            permission_codes = [p["code"] for p in data.get("permissions", [])]
            
            # 缓存 5 分钟
            self._cache[cache_key] = permission_codes
            return permission_codes
    
    async def get_permission_definitions(self) -> dict[str, dict]:
        """获取所有权限定义"""
        cache_key = "permission_defs"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_base_url}/permissions/definitions",
                headers={"Authorization": f"Bearer {self.api_token}"},
                timeout=5.0
            )
            response.raise_for_status()
            data = response.json()
            
            # 假设 API 返回格式：
            # {
            #   "permissions": [
            #     {
            #       "code": "module:issue",
            #       "name": "议题模块",
            #       "description": "管理项目议题",
            #       "actions": ["view", "create", "edit", "delete"]
            #     }
            #   ]
            # }
            
            # 转换为字典，方便查询
            perm_dict = {
                p["code"]: p for p in data.get("permissions", [])
            }
            
            # 缓存 30 分钟
            self._cache[cache_key] = perm_dict
            return perm_dict
    
    def check_permission(self, user_permissions: list[str], required: str) -> bool:
        """检查用户是否有某个权限"""
        # 支持通配符匹配
        # 例如：用户有 "module:issue:*"，则可以访问 "module:issue:view"
        for user_perm in user_permissions:
            if user_perm == required:
                return True
            if user_perm.endswith(":*") and required.startswith(user_perm[:-2]):
                return True
        return False
```

#### 2.2 权限缓存策略
```python
# 使用 Redis 或内存缓存
from functools import lru_cache
import time

class PermissionCache:
    def __init__(self, ttl: int = 300):  # 默认 5 分钟过期
        self.cache = {}
        self.ttl = ttl
    
    def get(self, key: str):
        if key in self.cache:
            value, expire_time = self.cache[key]
            if time.time() < expire_time:
                return value
            else:
                del self.cache[key]
        return None
    
    def set(self, key: str, value):
        self.cache[key] = (value, time.time() + self.ttl)
```

### 3. RAG 流程改造

#### 3.1 检索阶段（保持不变）
```python
# 正常检索，不过滤权限
chunks = retrieve_chunks(
    query="怎么创建反馈？",
    project_id="proj_001",
    top_k=5
)
# 返回所有相关文档，包括用户无权限的
```

#### 3.2 生成阶段（注入权限信息）
```python
async def build_rag_prompt_with_permissions(
    query: str,
    chunks: list[Chunk],
    user_permissions: list[str],
    permission_definitions: dict
) -> str:
    """构建包含权限信息的 RAG Prompt"""
    
    # 1. 构建用户权限描述
    user_modules = set()
    for perm_code in user_permissions:
        # 从 "module:issue:view" 提取 "issue"
        parts = perm_code.split(":")
        if len(parts) >= 2 and parts[0] == "module":
            user_modules.add(parts[1])
    
    # 获取模块的友好名称
    module_names = []
    for module_code in user_modules:
        perm_key = f"module:{module_code}"
        if perm_key in permission_definitions:
            module_names.append(permission_definitions[perm_key]["name"])
        else:
            module_names.append(module_code)
    
    # 2. 标记每个文档块的权限要求
    annotated_chunks = []
    for chunk in chunks:
        required_perms = chunk.required_permissions or []
        
        # 检查用户是否有权限
        has_permission = True
        if required_perms:
            has_permission = any(
                check_permission(user_permissions, req) 
                for req in required_perms
            )
        
        # 添加权限标记
        permission_note = ""
        if not has_permission and required_perms:
            # 获取缺失的权限名称
            missing_perm = required_perms[0]
            perm_name = permission_definitions.get(missing_perm, {}).get("name", missing_perm)
            permission_note = f"\n[权限要求：需要 {perm_name} 权限]"
        
        annotated_chunks.append({
            "text": chunk.text,
            "has_permission": has_permission,
            "permission_note": permission_note
        })
    
    # 3. 构建 Prompt
    context_parts = []
    for i, chunk in enumerate(annotated_chunks, 1):
        context_parts.append(
            f"[文档片段 {i}]{chunk['permission_note']}\n{chunk['text']}"
        )
    
    context = "\n\n".join(context_parts)
    
    prompt = f"""你是一个智能助手，需要根据用户的权限来回答问题。

## 用户当前拥有的权限
用户可以访问以下模块：{', '.join(module_names) if module_names else '无'}

## 重要规则
1. 如果用户询问的功能需要某个权限，而用户没有该权限：
   - 明确告诉用户：他没有该权限
   - 告诉用户：需要联系管理员或通过权限申请页面开通
   - 不要提供具体的操作步骤（因为用户看不到相关界面）

2. 如果用户有相应权限：
   - 正常提供详细的操作步骤

3. 如果文档片段标记了 [权限要求]：
   - 这表示该功能需要特定权限
   - 请根据用户是否有该权限来决定如何回答

## 知识库内容
{context}

## 用户问题
{query}

请根据用户的权限情况，给出恰当的回答。"""
    
    return prompt
```

### 4. 完整流程示例

#### 4.1 用户有权限的情况
```python
# 用户A的权限：["module:issue:view", "module:issue:create"]
# 用户A问："怎么创建议题？"

# 1. 检索相关文档
chunks = retrieve_chunks("怎么创建议题？", project_id="proj_001")
# 返回：[
#   Chunk(text="创建议题：进入议题模块，点击'新建'按钮...", 
#         required_permissions=["module:issue:view"])
# ]

# 2. 获取用户权限
user_perms = await permission_service.get_user_permissions("user_A")
# ["module:issue:view", "module:issue:create"]

# 3. 构建 Prompt
prompt = await build_rag_prompt_with_permissions(
    query="怎么创建议题？",
    chunks=chunks,
    user_permissions=user_perms,
    permission_definitions=perm_defs
)

# Prompt 内容：
"""
你是一个智能助手，需要根据用户的权限来回答问题。

## 用户当前拥有的权限
用户可以访问以下模块：议题模块

## 重要规则
...

## 知识库内容
[文档片段 1]
创建议题：进入议题模块，点击'新建'按钮...

## 用户问题
怎么创建议题？
"""

# 4. Claude 回答
# "您可以通过以下步骤创建议题：1. 进入议题模块 2. 点击'新建'按钮..."  ✅
```

#### 4.2 用户无权限的情况
```python
# 用户A的权限：["module:issue:view", "module:issue:create"]
# 用户A问："怎么创建反馈？"

# 1. 检索相关文档
chunks = retrieve_chunks("怎么创建反馈？", project_id="proj_001")
# 返回：[
#   Chunk(text="创建反馈：进入反馈模块，点击'新建反馈'按钮...", 
#         required_permissions=["module:feedback:view"])
# ]

# 2. 获取用户权限
user_perms = await permission_service.get_user_permissions("user_A")
# ["module:issue:view", "module:issue:create"]  ← 没有 feedback 权限

# 3. 构建 Prompt
prompt = await build_rag_prompt_with_permissions(
    query="怎么创建反馈？",
    chunks=chunks,
    user_permissions=user_perms,
    permission_definitions=perm_defs
)

# Prompt 内容：
"""
你是一个智能助手，需要根据用户的权限来回答问题。

## 用户当前拥有的权限
用户可以访问以下模块：议题模块

## 重要规则
1. 如果用户询问的功能需要某个权限，而用户没有该权限：
   - 明确告诉用户：他没有该权限
   - 告诉用户：需要联系管理员或通过权限申请页面开通
   - 不要提供具体的操作步骤

## 知识库内容
[文档片段 1][权限要求：需要 反馈模块 权限]
创建反馈：进入反馈模块，点击'新建反馈'按钮...

## 用户问题
怎么创建反馈？
"""

# 4. Claude 回答
# "抱歉，您当前没有'反馈模块'的访问权限。如需使用反馈功能，请联系管理员开通权限，或访问权限申请页面提交申请。"  ✅
```

### 5. 文档标注策略

#### 5.1 上传文档时标注权限
```python
@app.post("/api/documents")
async def upload_document(
    file: UploadFile,
    project_id: str,
    required_permissions: list[str] = []  # 🆕 可选的权限要求
):
    """
    上传文档时，可以指定访问该文档需要的权限
    
    例如：
    - 上传"反馈模块使用手册.pdf"时，标注 required_permissions=["module:feedback:view"]
    - 上传"议题管理指南.pdf"时，标注 required_permissions=["module:issue:view"]
    """
    doc = await ingest_document(file, project_id)
    doc.required_permissions = required_permissions
    save_documents([doc])
    return {"doc_id": doc.doc_id}
```

#### 5.2 自动推断权限（智能标注）
```python
def infer_permissions_from_content(doc_name: str, content: str) -> list[str]:
    """根据文档名称和内容自动推断所需权限"""
    permissions = []
    
    # 规则1：根据文档名称
    if "反馈" in doc_name or "feedback" in doc_name.lower():
        permissions.append("module:feedback:view")
    if "议题" in doc_name or "issue" in doc_name.lower():
        permissions.append("module:issue:view")
    
    # 规则2：根据内容关键词
    if "反馈模块" in content or "创建反馈" in content:
        permissions.append("module:feedback:view")
    if "议题列表" in content or "新建议题" in content:
        permissions.append("module:issue:view")
    
    return list(set(permissions))  # 去重

# 使用
doc = ingest_document(file, project_id)
doc.required_permissions = infer_permissions_from_content(doc.name, doc.content)
```

#### 5.3 批量标注工具
```python
# 提供一个管理界面，让管理员批量标注文档权限
@app.post("/api/documents/{doc_id}/permissions")
async def update_document_permissions(
    doc_id: str,
    permissions: list[str]
):
    """更新文档的权限要求"""
    docs = load_documents()
    for doc in docs:
        if doc.doc_id == doc_id:
            doc.required_permissions = permissions
            break
    save_documents(docs)
    return {"success": True}
```

### 6. API 接口设计

#### 6.1 对话接口（修改）
```python
@app.post("/api/chat")
async def chat(
    request: ChatRequest,
    user_id: str = Depends(get_current_user),
    project_id: str = Header(None, alias="X-Project-ID")
):
    """
    对话接口，自动注入用户权限
    """
    # 1. 获取用户权限
    user_permissions = await permission_service.get_user_permissions(user_id)
    permission_definitions = await permission_service.get_permission_definitions()
    
    # 2. 检索文档
    chunks = retrieve_chunks(
        query=request.message,
        project_id=project_id,
        top_k=5
    )
    
    # 3. 构建包含权限信息的 Prompt
    system_prompt = await build_rag_prompt_with_permissions(
        query=request.message,
        chunks=chunks,
        user_permissions=user_permissions,
        permission_definitions=permission_definitions
    )
    
    # 4. 调用 Claude
    response = await claude_client.messages.create(
        model="claude-opus-4-6",
        system=system_prompt,
        messages=[{"role": "user", "content": request.message}],
        stream=True
    )
    
    # 5. 流式返回
    return StreamingResponse(...)
```

#### 6.2 权限查询接口（新增）
```python
@app.get("/api/users/me/permissions")
async def get_my_permissions(user_id: str = Depends(get_current_user)):
    """获取当前用户的权限列表"""
    permissions = await permission_service.get_user_permissions(user_id)
    definitions = await permission_service.get_permission_definitions()
    
    # 返回友好的权限列表
    result = []
    for perm_code in permissions:
        perm_def = definitions.get(perm_code, {})
        result.append({
            "code": perm_code,
            "name": perm_def.get("name", perm_code),
            "description": perm_def.get("description", "")
        })
    
    return {"permissions": result}
```

### 7. 前端展示

#### 7.1 显示用户权限
```html
<!-- 在页面顶部显示用户当前权限 -->
<div class="user-permissions">
    <span>当前权限：</span>
    <span class="badge">议题模块</span>
    <span class="badge">文档模块</span>
    <button onclick="viewAllPermissions()">查看详情</button>
</div>
```

#### 7.2 权限不足提示
```javascript
// 当 AI 回答包含权限不足信息时，高亮显示
function renderMessage(message) {
    if (message.includes("没有") && message.includes("权限")) {
        return `
            <div class="message permission-denied">
                <i class="icon-warning"></i>
                ${message}
                <button onclick="applyPermission()">申请权限</button>
            </div>
        `;
    }
    return `<div class="message">${message}</div>`;
}
```

### 8. 高级优化

#### 8.1 权限预检查（可选）
```python
async def precheck_query_permissions(query: str, user_permissions: list[str]) -> dict:
    """
    在检索前，先用 LLM 判断用户可能在问什么功能
    如果明显超出权限，直接返回提示，不进行检索
    """
    # 使用轻量级模型快速判断
    prompt = f"""
    用户权限：{user_permissions}
    用户问题：{query}
    
    判断：用户是否在询问他没有权限的功能？
    如果是，返回 JSON: {{"has_permission": false, "required": "module:xxx"}}
    如果不是，返回: {{"has_permission": true}}
    """
    
    response = await claude_client.messages.create(
        model="claude-haiku-4-5",  # 使用快速模型
        messages=[{"role": "user", "content": prompt}],
        max_tokens=100
    )
    
    result = json.loads(response.content[0].text)
    return result
```

#### 8.2 权限申请流程集成
```python
@app.post("/api/permissions/apply")
async def apply_permission(
    permission_code: str,
    reason: str,
    user_id: str = Depends(get_current_user)
):
    """
    用户申请权限
    """
    # 调用外部权限系统的申请接口
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{PERMISSION_API_BASE}/applications",
            json={
                "user_id": user_id,
                "permission_code": permission_code,
                "reason": reason
            },
            headers={"Authorization": f"Bearer {PERMISSION_API_TOKEN}"}
        )
        return response.json()
```

#### 8.3 权限变更通知
```python
# 当用户权限变更时，清除缓存
@app.post("/api/webhooks/permission-changed")
async def on_permission_changed(event: dict):
    """
    接收权限系统的 Webhook 通知
    """
    user_id = event.get("user_id")
    
    # 清除该用户的权限缓存
    cache_key = f"user_perms_{user_id}"
    permission_cache.delete(cache_key)
    
    # 可选：推送通知给用户
    await notify_user(user_id, "您的权限已更新，请刷新页面")
    
    return {"success": True}
```

---

## 实施步骤

### Phase 1: 权限服务集成（1-2天）
1. 实现 `PermissionService` 类
2. 对接外部权限 API
3. 实现权限缓存机制
4. 测试权限获取和检查逻辑

### Phase 2: 文档权限标注（1天）
1. 修改 `Document` 和 `Chunk` 数据模型，添加 `required_permissions` 字段
2. 实现文档上传时的权限标注
3. 编写批量标注工具
4. 为现有文档标注权限

### Phase 3: RAG 流程改造（2-3天）
1. 实现 `build_rag_prompt_with_permissions` 函数
2. 修改对话接口，注入用户权限
3. 优化 Prompt 模板
4. 测试不同权限场景下的回答

### Phase 4: 前端展示（1天）
1. 显示用户当前权限
2. 优化权限不足的提示样式
3. 添加权限申请入口

### Phase 5: 测试和优化（1-2天）
1. 测试各种权限组合
2. 优化 Prompt 效果
3. 性能优化（缓存、预检查）

---

## 总结

### 核心思想
**不是过滤文档，而是让 AI 知道用户的权限，智能地给出不同回答**

### 关键点
1. **权限获取**：从外部 API 实时获取用户权限
2. **文档标注**：给文档打上权限标签
3. **Prompt 注入**：在 Prompt 中明确告诉 Claude 用户的权限
4. **智能回答**：Claude 根据权限给出"有权限→操作步骤"或"无权限→申请提示"

### 优势
- ✅ 用户体验好：明确告知权限状态
- ✅ 安全可控：不会泄露无权限的操作细节
- ✅ 灵活扩展：新增权限类型无需改代码
- ✅ 智能判断：利用 LLM 的理解能力

### 预计工作量
**6-8 个工作日**
