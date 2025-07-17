"""
pytest配置文件

定义全局fixtures和测试配置。
"""

import asyncio
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock
import uuid

from app.config import get_settings
from app.core import PipelineInterface
from app.models import Message, ConversationHistory
from app.services import LLMService, KnowledgeService, LightRagService, SearchService


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings():
    """测试配置"""
    settings = get_settings()
    # 覆盖测试配置
    settings.environment = "testing"
    settings.debug = True
    settings.log_level = "debug"
    settings.openai_api_key = "test_key"
    return settings


@pytest.fixture
def test_user_id():
    """测试用户ID"""
    return "test_user_123"


@pytest.fixture
def test_conversation_id():
    """测试对话ID"""
    return str(uuid.uuid4())


@pytest.fixture
def test_message():
    """测试消息"""
    return Message(
        role="user",
        content="这是一个测试消息",
        metadata={"test": True}
    )


@pytest.fixture
def test_conversation_history(test_conversation_id, test_user_id):
    """测试对话历史"""
    history = ConversationHistory(
        conversation_id=test_conversation_id,
        user_id=test_user_id
    )
    
    # 添加一些测试消息
    history.add_message(Message(
        role="user",
        content="你好",
        metadata={"test": True}
    ))
    
    history.add_message(Message(
        role="assistant", 
        content="您好！有什么可以帮助您的吗？",
        metadata={"test": True}
    ))
    
    return history


@pytest.fixture
def mock_llm_service():
    """模拟LLM服务"""
    service = AsyncMock(spec=LLMService)
    service.generate_response.return_value = "这是一个模拟的LLM响应"
    service.generate_json_response.return_value = {"result": "success"}
    service.generate_stream_response.return_value = async_generator_mock(["模拟", "流式", "响应"])
    return service


@pytest.fixture
def mock_knowledge_service():
    """模拟知识库服务"""
    service = AsyncMock(spec=KnowledgeService)
    service.search_cosmetics_knowledge.return_value = [
        {
            "title": "测试知识",
            "content": "这是测试知识内容",
            "score": 0.9,
            "source": "knowledge_base"
        }
    ]
    service.health_check.return_value = True
    return service


@pytest.fixture
def mock_lightrag_service():
    """模拟LightRAG服务"""
    service = AsyncMock(spec=LightRagService)
    service.search_lightrag.return_value = [
        {
            "title": "LightRAG测试结果",
            "content": "这是LightRAG测试内容",
            "score": 0.8,
            "source": "lightrag"
        }
    ]
    service.health_check.return_value = True
    return service


@pytest.fixture
def mock_search_service():
    """模拟搜索服务"""
    service = AsyncMock(spec=SearchService)
    service.search_online.return_value = [
        {
            "title": "在线搜索测试结果",
            "content": "这是在线搜索测试内容",
            "url": "https://example.com",
            "score": 0.7,
            "source": "online_search"
        }
    ]
    service.health_check.return_value = True
    return service


@pytest.fixture
def pipeline_interface():
    """Pipeline接口实例"""
    return PipelineInterface()


@pytest.fixture
def test_chat_request_data(test_conversation_id):
    """测试聊天请求数据"""
    return {
        "conversation_id": test_conversation_id,
        "message": "请介绍一下透明质酸的作用",
        "user_id": "test_user",
        "metadata": {"test": True}
    }


@pytest.fixture
def test_stream_response_data(test_conversation_id):
    """测试流式响应数据"""
    return {
        "conversation_id": test_conversation_id,
        "response_type": "content",
        "content": "这是测试响应内容",
        "timestamp": "2024-01-01T00:00:00Z"
    }


async def async_generator_mock(items):
    """异步生成器模拟"""
    for item in items:
        yield item


@pytest.fixture
def mock_redis():
    """模拟Redis客户端"""
    redis_mock = AsyncMock()
    redis_mock.get.return_value = None
    redis_mock.set.return_value = True
    redis_mock.delete.return_value = 1
    redis_mock.exists.return_value = False
    redis_mock.ping.return_value = True
    return redis_mock


@pytest.fixture
def mock_database():
    """模拟数据库连接"""
    db_mock = AsyncMock()
    db_mock.execute.return_value = MagicMock()
    db_mock.fetch.return_value = []
    db_mock.fetchrow.return_value = None
    return db_mock


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """设置测试环境"""
    # 设置测试环境变量
    monkeypatch.setenv("ENVIRONMENT", "testing")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setenv("OPENAI_API_KEY", "test_key")


@pytest.fixture
def test_agent_state():
    """测试Agent状态"""
    return {
        "user_question": "测试问题",
        "conversation_history": [],
        "current_stage": "master_agent",
        "final_answer": "",
        "online_search_results": [],
        "knowledge_search_results": [],
        "lightrag_results": [],
        "master_decision": "",
        "need_more_info": True,
        "optimized_queries": {},
        "online_summary": "",
        "knowledge_summary": "",
        "lightrag_summary": "",
        "metadata": {"test": True},
        "execution_path": [],
        "agent_outputs": {}
    }


@pytest.fixture
def test_search_results():
    """测试搜索结果"""
    return [
        {
            "title": "测试结果1",
            "content": "这是测试内容1",
            "url": "https://example1.com",
            "score": 0.9,
            "source": "test",
            "metadata": {"test": True}
        },
        {
            "title": "测试结果2", 
            "content": "这是测试内容2",
            "url": "https://example2.com",
            "score": 0.8,
            "source": "test",
            "metadata": {"test": True}
        }
    ]


# 测试标记
def pytest_configure(config):
    """pytest配置"""
    config.addinivalue_line(
        "markers", "unit: 单元测试标记"
    )
    config.addinivalue_line(
        "markers", "integration: 集成测试标记"
    )
    config.addinivalue_line(
        "markers", "e2e: 端到端测试标记"
    )


# 测试收集钩子
def pytest_collection_modifyitems(config, items):
    """修改测试项目"""
    for item in items:
        # 为异步测试添加asyncio标记
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.asyncio)
        
        # 根据路径添加标记
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)


# 测试会话钩子
@pytest.fixture(scope="session", autouse=True)
def setup_test_session():
    """设置测试会话"""
    print("\n开始测试会话...")
    yield
    print("\n测试会话结束")


@pytest.fixture(autouse=True)
def setup_test_function():
    """设置每个测试函数"""
    # 测试前设置
    yield
    # 测试后清理
