# Git 清理指南

## 如何清除 Git 中已跟踪的文件

如果您之前已经将一些应该被忽略的文件提交到了 Git，需要清除它们，请按照以下步骤操作。

### ⚠️ 重要提示

在执行清理操作前，**请先备份您的代码**或确保已提交所有重要更改！

```bash
# 1. 先提交当前的更改（如果有）
git add .
git commit -m "保存当前工作"
```

---

## 方法一：清除已跟踪但应被忽略的文件（推荐）

此方法会从 Git 索引中移除文件，但**保留本地文件**。

### 1. 确保 .gitignore 已正确配置

确保 `.gitignore` 文件包含所有需要忽略的规则（已创建）。

### 2. 清除 Git 缓存

```bash
# 移除所有已跟踪的文件（保留本地文件）
git rm -r --cached .

# 重新添加所有文件（.gitignore 规则会生效）
git add .

# 提交更改
git commit -m "清理 Git 缓存，应用 .gitignore 规则"
```

### 3. 推送到远程仓库（如果使用）

```bash
git push origin <branch-name>
```

---

## 方法二：仅清除特定目录/文件

如果您只想清除某些特定的已跟踪文件：

```bash
# 清除后端虚拟环境（保留本地文件）
git rm -r --cached backend/venv

# 清除前端 node_modules（保留本地文件）
git rm -r --cached frontend/node_modules

# 清除上传的文件（保留本地文件）
git rm -r --cached backend/uploads/
git rm -r --cached backend/data/

# 重新添加（.gitignore 会生效）
git add .
git commit -m "清除应忽略的文件"
```

---

## 方法三：完全重置（⚠️ 谨慎使用）

如果您想完全清除 Git 历史并重新开始：

```bash
# ⚠️ 警告：这会删除所有 Git 历史！

# 1. 删除 .git 目录
rm -rf .git

# 2. 重新初始化 Git
git init

# 3. 添加所有文件（.gitignore 会生效）
git add .

# 4. 创建初始提交
git commit -m "Initial commit with .gitignore"

# 5. 添加远程仓库（如果需要）
git remote add origin <repository-url>
git push -u origin main
```

---

## 验证清理结果

清理后，验证 Git 状态：

```bash
# 查看 Git 状态
git status

# 应该只显示已修改或新文件，不显示已忽略的文件
# 例如：
#   modified:   README.md
#   modified:   .gitignore
#   不应该显示：venv/, node_modules/, __pycache__/ 等
```

---

## 常用 Git 清理命令

### 查看被跟踪但应被忽略的文件

```bash
# 列出被跟踪但匹配 .gitignore 的文件
git ls-files -i --exclude-standard
```

### 清除特定类型的文件

```bash
# 清除所有 .pyc 文件
find . -name "*.pyc" -exec git rm --cached {} \;

# 清除所有 __pycache__ 目录
find . -type d -name "__pycache__" -exec git rm -r --cached {} \;
```

### 查看 Git 仓库大小

```bash
# 查看仓库大小
git count-objects -vH
```

---

## 推荐工作流程

### 首次设置（新项目）

```bash
# 1. 创建 .gitignore（已完成）
# 2. 初始化 Git（如果还没有）
git init

# 3. 添加文件
git add .

# 4. 首次提交
git commit -m "Initial commit"
```

### 清理已存在的仓库

```bash
# 1. 确保 .gitignore 已更新（已完成）
# 2. 清除缓存并重新应用规则
git rm -r --cached .
git add .
git commit -m "Apply .gitignore rules"

# 3. 推送更改
git push
```

---

## 需要忽略的常见文件类型

本项目已配置忽略以下内容：

### Python
- `__pycache__/` - Python 缓存
- `*.pyc` - 编译的 Python 文件
- `venv/` - 虚拟环境
- `*.egg-info/` - 包信息

### Node.js
- `node_modules/` - Node 依赖
- `dist/` - 构建产物
- `*.log` - 日志文件

### 运行时数据
- `backend/data/` - 运行时生成的数据
- `backend/uploads/` - 上传的文件
- `*.json` - 运行时配置文件（某些）

### IDE 和系统文件
- `.vscode/` - VS Code 配置
- `.idea/` - IntelliJ IDEA 配置
- `.DS_Store` - macOS 系统文件
- `Thumbs.db` - Windows 缩略图

---

## 注意事项

1. **备份重要数据**：清理前确保重要文件已备份
2. **检查 .gitignore**：确保规则正确，避免误删重要文件
3. **测试清理结果**：清理后检查 `git status` 确认结果
4. **团队协作**：如果多人协作，清理后需要团队成员更新本地仓库

---

## 如果清理后出现问题

### 恢复被误删的文件

```bash
# 查看最近的提交
git log --oneline

# 恢复到清理前的状态
git reset --soft HEAD~1

# 或者恢复到特定提交
git reset --hard <commit-hash>
```

### 恢复本地文件（如果被误删）

如果本地文件也被删除（使用了 `git rm` 而非 `git rm --cached`）：

```bash
# 从最近的提交恢复
git checkout HEAD -- <file-path>

# 恢复整个目录
git checkout HEAD -- backend/venv/
```

---

## 快速检查清单

清理前检查：

- [ ] `.gitignore` 文件已创建并配置正确
- [ ] 重要文件已备份或已提交
- [ ] 了解清理操作的影响范围
- [ ] 已与团队成员沟通（如果协作开发）

清理后检查：

- [ ] `git status` 显示正常
- [ ] 本地文件仍然存在（如果使用了 `--cached`）
- [ ] `.gitignore` 规则生效
- [ ] 提交和推送成功

