# 环境设置指南

## Python 环境检查

你的系统已安装：
- ✅ Python 3.13.5
- ✅ pip3 可用

## 解决方案

### 方案 1: 使用 `pip3` (推荐)

直接使用 `pip3` 代替 `pip`：

```bash
cd backend
pip3 install -r requirements.txt
```

### 方案 2: 使用 `python3 -m pip`

```bash
cd backend
python3 -m pip install -r requirements.txt
```

### 方案 3: 创建别名 (可选)

如果你想使用 `pip` 命令，可以在 `~/.zshrc` 中添加别名：

```bash
echo 'alias pip=pip3' >> ~/.zshrc
source ~/.zshrc
```

## 安装依赖

```bash
# 进入后端目录
cd backend

# 安装依赖
pip3 install -r requirements.txt

# 或者
python3 -m pip install -r requirements.txt
```

## 设置环境变量

```bash
# 对于 SQLite (本地开发)
export DATABASE_URL="sqlite:///./mgx_engine.db"

# 或者创建 .env 文件
echo 'DATABASE_URL=sqlite:///./mgx_engine.db' > .env
```

## 运行服务器

```bash
# 方法 1: 使用 uvicorn
uvicorn app.main:app --reload

# 方法 2: 使用 Python
python3 -m uvicorn app.main:app --reload

# 方法 3: 直接运行
python3 -m app.main
```

## 运行测试

```bash
# 安装测试依赖（如果还没安装）
pip3 install -r requirements.txt

# 运行测试
pytest

# 或使用 Python 模块方式
python3 -m pytest
```

## 验证安装

```bash
# 检查 Python 版本
python3 --version

# 检查 pip 版本
pip3 --version

# 检查已安装的包
pip3 list | grep -E "(fastapi|sqlalchemy|pydantic)"
```

