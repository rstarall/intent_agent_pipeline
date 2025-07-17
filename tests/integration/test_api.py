"""
API集成测试

测试FastAPI应用的API接口。
"""

import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from app.main import create_app
from app.core import PipelineInterface


@pytest.fixture
def app():
    """创建测试应用"""
    return create_app()


@pytest.fixture
def client(app):
    """创建测试客户端"""
    return TestClient(app)


@pytest.fixture
def mock_pipeline():
    """模拟Pipeline接口"""
    pipeline = AsyncMock(spec=PipelineInterface)
    pipeline.create_conversation.return_value = "test-conversation-123"
    pipeline.get_conversation_history.return_value = []
    pipeline.get_conversation_summary.return_value = {
        "conversation_id": "test-conversation-123",
        "user_id": "test_user",
        "mode": "workflow",
        "status": "active"
    }
    pipeline.list_active_conversations.return_value = []
    pipeline.close_conversation.return_value = True
    pipeline.get_statistics.return_value = {
        "total_conversations": 0,
        "workflow_conversations": 0,
        "agent_conversations": 0
    }
    return pipeline


class TestHealthAPI:
    """健康检查API测试"""
    
    def test_basic_health_check(self, client):
        """测试基础健康检查"""
        response = client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"
        assert "timestamp" in data
    
    def test_detailed_health_check(self, client):
        """测试详细健康检查"""
        with patch('app.services.KnowledgeService.health_check', new_callable=AsyncMock) as mock_knowledge:
            with patch('app.services.LightRagService.health_check', new_callable=AsyncMock) as mock_lightrag:
                with patch('app.services.SearchService.health_check', new_callable=AsyncMock) as mock_search:
                    mock_knowledge.return_value = True
                    mock_lightrag.return_value = True
                    mock_search.return_value = True
                    
                    response = client.get("/api/v1/health/detailed")
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data["success"] is True
                    assert "data" in data
                    assert "services" in data["data"]
    
    def test_service_health_check(self, client):
        """测试单个服务健康检查"""
        with patch('app.services.KnowledgeService.health_check', new_callable=AsyncMock) as mock_health:
            mock_health.return_value = True
            
            response = client.get("/api/v1/health/services/knowledge")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
    
    def test_unknown_service_health_check(self, client):
        """测试未知服务健康检查"""
        response = client.get("/api/v1/health/services/unknown")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "未知的服务名称" in data["message"]
    
    def test_health_stats(self, client):
        """测试健康统计信息"""
        response = client.get("/api/v1/health/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "application" in data["data"]
        assert "configuration" in data["data"]


class TestPipelineAPI:
    """Pipeline API测试"""
    
    def test_create_conversation(self, client, mock_pipeline):
        """测试创建对话"""
        with patch('app.main.app.state.pipeline', mock_pipeline):
            response = client.post(
                "/api/v1/conversations",
                params={"user_id": "test_user", "mode": "workflow"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["conversation_id"] == "test-conversation-123"
            assert data["data"]["user_id"] == "test_user"
            assert data["data"]["mode"] == "workflow"
    
    def test_send_message(self, client, mock_pipeline):
        """测试发送消息"""
        # 模拟流式响应
        async def mock_send_message(*args, **kwargs):
            from app.models import StreamResponse
            yield StreamResponse.create_content_response("test-conv", "测试回答")
        
        mock_pipeline.send_message.return_value = mock_send_message()
        
        with patch('app.main.app.state.pipeline', mock_pipeline):
            request_data = {
                "conversation_id": "test-conversation-123",
                "message": "测试问题",
                "user_id": "test_user"
            }
            
            response = client.post(
                "/api/v1/conversations/test-conversation-123/messages",
                json=request_data
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "message" in data["data"]
    
    def test_stream_chat(self, client, mock_pipeline):
        """测试流式聊天"""
        # 模拟流式响应
        async def mock_send_message(*args, **kwargs):
            from app.models import StreamResponse
            yield StreamResponse.create_status_response("test-conv", "analyzing_question")
            yield StreamResponse.create_content_response("test-conv", "测试")
            yield StreamResponse.create_content_response("test-conv", "回答")
        
        mock_pipeline.send_message.return_value = mock_send_message()
        
        with patch('app.main.app.state.pipeline', mock_pipeline):
            request_data = {
                "conversation_id": "test-conversation-123",
                "message": "测试问题",
                "user_id": "test_user"
            }
            
            response = client.post(
                "/api/v1/conversations/test-conversation-123/stream",
                json=request_data
            )
            
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/plain; charset=utf-8"
            
            # 检查流式响应内容
            content = response.text
            assert "data:" in content
    
    def test_get_conversation_history(self, client, mock_pipeline):
        """测试获取对话历史"""
        from app.models import Message
        
        mock_pipeline.get_conversation_history.return_value = [
            Message(role="user", content="用户消息"),
            Message(role="assistant", content="助手回复")
        ]
        
        with patch('app.main.app.state.pipeline', mock_pipeline):
            response = client.get("/api/v1/conversations/test-conversation-123/history")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["data"]["messages"]) == 2
    
    def test_get_conversation_summary(self, client, mock_pipeline):
        """测试获取对话摘要"""
        with patch('app.main.app.state.pipeline', mock_pipeline):
            response = client.get("/api/v1/conversations/test-conversation-123/summary")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["conversation_id"] == "test-conversation-123"
    
    def test_list_conversations(self, client, mock_pipeline):
        """测试列出对话"""
        mock_pipeline.list_active_conversations.return_value = [
            {
                "conversation_id": "conv1",
                "user_id": "user1",
                "mode": "workflow",
                "status": "active"
            }
        ]
        
        with patch('app.main.app.state.pipeline', mock_pipeline):
            response = client.get("/api/v1/conversations")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["data"]["conversations"]) == 1
    
    def test_close_conversation(self, client, mock_pipeline):
        """测试关闭对话"""
        with patch('app.main.app.state.pipeline', mock_pipeline):
            response = client.delete("/api/v1/conversations/test-conversation-123")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
    
    def test_get_statistics(self, client, mock_pipeline):
        """测试获取统计信息"""
        with patch('app.main.app.state.pipeline', mock_pipeline):
            response = client.get("/api/v1/statistics")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "total_conversations" in data["data"]
    
    def test_conversation_id_mismatch(self, client, mock_pipeline):
        """测试对话ID不匹配"""
        with patch('app.main.app.state.pipeline', mock_pipeline):
            request_data = {
                "conversation_id": "different-id",
                "message": "测试问题",
                "user_id": "test_user"
            }
            
            response = client.post(
                "/api/v1/conversations/test-conversation-123/messages",
                json=request_data
            )
            
            assert response.status_code == 400
            assert "对话ID不匹配" in response.json()["detail"]


class TestErrorHandling:
    """错误处理测试"""
    
    def test_404_error(self, client):
        """测试404错误"""
        response = client.get("/nonexistent-endpoint")
        
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert "不存在" in data["message"]
    
    def test_validation_error(self, client, mock_pipeline):
        """测试验证错误"""
        with patch('app.main.app.state.pipeline', mock_pipeline):
            # 发送无效数据
            response = client.post(
                "/api/v1/conversations",
                params={"user_id": "", "mode": "invalid_mode"}
            )
            
            # 应该返回验证错误
            assert response.status_code in [400, 422]
    
    def test_internal_server_error(self, client, mock_pipeline):
        """测试内部服务器错误"""
        mock_pipeline.create_conversation.side_effect = Exception("测试异常")
        
        with patch('app.main.app.state.pipeline', mock_pipeline):
            response = client.post(
                "/api/v1/conversations",
                params={"user_id": "test_user", "mode": "workflow"}
            )
            
            assert response.status_code == 500
            data = response.json()
            assert data["success"] is False
            assert "内部服务器错误" in data["message"]


class TestRootEndpoint:
    """根端点测试"""
    
    def test_root_endpoint(self, client):
        """测试根端点"""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert "docs" in data
        assert "health" in data
