"""
Pipeline集成测试

测试Pipeline接口的完整功能。
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock

from app.core import PipelineInterface
from app.models import Message, StreamResponse


class TestPipelineInterface:
    """Pipeline接口集成测试"""
    
    @pytest.fixture
    def pipeline(self):
        """Pipeline接口实例"""
        return PipelineInterface()
    
    def test_create_conversation(self, pipeline):
        """测试创建对话"""
        user_id = "test_user_123"
        mode = "workflow"
        
        conversation_id = pipeline.create_conversation(user_id, mode)
        
        assert conversation_id is not None
        assert len(conversation_id) > 0
        assert conversation_id in pipeline.active_conversations
        
        # 验证对话任务
        task = pipeline.active_conversations[conversation_id]
        assert task.user_id == user_id
        assert task.mode == mode
        assert task.status == "pending"
    
    def test_create_agent_conversation(self, pipeline):
        """测试创建Agent对话"""
        user_id = "test_user_456"
        mode = "agent"
        
        conversation_id = pipeline.create_conversation(user_id, mode)
        
        assert conversation_id in pipeline.active_conversations
        
        task = pipeline.active_conversations[conversation_id]
        assert task.mode == "agent"
    
    @pytest.mark.asyncio
    async def test_send_message_workflow(self, pipeline):
        """测试发送消息（工作流模式）"""
        # 创建对话
        user_id = "test_user"
        conversation_id = pipeline.create_conversation(user_id, "workflow")
        
        # 模拟服务响应
        with patch.multiple(
            'app.core.workflow_task.WorkflowTask',
            _execute_online_search=AsyncMock(return_value=[{"title": "测试结果", "content": "测试内容"}]),
            _execute_knowledge_search=AsyncMock(return_value=[{"title": "知识结果", "content": "知识内容"}]),
            _execute_lightrag_search=AsyncMock(return_value=[{"title": "LightRAG结果", "content": "LightRAG内容"}])
        ):
            with patch('app.services.LLMService.generate_response', new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = "这是一个测试回答"
                
                # 发送消息并收集响应
                responses = []
                async for response in pipeline.send_message(conversation_id, "测试问题", user_id):
                    responses.append(response)
                
                # 验证响应
                assert len(responses) > 0
                
                # 检查是否有状态响应
                status_responses = [r for r in responses if r.response_type == "status"]
                assert len(status_responses) > 0
                
                # 检查是否有内容响应
                content_responses = [r for r in responses if r.response_type == "content"]
                assert len(content_responses) > 0
                
                # 验证最终回答
                final_content = "".join(r.content for r in content_responses if r.content)
                assert len(final_content) > 0
    
    @pytest.mark.asyncio
    async def test_send_message_agent(self, pipeline):
        """测试发送消息（Agent模式）"""
        # 创建Agent对话
        user_id = "test_user"
        conversation_id = pipeline.create_conversation(user_id, "agent")
        
        # 模拟LangGraph响应
        mock_chunks = [
            {"node": "master_agent", "output": {"decision": "continue", "reasoning": "需要更多信息"}},
            {"node": "query_optimizer", "output": {"optimized_queries": {"online_search": "优化查询"}}},
            {"node": "parallel_search", "output": {"search_results": {"online": [{"title": "结果"}]}}},
            {"node": "final_output", "output": {"final_answer": "最终回答"}}
        ]
        
        with patch('app.langgraph.LangGraphManager.stream_workflow') as mock_stream:
            mock_stream.return_value = async_generator_mock(mock_chunks)
            
            with patch('app.langgraph.LangGraphManager.get_final_state') as mock_final:
                mock_final.return_value = {"final_answer": "最终回答"}
                
                # 发送消息并收集响应
                responses = []
                async for response in pipeline.send_message(conversation_id, "测试问题", user_id):
                    responses.append(response)
                
                # 验证响应
                assert len(responses) > 0
                
                # 检查是否有内容响应
                content_responses = [r for r in responses if r.response_type == "content"]
                assert len(content_responses) > 0
    
    def test_get_conversation_history(self, pipeline):
        """测试获取对话历史"""
        # 创建对话并添加消息
        user_id = "test_user"
        conversation_id = pipeline.create_conversation(user_id, "workflow")
        
        task = pipeline.active_conversations[conversation_id]
        task.add_message(Message(role="user", content="用户消息"))
        task.add_message(Message(role="assistant", content="助手回复"))
        
        # 获取历史
        history = pipeline.get_conversation_history(conversation_id)
        
        assert len(history) == 2
        assert history[0].role == "user"
        assert history[0].content == "用户消息"
        assert history[1].role == "assistant"
        assert history[1].content == "助手回复"
    
    def test_get_conversation_summary(self, pipeline):
        """测试获取对话摘要"""
        user_id = "test_user"
        conversation_id = pipeline.create_conversation(user_id, "workflow")
        
        summary = pipeline.get_conversation_summary(conversation_id)
        
        assert summary["conversation_id"] == conversation_id
        assert summary["user_id"] == user_id
        assert summary["mode"] == "workflow"
        assert summary["status"] == "pending"
        assert "created_at" in summary
        assert "updated_at" in summary
    
    def test_list_active_conversations(self, pipeline):
        """测试列出活跃对话"""
        # 创建多个对话
        user1 = "user1"
        user2 = "user2"
        
        conv1 = pipeline.create_conversation(user1, "workflow")
        conv2 = pipeline.create_conversation(user2, "agent")
        conv3 = pipeline.create_conversation(user1, "workflow")
        
        # 列出所有对话
        all_conversations = pipeline.list_active_conversations()
        assert len(all_conversations) == 3
        
        # 按用户过滤
        user1_conversations = pipeline.list_active_conversations(user1)
        assert len(user1_conversations) == 2
        assert all(conv["user_id"] == user1 for conv in user1_conversations)
        
        user2_conversations = pipeline.list_active_conversations(user2)
        assert len(user2_conversations) == 1
        assert user2_conversations[0]["user_id"] == user2
    
    def test_close_conversation(self, pipeline):
        """测试关闭对话"""
        user_id = "test_user"
        conversation_id = pipeline.create_conversation(user_id, "workflow")
        
        # 验证对话存在
        assert conversation_id in pipeline.active_conversations
        
        # 关闭对话
        result = pipeline.close_conversation(conversation_id)
        
        assert result is True
        assert conversation_id not in pipeline.active_conversations
        
        # 再次关闭应该返回False
        result = pipeline.close_conversation(conversation_id)
        assert result is False
    
    def test_get_statistics(self, pipeline):
        """测试获取统计信息"""
        # 创建一些对话
        pipeline.create_conversation("user1", "workflow")
        pipeline.create_conversation("user2", "agent")
        pipeline.create_conversation("user3", "workflow")
        
        stats = pipeline.get_statistics()
        
        assert stats["total_conversations"] == 3
        assert stats["workflow_conversations"] == 2
        assert stats["agent_conversations"] == 1
        assert "status_distribution" in stats
        assert "timestamp" in stats
    
    def test_invalid_conversation_id(self, pipeline):
        """测试无效对话ID"""
        invalid_id = "nonexistent-conversation"
        
        with pytest.raises(ValueError) as exc_info:
            pipeline.get_conversation_history(invalid_id)
        
        assert "对话不存在" in str(exc_info.value)
        
        with pytest.raises(ValueError) as exc_info:
            pipeline.get_conversation_summary(invalid_id)
        
        assert "对话不存在" in str(exc_info.value)
    
    def test_invalid_execution_mode(self, pipeline):
        """测试无效执行模式"""
        with pytest.raises(ValueError) as exc_info:
            pipeline.create_conversation("test_user", "invalid_mode")
        
        assert "不支持的执行模式" in str(exc_info.value)


async def async_generator_mock(items):
    """异步生成器模拟"""
    for item in items:
        yield item
