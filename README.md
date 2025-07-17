# 化妆品知识库问答机器人Pipeline项目

## 项目概述

这是一个智能化妆品知识库问答系统，支持两种执行模式：

- **Workflow模式**：固定流程的多轮对话任务
- **Agent模式**：基于LangGraph的智能代理系统

## 技术架构

- **Workflow实现**：使用HTTP请求进行流式聊天接口调用
- **Agent实现**：基于LangGraph框架，支持流式响应
- **知识检索**：集成多源知识库API
  - 化妆品专业知识库
  - LightRAG检索系统
  - 在线搜索引擎

## 快速开始

### 环境要求

- Python 3.11+
- Redis 7.0+

### 安装依赖

**快速安装（推荐）：**
```bash
# 使用自动安装脚本
python scripts/install_deps.py
```

**手动安装：**
```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

> 📖 **详细安装指南**：如果遇到安装问题，请查看 [INSTALL.md](INSTALL.md) 获取详细的安装步骤和故障排除方案。

### 配置环境

```bash
# 复制环境配置文件
cp .env.example .env

# 编辑配置文件，填入相应的API密钥和配置
vim .env
```

### 运行应用

```bash
# 开发模式
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 生产模式
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 使用Docker

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d
```

## API文档

启动应用后，访问以下地址查看API文档：

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 项目结构

```
intent_agent_pipeline/
├── app/                    # 应用主目录
│   ├── config/            # 配置管理
│   ├── core/              # 核心业务逻辑
│   ├── agents/            # 智能代理
│   ├── langgraph/         # LangGraph工作流
│   ├── services/          # 外部服务接口
│   ├── models/            # 数据模型
│   ├── api/               # API接口
│   └── utils/             # 工具函数
├── tests/                 # 测试目录
├── docker/                # Docker配置
└── requirements.txt       # 依赖文件
```

## 开发指南

### 代码规范

- 使用pytest进行测试
- 遵循PEP 8代码规范

### 运行测试

```bash
# 运行所有测试
pytest

# 运行单元测试
pytest tests/unit/

# 运行集成测试
pytest tests/integration/

# 生成覆盖率报告
pytest --cov=app tests/
```

## 许可证

MIT License
