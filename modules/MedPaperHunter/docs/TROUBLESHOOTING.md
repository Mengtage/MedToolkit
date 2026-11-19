# 故障排除指南

## 问题 1: 无法连接 GitHub

**症状**:
```
fatal: unable to access 'https://github.com/...': Failed to connect to github.com port 443
```

**解决方案**:

### 方案 A: 使用快速启动版（推荐）
我们已经为你创建了 `quick_start.py` 单文件版本，可以直接使用！

```bash
# 直接运行快速版
python3 quick_start.py
```

### 方案 B: 配置代理
如果你有代理，配置 Git 使用代理：

```bash
# HTTP 代理
git config --global http.proxy http://127.0.0.1:7890
git config --global https.proxy http://127.0.0.1:7890

# 或 SOCKS5 代理
git config --global http.proxy socks5://127.0.0.1:7890
```

### 方案 C: 使用镜像站
尝试使用 GitHub 镜像：

```bash
# 使用 GitHub 镜像（如果有的话）
git clone https://mirror.ghproxy.com/https://github.com/Mengtage/MedPaperHunter.git
```

---

## 问题 2: Python 命令找不到

**症状**:
```
zsh: command not found: python
```

**解决方案**:

### 检查 Python 3
Mac 通常默认有 python3：

```bash
# 检查 python3 是否可用
python3 --version

# 使用 python3 替代 python
python3 quick_start.py
```

### 创建 python 别名（可选）
```bash
# 在 ~/.zshrc 中添加
echo 'alias python="python3"' >> ~/.zshrc
echo 'alias pip="pip3"' >> ~/.zshrc
source ~/.zshrc
```

### 安装 Python 3（如果没有）
```bash
# 使用 Homebrew 安装
brew install python3
```

---

## 问题 3: 找不到 requirements.txt

**症状**:
```
ERROR: Could not open requirements file: [Errno 2] No such file or directory
```

**解决方案**:

确保你在正确的目录：

```bash
# 检查当前目录
pwd

# 查看目录内容
ls -la

# 如果文件不存在，使用快速启动版
python3 quick_start.py
```

---

## 问题 4: 模块导入错误

**症状**:
```
ModuleNotFoundError: No module named 'xxx'
```

**解决方案**:

安装缺失的依赖：

```bash
# 安装所有依赖
pip3 install requests beautifulsoup4 lxml openpyxl pandas pymupdf

# 或者分步骤安装
pip3 install requests
pip3 install beautifulsoup4
pip3 install lxml
pip3 install openpyxl
pip3 install pandas
pip3 install pymupdf
```

---

## 快速开始（跳过 GitHub）

如果你不想处理 GitHub，可以直接使用我们的快速启动版：

```bash
# 1. 确保你有 Python 3
python3 --version

# 2. 安装依赖
pip3 install requests beautifulsoup4 lxml openpyxl pandas pymupdf

# 3. 运行快速版
python3 quick_start.py "你的研究主题"
```

---

## 完整检查清单

运行这个命令检查你的环境：

```bash
echo "=== 环境检查 ==="
echo "Python 版本:"
python3 --version 2>/dev/null || python --version 2>/dev/null || echo "未找到 Python"

echo -e "\nPIP 版本:"
pip3 --version 2>/dev/null || pip --version 2>/dev/null || echo "未找到 PIP"

echo -e "\n当前目录:"
pwd

echo -e "\n目录内容:"
ls -la

echo -e "\n网络连接测试:"
ping -c 3 github.com 2>/dev/null || echo "无法连接 GitHub"
```

---

## 还需要帮助？

如果以上方法都无法解决问题，请：

1. 运行快速启动版 `python3 quick_start.py`
2. 查看 `quick_start.py` 中的代码，它是自包含的
3. 根据需要手动复制代码到你的环境

祝你使用愉快！

