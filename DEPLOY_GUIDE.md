# 🚀 部署指南总结

## 当前问题

你遇到的Git访问错误：
```
fatal: unable to access 'https://github.com/...': Empty reply from server
```

## 解决方案（3种方式）

### 方案1：使用部署包（推荐）✨

**最简单、最可靠的方式**

#### 步骤1：创建部署包（本地执行）

```bash
cd /Users/coopwire-test/remote-project/rag-website
./create_deploy_package.sh
```

会生成：`api-source-deploy-YYYYMMDD-HHMMSS.tar.gz` (约60KB)

#### 步骤2：上传到服务器

```bash
scp api-source-deploy-*.tar.gz user@your-server:/tmp/
```

#### 步骤3：在服务器上部署

```bash
# SSH登录服务器
ssh user@your-server

# 进入项目目录
cd /path/to/rag-website

# 备份现有文件
cp main.py main.py.backup
cp static/index.html static/index.html.backup

# 解压部署包
tar -xzf /tmp/api-source-deploy-*.tar.gz --strip-components=1

# 设置权限
chmod +x test_*.sh deploy_with_retry.sh

# 安装依赖
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

# 重启服务
sudo systemctl restart qa-chat

# 验证
sudo systemctl status qa-chat
```

### 方案2：使用改进的部署脚本

如果Git偶尔可以访问：

```bash
# 在服务器上执行
cd /path/to/rag-website
./deploy_with_retry.sh
```

这个脚本会：
- 自动重试Git拉取3次
- 如果失败，跳过Git继续部署
- 完成依赖安装和服务重启

### 方案3：修复Git访问

#### 检查网络

```bash
# 测试GitHub连接
curl -I https://github.com

# 测试DNS
nslookup github.com
```

#### 配置代理（如果需要）

```bash
# 设置代理
git config --global http.proxy http://proxy:port
git config --global https.proxy https://proxy:port

# 或取消代理
git config --global --unset http.proxy
git config --global --unset https.proxy
```

#### 切换到SSH

```bash
# 查看当前配置
git remote -v

# 切换到SSH
git remote set-url origin git@github.com:Carpe912/rag-website.git
```

## 快速部署检查清单

- [ ] 备份现有文件
- [ ] 上传/更新代码
- [ ] 安装依赖 (`pip install -r requirements.txt`)
- [ ] 重启服务 (`systemctl restart qa-chat`)
- [ ] 检查状态 (`systemctl status qa-chat`)
- [ ] 查看日志 (`journalctl -u qa-chat -n 20`)
- [ ] 访问界面测试

## 验证部署成功

### 1. 服务状态

```bash
sudo systemctl status qa-chat
```

应该看到：`Active: active (running)`

### 2. API测试

```bash
# 健康检查
curl http://localhost:8000/api/health

# 数据源列表
curl http://localhost:8000/api/sources
```

### 3. 界面检查

访问：`http://your-server:8000`

检查侧边栏是否有：
- ✅ "Knowledge" 区域（原有）
- ✅ "API数据源" 区域（新增）

### 4. 功能测试

1. 点击"添加数据源"
2. 填写测试配置：
   ```
   数据源名称: 测试
   接口类型: 单接口模式
   API地址: https://jsonplaceholder.typicode.com/posts/1
   内容字段路径: body
   ```
3. 保存并点击"同步"
4. 查看是否成功导入

## 故障排查

### 服务启动失败

```bash
# 查看详细日志
journalctl -u qa-chat -n 100 --no-pager

# 检查端口占用
sudo lsof -i :8000

# 手动启动测试
cd /path/to/rag-website
.venv/bin/python main.py
```

### 模块导入错误

```bash
# 检查httpx是否安装
.venv/bin/pip list | grep httpx

# 重新安装
.venv/bin/pip install httpx
```

### 界面没有新功能

1. 清除浏览器缓存（Ctrl+Shift+R）
2. 检查 `static/index.html` 是否更新
3. 查看浏览器控制台错误

## 回滚方案

如果出现问题：

```bash
# 恢复备份
cp main.py.backup main.py
cp static/index.html.backup static/index.html

# 重启服务
sudo systemctl restart qa-chat
```

## 文件清单

部署包包含：

**核心代码**
- `api_source.py` - 新增模块
- `main.py` - 更新
- `static/index.html` - 更新

**测试脚本**
- `test_api_source.py`
- `test_transform.py`
- `test_api_feature.sh`
- `test_all_features.sh`

**文档**
- `QUICKSTART.md` - 快速上手
- `API_SOURCE_GUIDE.md` - 详细指南
- `TRANSFORM_GUIDE.md` - 转换功能
- `MANUAL_DEPLOY.md` - 手动部署
- 其他文档...

**部署脚本**
- `deploy_with_retry.sh` - 改进的部署脚本
- `DEPLOY_README.txt` - 部署说明

## 推荐部署流程

```
本地机器                    服务器
   │                          │
   ├─ 1. 创建部署包           │
   │  ./create_deploy_package.sh
   │                          │
   ├─ 2. 上传 ──────────────> │
   │  scp package.tar.gz      │
   │                          │
   │                          ├─ 3. 备份现有文件
   │                          │
   │                          ├─ 4. 解压部署包
   │                          │
   │                          ├─ 5. 安装依赖
   │                          │
   │                          ├─ 6. 重启服务
   │                          │
   │                          ├─ 7. 验证功能
   │                          │
   │  <──────────────────────┤ 8. 确认成功
   │                          │
```

## 相关文档

- 📦 [MANUAL_DEPLOY.md](./MANUAL_DEPLOY.md) - 详细的手动部署指南
- 🚀 [QUICKSTART.md](./QUICKSTART.md) - 功能快速上手
- 📖 [API_SOURCE_GUIDE.md](./API_SOURCE_GUIDE.md) - 完整使用指南
- 🌲 [TRANSFORM_GUIDE.md](./TRANSFORM_GUIDE.md) - 数据转换功能

## 获取帮助

如果遇到问题：

1. 查看 [MANUAL_DEPLOY.md](./MANUAL_DEPLOY.md) 的故障排查章节
2. 收集错误日志：`journalctl -u qa-chat -n 100 > error.log`
3. 检查系统信息：`python --version`, `pip list`

---

**建议**：由于Git访问不稳定，推荐使用**方案1（部署包）**进行部署。
