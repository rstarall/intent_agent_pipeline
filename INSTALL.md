# 安装指南

本文档提供了详细的安装步骤和常见问题解决方案。

## 环境要求

- Python 3.11+
- Redis 7.0+（可选，用于缓存）

## 快速安装

### 方法1：使用安装脚本（推荐）

```bash
# 运行自动安装脚本
python scripts/install_deps.py
```

### 方法2：手动安装

```bash
# 1. 创建虚拟环境
python -m venv venv

# 2. 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 3. 升级pip
python -m pip install --upgrade pip

# 4. 安装核心依赖
pip install -r requirements.txt

# 5. 安装开发依赖（可选）
pip install -r requirements-dev.txt
```

## 常见问题解决

### 1. structlog 导入错误

如果遇到 `无法解析导入"structlog.stdlib"` 错误：

```bash
# 安装 structlog
pip install structlog>=23.1.0

# 如果仍有问题，尝试重新安装
pip uninstall structlog
pip install structlog>=23.1.0
```

### 2. 其他包导入问题

对于其他包的导入问题，可以逐个安装：

```bash
# 安装特定包
pip install fastapi uvicorn pydantic redis aiohttp httpx

# 安装 LangChain 相关包
pip install langgraph langchain langchain-openai langchain-community

# 安装数据处理包
pip install pandas numpy

# 安装工具包
pip install python-multipart python-dotenv pyyaml jinja2
```

### 3. 开发工具安装问题

如果开发工具安装失败，可以选择性安装：

```bash
# 测试工具
pip install pytest pytest-asyncio

# 基本开发工具（可选）
pip install pytest-cov
```

### 4. 可选依赖

以下依赖是可选的，安装失败不会影响核心功能：

```bash
# 高性能事件循环（Linux/Mac）
pip install uvloop
```

## 验证安装

运行以下命令验证安装：

```bash
# 检查核心包
python -c "import fastapi, uvicorn, pydantic, redis; print('核心包安装成功')"

# 检查 LangChain 包
python -c "import langgraph, langchain; print('LangChain包安装成功')"

# 检查日志包
python -c "import structlog; print('日志包安装成功')"

# 运行测试（如果安装了开发依赖）
pytest --version
```

## 配置环境

安装完成后，需要配置环境：

```bash
# 1. 复制环境配置文件
cp .env.example .env

# 2. 编辑配置文件
# 填入你的 OpenAI API 密钥和其他配置
vim .env  # 或使用其他编辑器
```

## 运行应用

```bash
# 开发模式
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 或者使用 Docker
docker-compose -f docker/docker-compose.dev.yml up --build
```

## 故障排除

### Python 版本问题

确保使用 Python 3.11 或更高版本：

```bash
python --version
# 应该显示 Python 3.11.x 或更高
```

### 虚拟环境问题

如果虚拟环境有问题，删除并重新创建：

```bash
# 删除虚拟环境
rm -rf venv  # Linux/Mac
rmdir /s venv  # Windows

# 重新创建
python -m venv venv
```

### 网络问题

如果下载包时遇到网络问题，可以使用国内镜像：

```bash
# 使用清华镜像
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/

# 或使用阿里镜像
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
```

### 权限问题

在某些系统上可能需要管理员权限：

```bash
# Windows（以管理员身份运行命令提示符）
pip install -r requirements.txt

# Linux/Mac
sudo pip install -r requirements.txt
# 或者使用用户安装
pip install --user -r requirements.txt
```

## 获取帮助

如果遇到其他问题：

1. 检查错误信息，通常会提示具体的问题
2. 确保网络连接正常
3. 尝试更新 pip：`python -m pip install --upgrade pip`
4. 查看项目的 GitHub Issues 页面
5. 联系项目维护者

## 最小化安装

如果只需要运行核心功能，可以只安装最基本的依赖：

```bash
pip install fastapi uvicorn pydantic redis python-dotenv
```

这样可以运行基本的 API 服务，但可能缺少一些高级功能。
