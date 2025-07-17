"""
API接口测试用例

测试intent_pipeline.py与后端API的接口兼容性
"""

import json
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from datetime import datetime
from typing import Dict, Any, List

# 导入应用和相关模块
from app.main import create_app
from app.core import PipelineInterface
from app.models import ChatRequest, CreateConversationRequest, StreamResponse, APIResponse


class TestAPIInterface:
    """API接口测试类"""
    
    @pytest.fixture
    def app(self):
        """创建测试应用"""
        app = create_app()
        # 为测试环境手动设置pipeline接口
        from app.core import PipelineInterface
        app.state.pipeline = PipelineInterface()
        return app
    
    @pytest.fixture
    def client(self, app):
        """创建测试客户端"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_pipeline(self):
        """创建Mock的Pipeline接口"""
        mock = Mock(spec=PipelineInterface)
        mock.create_conversation.return_value = "test-conversation-id"
        mock.send_message = AsyncMock()
        mock.get_conversation_history.return_value = []
        mock.get_conversation_summary.return_value = {"summary": "test"}
        mock.list_active_conversations.return_value = []
        mock.close_conversation.return_value = True
        mock.get_statistics.return_value = {"total": 0}
        return mock
    
    def test_create_conversation(self, client, mock_pipeline):
        """测试创建对话接口"""
        # 模拟Pipeline
        with patch('app.main.pipeline_interface', mock_pipeline):
            # 构造请求数据
            request_data = {
                "user_id": "test_user",
                "mode": "workflow"
            }
            
            # 发送请求
            response = client.post("/api/v1/conversations", json=request_data)
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["conversation_id"] == "test-conversation-id"
            assert data["data"]["user_id"] == "test_user"
            assert data["data"]["mode"] == "workflow"
            
            # 验证Pipeline调用
            mock_pipeline.create_conversation.assert_called_once_with("test_user", "workflow")
    
    def test_stream_chat_interface(self, client, mock_pipeline):
        """测试流式聊天接口"""
        # 模拟流式响应
        async def mock_send_message(*args, **kwargs):
            """模拟发送消息的异步生成器"""
            # 返回status响应
            yield StreamResponse(
                conversation_id="test-conversation-id",
                response_type="status",
                stage="initialization"
            )
            
            # 返回content响应
            yield StreamResponse(
                conversation_id="test-conversation-id",
                response_type="content",
                content="这是测试回复"
            )
        
        mock_pipeline.send_message = mock_send_message
        
        with patch('app.main.pipeline_interface', mock_pipeline):
            # 构造请求数据
            request_data = {
                "conversation_id": "test-conversation-id",
                "message": "你好",
                "user_id": "test_user",
                "mode": "workflow"
            }
            
            # 发送流式请求
            response = client.post(
                "/api/v1/conversations/test-conversation-id/stream",
                json=request_data
            )
            
            # 验证响应
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/plain; charset=utf-8"
            
            # 验证流式响应内容
            content = response.content.decode('utf-8')
            assert "data: " in content
            assert "[DONE]" in content
            
            # 解析流式响应
            lines = content.strip().split('\n')
            data_lines = [line for line in lines if line.startswith("data: ")]
            
            # 验证至少有状态和内容响应
            assert len(data_lines) >= 2
            
            # 验证最后一行是结束标记
            assert data_lines[-1] == "data: [DONE]"
    
    def test_intent_pipeline_compatibility(self):
        """测试与intent_pipeline.py的兼容性"""
        # 测试数据模型兼容性
        
        # 1. 测试CreateConversationRequest
        create_request = CreateConversationRequest(
            user_id="test_user",
            mode="workflow"
        )
        assert create_request.user_id == "test_user"
        assert create_request.mode == "workflow"
        
        # 2. 测试ChatRequest
        chat_request = ChatRequest(
            conversation_id="test-conversation-id",
            message="测试消息",
            user_id="test_user",
            mode="workflow",
            metadata={"stream": True}
        )
        assert chat_request.conversation_id == "test-conversation-id"
        assert chat_request.message == "测试消息"
        assert chat_request.user_id == "test_user"
        assert chat_request.mode == "workflow"
        assert chat_request.metadata["stream"] is True
        
        # 3. 测试StreamResponse.to_dict()输出格式
        # 测试content响应
        content_response = StreamResponse(
            conversation_id="test-conversation-id",
            response_type="content",
            content="测试内容"
        )
        content_dict = content_response.to_dict()
        assert content_dict["type"] == "content"
        assert content_dict["content"] == "测试内容"
        assert "timestamp" in content_dict
        
        # 测试status响应
        status_response = StreamResponse(
            conversation_id="test-conversation-id",
            response_type="status",
            stage="initialization"
        )
        status_dict = status_response.to_dict()
        assert status_dict["type"] == "status"
        assert "description" in status_dict
        assert status_dict["stage"] == "initialization"
        
        # 测试error响应
        error_response = StreamResponse(
            conversation_id="test-conversation-id",
            response_type="error",
            error_code="TEST_ERROR",
            error_message="测试错误"
        )
        error_dict = error_response.to_dict()
        assert error_dict["type"] == "error"
        assert error_dict["error"] == "测试错误"
        assert error_dict["code"] == "TEST_ERROR"
    
    def test_error_handling(self, client, mock_pipeline):
        """测试错误处理"""
        # 测试创建对话失败
        mock_pipeline.create_conversation.side_effect = Exception("创建对话失败")
        
        with patch('app.main.pipeline_interface', mock_pipeline):
            request_data = {
                "user_id": "test_user",
                "mode": "workflow"
            }
            
            response = client.post("/api/v1/conversations", json=request_data)
            
            # 验证错误响应
            assert response.status_code == 200  # API返回结构化错误，HTTP状态码仍为200
            data = response.json()
            assert data["success"] is False
            assert "创建对话失败" in data["message"]
            assert data["error_code"] == "CREATE_CONVERSATION_ERROR"
    
    def test_conversation_id_validation(self, client, mock_pipeline):
        """测试对话ID验证"""
        with patch('app.main.pipeline_interface', mock_pipeline):
            # 测试URL中的conversation_id与请求体中的不匹配
            request_data = {
                "conversation_id": "different-conversation-id",
                "message": "测试消息",
                "user_id": "test_user"
            }
            
            response = client.post(
                "/api/v1/conversations/test-conversation-id/stream",
                json=request_data
            )
            
            # 验证返回400错误
            assert response.status_code == 400
            assert "对话ID不匹配" in response.json()["detail"]
    
    def test_token_handling(self, client, mock_pipeline):
        """测试Token处理"""
        with patch('app.main.pipeline_interface', mock_pipeline):
            # 测试带Authorization头的请求
            request_data = {
                "conversation_id": "test-conversation-id",
                "message": "测试消息",
                "user_id": "test_user"
            }
            
            headers = {
                "Authorization": "Bearer test-token-123"
            }
            
            response = client.post(
                "/api/v1/conversations/test-conversation-id/stream",
                json=request_data,
                headers=headers
            )
            
            # 验证请求成功处理
            assert response.status_code == 200
            
            # 测试请求体中的token
            request_data_with_token = {
                "conversation_id": "test-conversation-id",
                "message": "测试消息",
                "user_id": "test_user",
                "user": {
                    "token": "test-token-456"
                }
            }
            
            response = client.post(
                "/api/v1/conversations/test-conversation-id/stream",
                json=request_data_with_token
            )
            
            # 验证请求成功处理
            assert response.status_code == 200


class TestDataModelIntegration:
    """数据模型集成测试类"""
    
    def test_chat_request_get_user_token(self):
        """测试ChatRequest.get_user_token()方法"""
        # 测试带token的请求
        request_with_token = ChatRequest(
            conversation_id="test-conversation-id",
            message="测试消息",
            user_id="test_user",
            user={"token": "test-token"}
        )
        
        assert request_with_token.get_user_token() == "test-token"
        
        # 测试不带token的请求
        request_without_token = ChatRequest(
            conversation_id="test-conversation-id",
            message="测试消息",
            user_id="test_user"
        )
        
        assert request_without_token.get_user_token() is None
    
    def test_stream_response_dict_format(self):
        """测试StreamResponse.to_dict()输出格式符合intent_pipeline.py期望"""
        # 测试各种类型的响应格式
        
        # 1. content类型
        content_response = StreamResponse.create_content_response(
            conversation_id="test-conversation-id",
            content="测试内容"
        )
        content_dict = content_response.to_dict()
        
        expected_keys = ["type", "content", "timestamp"]
        assert all(key in content_dict for key in expected_keys)
        assert content_dict["type"] == "content"
        assert content_dict["content"] == "测试内容"
        
        # 2. status类型
        status_response = StreamResponse.create_status_response(
            conversation_id="test-conversation-id",
            stage="initialization"
        )
        status_dict = status_response.to_dict()
        
        expected_keys = ["type", "description", "stage", "timestamp"]
        assert all(key in status_dict for key in expected_keys)
        assert status_dict["type"] == "status"
        assert "正在初始化" in status_dict["description"]
        assert status_dict["stage"] == "initialization"
        
        # 3. error类型
        error_response = StreamResponse.create_error_response(
            conversation_id="test-conversation-id",
            error_code="TEST_ERROR",
            error_message="测试错误消息"
        )
        error_dict = error_response.to_dict()
        
        expected_keys = ["type", "error", "code", "timestamp"]
        assert all(key in error_dict for key in expected_keys)
        assert error_dict["type"] == "error"
        assert error_dict["error"] == "测试错误消息"
        assert error_dict["code"] == "TEST_ERROR"


class TestPipelineIntegration:
    """Pipeline集成测试类"""
    
    @pytest.fixture
    def pipeline(self):
        """创建Pipeline实例"""
        return PipelineInterface()
    
    def test_create_conversation_workflow(self, pipeline):
        """测试创建工作流对话"""
        conversation_id = pipeline.create_conversation("test_user", "workflow")
        
        assert conversation_id is not None
        assert len(conversation_id) > 0
        assert conversation_id in pipeline.active_conversations
        
        # 验证对话任务类型
        task = pipeline.active_conversations[conversation_id]
        assert task.user_id == "test_user"
        assert task.mode == "workflow"
    
    def test_create_conversation_agent(self, pipeline):
        """测试创建代理对话"""
        conversation_id = pipeline.create_conversation("test_user", "agent")
        
        assert conversation_id is not None
        assert len(conversation_id) > 0
        assert conversation_id in pipeline.active_conversations
        
        # 验证对话任务类型
        task = pipeline.active_conversations[conversation_id]
        assert task.user_id == "test_user"
        assert task.mode == "agent"
    
    def test_invalid_mode_error(self, pipeline):
        """测试无效模式错误"""
        with pytest.raises(ValueError, match="不支持的执行模式"):
            pipeline.create_conversation("test_user", "invalid_mode")
    
    def test_conversation_not_found_error(self, pipeline):
        """测试对话不存在错误"""
        with pytest.raises(ValueError, match="对话不存在"):
            pipeline.get_conversation_history("nonexistent-conversation-id")
    
    def test_close_conversation(self, pipeline):
        """测试关闭对话"""
        conversation_id = pipeline.create_conversation("test_user", "workflow")
        
        # 验证对话存在
        assert conversation_id in pipeline.active_conversations
        
        # 关闭对话
        result = pipeline.close_conversation(conversation_id)
        assert result is True
        
        # 验证对话已移除
        assert conversation_id not in pipeline.active_conversations
        
        # 尝试关闭不存在的对话
        result = pipeline.close_conversation("nonexistent-conversation-id")
        assert result is False
    
    def test_list_active_conversations(self, pipeline):
        """测试列出活跃对话"""
        # 创建多个对话
        conv1 = pipeline.create_conversation("user1", "workflow")
        conv2 = pipeline.create_conversation("user2", "agent")
        conv3 = pipeline.create_conversation("user1", "workflow")
        
        # 获取所有对话
        all_conversations = pipeline.list_active_conversations()
        assert len(all_conversations) == 3
        
        # 按用户过滤
        user1_conversations = pipeline.list_active_conversations("user1")
        assert len(user1_conversations) == 2
        
        user2_conversations = pipeline.list_active_conversations("user2")
        assert len(user2_conversations) == 1
        
        # 验证数据结构
        conv_summary = user1_conversations[0]
        expected_keys = ["conversation_id", "user_id", "mode", "status", "current_stage", 
                        "message_count", "created_at", "updated_at"]
        assert all(key in conv_summary for key in expected_keys)
    
    def test_get_statistics(self, pipeline):
        """测试获取统计信息"""
        # 创建不同类型的对话
        pipeline.create_conversation("user1", "workflow")
        pipeline.create_conversation("user2", "agent")
        pipeline.create_conversation("user3", "workflow")
        
        # 获取统计信息
        stats = pipeline.get_statistics()
        
        # 验证统计信息结构
        expected_keys = ["total_conversations", "workflow_conversations", 
                        "agent_conversations", "status_distribution", "timestamp"]
        assert all(key in stats for key in expected_keys)
        
        # 验证统计数据
        assert stats["total_conversations"] == 3
        assert stats["workflow_conversations"] == 2
        assert stats["agent_conversations"] == 1
        assert "pending" in stats["status_distribution"]


# 运行特定测试的辅助函数
def run_specific_tests():
    """运行特定测试用例"""
    import subprocess
    import sys
    
    # 运行API接口测试
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        "tests/pipeline/test_api_interface.py::TestAPIInterface::test_create_conversation",
        "-v"
    ], capture_output=True, text=True)
    
    print("API接口测试结果:")
    print(result.stdout)
    if result.stderr:
        print("错误信息:")
        print(result.stderr)
    
    return result.returncode == 0


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"]) 