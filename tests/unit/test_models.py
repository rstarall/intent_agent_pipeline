"""
数据模型单元测试

测试各种数据模型的功能和验证逻辑。
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from app.models import (
    Message, ConversationHistory, ChatRequest, ChatResponse,
    StreamResponse, APIResponse, SearchResult,
    TaskStatus, ResponseType, MessageRole
)


class TestMessage:
    """Message模型测试"""
    
    def test_create_message(self):
        """测试创建消息"""
        message = Message(
            role="user",
            content="测试消息",
            metadata={"test": True}
        )
        
        assert message.role == "user"
        assert message.content == "测试消息"
        assert message.metadata == {"test": True}
        assert isinstance(message.timestamp, datetime)
    
    def test_message_to_dict(self):
        """测试消息转字典"""
        message = Message(
            role="assistant",
            content="助手回复",
            metadata={"source": "test"}
        )
        
        data = message.to_dict()
        
        assert data["role"] == "assistant"
        assert data["content"] == "助手回复"
        assert data["metadata"] == {"source": "test"}
        assert "timestamp" in data
    
    def test_message_from_dict(self):
        """测试从字典创建消息"""
        data = {
            "role": "user",
            "content": "用户消息",
            "timestamp": "2024-01-01T00:00:00",
            "metadata": {"test": True}
        }
        
        message = Message.from_dict(data)
        
        assert message.role == "user"
        assert message.content == "用户消息"
        assert message.metadata == {"test": True}
    
    def test_invalid_role(self):
        """测试无效角色"""
        with pytest.raises(ValidationError):
            Message(
                role="invalid_role",
                content="测试消息"
            )
    
    def test_empty_content(self):
        """测试空内容"""
        with pytest.raises(ValidationError):
            Message(
                role="user",
                content=""
            )


class TestConversationHistory:
    """ConversationHistory模型测试"""
    
    def test_create_conversation_history(self):
        """测试创建对话历史"""
        history = ConversationHistory(
            conversation_id="test-conv-123",
            user_id="test-user-456"
        )
        
        assert history.conversation_id == "test-conv-123"
        assert history.user_id == "test-user-456"
        assert len(history.messages) == 0
        assert isinstance(history.created_at, datetime)
    
    def test_add_message(self):
        """测试添加消息"""
        history = ConversationHistory(
            conversation_id="test-conv",
            user_id="test-user"
        )
        
        message = Message(role="user", content="测试消息")
        history.add_message(message)
        
        assert len(history.messages) == 1
        assert history.messages[0] == message
    
    def test_get_recent_messages(self):
        """测试获取最近消息"""
        history = ConversationHistory(
            conversation_id="test-conv",
            user_id="test-user"
        )
        
        # 添加多条消息
        for i in range(15):
            message = Message(role="user", content=f"消息{i}")
            history.add_message(message)
        
        # 获取最近10条
        recent = history.get_recent_messages(10)
        assert len(recent) == 10
        assert recent[-1].content == "消息14"
    
    def test_get_messages_by_role(self):
        """测试按角色获取消息"""
        history = ConversationHistory(
            conversation_id="test-conv",
            user_id="test-user"
        )
        
        # 添加不同角色的消息
        history.add_message(Message(role="user", content="用户消息1"))
        history.add_message(Message(role="assistant", content="助手回复1"))
        history.add_message(Message(role="user", content="用户消息2"))
        
        user_messages = history.get_messages_by_role("user")
        assert len(user_messages) == 2
        assert all(msg.role == "user" for msg in user_messages)
        
        assistant_messages = history.get_messages_by_role("assistant")
        assert len(assistant_messages) == 1
        assert assistant_messages[0].role == "assistant"
    
    def test_to_langchain_format(self):
        """测试转换为LangChain格式"""
        history = ConversationHistory(
            conversation_id="test-conv",
            user_id="test-user"
        )
        
        history.add_message(Message(role="user", content="用户消息"))
        history.add_message(Message(role="assistant", content="助手回复"))
        
        langchain_format = history.to_langchain_format()
        
        assert len(langchain_format) == 2
        assert langchain_format[0] == {"role": "user", "content": "用户消息"}
        assert langchain_format[1] == {"role": "assistant", "content": "助手回复"}


class TestStreamResponse:
    """StreamResponse模型测试"""
    
    def test_create_status_response(self):
        """测试创建状态响应"""
        response = StreamResponse.create_status_response(
            conversation_id="test-conv",
            stage="analyzing_question",
            status="running",
            progress=0.5
        )
        
        assert response.conversation_id == "test-conv"
        assert response.response_type == "status"
        assert response.stage == "analyzing_question"
        assert response.status == "running"
        assert response.progress == 0.5
    
    def test_create_content_response(self):
        """测试创建内容响应"""
        response = StreamResponse.create_content_response(
            conversation_id="test-conv",
            content="这是响应内容",
            metadata={"source": "test"}
        )
        
        assert response.conversation_id == "test-conv"
        assert response.response_type == "content"
        assert response.content == "这是响应内容"
        assert response.metadata == {"source": "test"}
    
    def test_create_error_response(self):
        """测试创建错误响应"""
        response = StreamResponse.create_error_response(
            conversation_id="test-conv",
            error_code="TEST_ERROR",
            error_message="测试错误消息"
        )
        
        assert response.conversation_id == "test-conv"
        assert response.response_type == "error"
        assert response.error_code == "TEST_ERROR"
        assert response.error_message == "测试错误消息"
    
    def test_to_dict(self):
        """测试转换为字典"""
        response = StreamResponse.create_content_response(
            conversation_id="test-conv",
            content="测试内容"
        )
        
        data = response.to_dict()
        
        assert data["conversation_id"] == "test-conv"
        assert data["response_type"] == "content"
        assert data["content"] == "测试内容"
        assert "timestamp" in data


class TestAPIResponse:
    """APIResponse模型测试"""
    
    def test_success_response(self):
        """测试成功响应"""
        response = APIResponse.success_response(
            message="操作成功",
            data={"result": "success"}
        )
        
        assert response.success is True
        assert response.message == "操作成功"
        assert response.data == {"result": "success"}
        assert response.error_code is None
    
    def test_error_response(self):
        """测试错误响应"""
        response = APIResponse.error_response(
            message="操作失败",
            error_code="TEST_ERROR",
            data={"details": "错误详情"}
        )
        
        assert response.success is False
        assert response.message == "操作失败"
        assert response.error_code == "TEST_ERROR"
        assert response.data == {"details": "错误详情"}


class TestSearchResult:
    """SearchResult模型测试"""
    
    def test_create_search_result(self):
        """测试创建搜索结果"""
        result = SearchResult(
            title="测试标题",
            content="测试内容",
            url="https://example.com",
            score=0.9,
            source="test_source",
            metadata={"category": "test"}
        )
        
        assert result.title == "测试标题"
        assert result.content == "测试内容"
        assert result.url == "https://example.com"
        assert result.score == 0.9
        assert result.source == "test_source"
        assert result.metadata == {"category": "test"}
    
    def test_to_dict(self):
        """测试转换为字典"""
        result = SearchResult(
            title="测试标题",
            content="测试内容",
            source="test_source"
        )
        
        data = result.to_dict()
        
        assert data["title"] == "测试标题"
        assert data["content"] == "测试内容"
        assert data["source"] == "test_source"
        assert data["url"] is None
        assert data["score"] is None


class TestEnums:
    """枚举类型测试"""
    
    def test_task_status_enum(self):
        """测试任务状态枚举"""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.ERROR.value == "error"
        assert TaskStatus.CANCELLED.value == "cancelled"
    
    def test_response_type_enum(self):
        """测试响应类型枚举"""
        assert ResponseType.STATUS.value == "status"
        assert ResponseType.CONTENT.value == "content"
        assert ResponseType.PROGRESS.value == "progress"
        assert ResponseType.ERROR.value == "error"
    
    def test_message_role_enum(self):
        """测试消息角色枚举"""
        assert MessageRole.USER.value == "user"
        assert MessageRole.ASSISTANT.value == "assistant"
        assert MessageRole.SYSTEM.value == "system"
