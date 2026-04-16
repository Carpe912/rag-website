# 手动部署指南

## 问题诊断

你遇到的错误：
```
fatal: unable to access 'https://github.com/...': Empty reply from server
```

这通常是由以下原因造成的：

1. **网络问题** - 服务器无法访问GitHub
2. **代理配置** - Git代理设置有问题
3. **GitHub访问限制** - 防火墙或网络策略

## 解决方案

### 方案1：使用改进的部署脚本（推荐）

```bash
chmod +x deploy_with_retry.sh
./deploy_with_retry.sh
```

这个脚本会：
- 自动重试Git拉取（最多3次）
- 如果Git失败，跳过并使用本地代码
- 继续完成部署流程

### 方案2：手动上传代码

如果Git完全无法访问，可以手动上传代码：

#### 步骤1：在本地打包代码

```bash
# 在本地机器上执行
cd /Users/coopwire-test/remote-project/rag-website

# 打包新增和修改的文件
tar -czf api-source-update.tar.gz \
  api_source.py \
  test_api_source.py \
  test_transform.py \
  test_api_feature.sh \
  test_all_features.sh \
  main.py \
  static/index.html \
  *.md

# 查看打包内容
tar -tzf api-source-update.tar.gz
```

#### 步骤2：上传到服务器

```bash
# 使用scp上传
scp api-source-update.tar.gz user@your-server:/path/to/rag-website/

# 或使用其他方式（FTP、SFTP等）
```

#### 步骤3：在服务器上解压

```bash
# SSH登录服务器
ssh user@your-server

# 进入项目目录
cd /path/to/rag-website

# 备份现有文件
cp main.py main.py.backup
cp static/index.html static/index.html.backup

# 解压新文件
tar -xzf api-source-update.tar.gz

# 设置执行权限
chmod +x test_*.sh
```

#### 步骤4：安装依赖并重启

```bash
# 安装依赖（httpx已在requirements.txt中）
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

# 重启服务
sudo systemctl restart qa-chat

# 检查状态
sudo systemctl status qa-chat
```

### 方案3：配置Git代理

如果服务器需要通过代理访问GitHub：

```bash
# 设置HTTP代理
git config --global http.proxy http://proxy-server:port
git config --global https.proxy https://proxy-server:port

# 或者取消代理
git config --global --unset http.proxy
git config --global --unset https.proxy

# 然后重试
git pull origin master
```

### 方案4：使用SSH方式

如果HTTPS访问有问题，尝试SSH：

```bash
# 查看当前远程地址
git remote -v

# 切换到SSH方式
git remote set-url origin git@github.com:Carpe912/rag-website.git

# 拉取代码
git pull origin master
```

## 快速部署（跳过Git）

如果你只想快速部署，不管Git：

```bash
# 1. 确保代码已经是最新的（手动上传或其他方式）

# 2. 安装依赖
.venv/bin/pip install -q -r requirements.txt

# 3. 重启服务
sudo systemctl restart qa-chat

# 4. 检查状态
sudo systemctl status qa-chat

# 5. 查看日志
journalctl -u qa-chat -f
```

## 验证部署

### 1. 检查服务状态

```bash
sudo systemctl status qa-chat
```

应该看到：`Active: active (running)`

### 2. 检查日志

```bash
# 查看最近日志
journalctl -u qa-chat -n 50

# 实时查看日志
journalctl -u qa-chat -f
```

### 3. 测试API

```bash
# 测试健康检查
curl http://localhost:8000/api/health

# 测试数据源列表
curl http://localhost:8000/api/sources
```

### 4. 访问界面

打开浏览器访问：`http://your-server:8000`

检查侧边栏是否有"API数据源"区域

## 常见问题

### Q: 服务启动失败

```bash
# 查看详细错误
journalctl -u qa-chat -n 100 --no-pager

# 检查端口占用
sudo lsof -i :8000

# 手动启动测试
cd /path/to/rag-website
.venv/bin/python main.py
```

### Q: 依赖安装失败

```bash
# 清理pip缓存
.venv/bin/pip cache purge

# 重新安装
.venv/bin/pip install --no-cache-dir -r requirements.txt

# 检查Python版本
.venv/bin/python --version  # 应该是3.10+
```

### Q: 找不到模块

```bash
# 确认虚拟环境
which python  # 应该指向.venv/bin/python

# 检查已安装包
.venv/bin/pip list | grep httpx
```

## 回滚方案

如果部署出现问题，可以快速回滚：

```bash
# 恢复备份文件
cp main.py.backup main.py
cp static/index.html.backup static/index.html

# 重启服务
sudo systemctl restart qa-chat
```

## 推荐部署流程

1. **先在测试环境验证**
   ```bash
   # 本地测试
   ./test_all_features.sh
   ```

2. **备份现有文件**
   ```bash
   cp main.py main.py.backup
   cp static/index.html static/index.html.backup
   ```

3. **部署新代码**
   - 使用Git（如果可以）
   - 或手动上传

4. **安装依赖**
   ```bash
   .venv/bin/pip install -r requirements.txt
   ```

5. **重启服务**
   ```bash
   sudo systemctl restart qa-chat
   ```

6. **验证功能**
   - 检查服务状态
   - 访问界面测试
   - 查看日志

## 联系支持

如果遇到无法解决的问题：

1. 收集错误信息
   ```bash
   journalctl -u qa-chat -n 100 > error.log
   ```

2. 检查系统信息
   ```bash
   python --version
   pip list
   systemctl status qa-chat
   ```

3. 提供详细的错误描述

---

**建议**：如果GitHub访问经常有问题，考虑使用方案2（手动上传）或配置稳定的代理。
