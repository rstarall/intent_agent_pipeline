"""
完整集成测试

测试所有修复的功能，包括配置、API接口、错误处理等
"""

import pytest
import asyncio
import json
from unittest.mock import patch, Mock, AsyncMock
from fastapi.testclient import TestClient
from typing import Dict, Any, List
import threading
import time

# 导入应用和相关模块
from app.main import create_app
from app.core import (
    PipelineInterface, 
    ErrorHandler, 
    task_manager,
    circuit_breaker,
    rate_limiter,
    get_error_handling_statistics
)
from app.models import ChatRequest, CreateConversationRequest, StreamResponse
from app.config.pipeline_config import (
    get_pipeline_config,
    validate_pipeline_compatibility,
    print_configuration_report
)


class TestCompleteIntegration:
    """完整集成测试类"""
    
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
    
    def test_configuration_compatibility(self):
        """测试配置兼容性"""
        # 获取Pipeline配置
        pipeline_config = get_pipeline_config()
        
        # 验证配置
        assert pipeline_config.backend_base_url.startswith("http://")
        assert "117.50.252.245" in pipeline_config.backend_base_url
        assert pipeline_config.request_timeout == 300
        assert pipeline_config.stream_chunk_size == 1024
        assert pipeline_config.default_mode == "workflow"
        
        # 验证兼容性
        compatibility = validate_pipeline_compatibility()
        assert compatibility["config_validation"]["all_valid"]
        assert compatibility["timeout_consistency"]["matches"]
        assert compatibility["chunk_size_consistency"]["matches"]
        
        print("配置兼容性测试通过")
    
    def test_api_endpoints_integration(self, client):
        """测试API端点集成"""
        # 创建对话测试
        create_data = {
            "user_id": "test_user",
            "mode": "workflow"
        }
        
        response = client.post("/api/v1/conversations", json=create_data)
        assert response.status_code == 200
        
        result = response.json()
        assert result["success"] is True
        assert "conversation_id" in result["data"]
        
        conversation_id = result["data"]["conversation_id"]
        
        # 测试流式聊天
        stream_data = {
            "conversation_id": conversation_id,
            "message": "测试消息",
            "user_id": "test_user",
            "mode": "workflow"
        }
        
        # 这里需要Mock实际的Pipeline执行
        with patch('app.core.pipeline.PipelineInterface') as mock_pipeline_class:
            mock_pipeline = Mock()
            mock_pipeline_class.return_value = mock_pipeline
            
            # Mock流式响应
            async def mock_stream_response(*args, **kwargs):
                yield StreamResponse(
                    conversation_id=conversation_id,
                    response_type="status",
                    stage="initialization"
                )
                yield StreamResponse(
                    conversation_id=conversation_id,
                    response_type="content",
                    content="测试回复"
                )
            
            mock_pipeline.send_message = mock_stream_response
            
            stream_response = client.post(
                f"/api/v1/conversations/{conversation_id}/stream",
                json=stream_data
            )
            
            assert stream_response.status_code == 200
            assert "text/plain" in stream_response.headers["content-type"]
        
        print("API端点集成测试通过")
    
    def test_error_handling_robustness(self):
        """测试错误处理鲁棒性"""
        # 创建错误处理器
        error_handler = ErrorHandler("test-conversation-id")
        
        # 测试不同类型的错误
        test_errors = [
            ValueError("测试值错误"),
            TimeoutError("测试超时错误"),
            ConnectionError("测试连接错误"),
            RuntimeError("测试运行时错误")
        ]
        
        for error in test_errors:
            error_response = error_handler.handle_error(error)
            
            assert error_response.response_type == "error"
            assert error_response.error_message == str(error)
            assert error_response.error_code is not None
            assert error_response.conversation_id == "test-conversation-id"
        
        print("错误处理鲁棒性测试通过")
    
    def test_concurrent_task_isolation(self):
        """测试并发任务隔离"""
        # 创建多个任务上下文
        task_contexts = []
        
        for i in range(5):
            conversation_id = f"test-conversation-{i}"
            user_id = f"user-{i}"
            
            context = task_manager.create_task_context(conversation_id, user_id)
            task_contexts.append(context)
        
        # 验证任务隔离
        assert len(task_manager.active_tasks) == 5
        
        # 模拟并发任务执行
        def simulate_task_execution(conversation_id: str, duration: float):
            """模拟任务执行"""
            task_lock = task_manager.get_task_lock(conversation_id)
            
            with task_lock:
                task_manager.update_task_status(conversation_id, "running")
                time.sleep(duration)
                task_manager.update_task_status(conversation_id, "completed")
        
        # 创建并发线程
        threads = []
        for i in range(5):
            conversation_id = f"test-conversation-{i}"
            thread = threading.Thread(
                target=simulate_task_execution,
                args=(conversation_id, 0.1)
            )
            threads.append(thread)
            thread.start()
        
        # 等待所有任务完成
        for thread in threads:
            thread.join()
        
        # 验证任务都完成了
        stats = task_manager.get_task_statistics()
        assert stats["completed_tasks"] == 5
        assert stats["running_tasks"] == 0
        
        # 清理任务
        for i in range(5):
            conversation_id = f"test-conversation-{i}"
            task_manager.cleanup_task(conversation_id)
        
        print("并发任务隔离测试通过")
    
    def test_stream_response_format_compatibility(self):
        """测试流式响应格式兼容性"""
        # 测试各种响应类型
        test_responses = [
            {
                "type": StreamResponse(
                    conversation_id="test-id",
                    response_type="content",
                    content="测试内容"
                ),
                "expected_keys": ["type", "content", "timestamp"]
            },
            {
                "type": StreamResponse(
                    conversation_id="test-id",
                    response_type="status",
                    stage="initialization"
                ),
                "expected_keys": ["type", "description", "stage", "timestamp"]
            },
            {
                "type": StreamResponse(
                    conversation_id="test-id",
                    response_type="error",
                    error_code="TEST_ERROR",
                    error_message="测试错误"
                ),
                "expected_keys": ["type", "error", "code", "timestamp"]
            },
            {
                "type": StreamResponse(
                    conversation_id="test-id",
                    response_type="progress",
                    progress=0.5,
                    stage="processing"
                ),
                "expected_keys": ["type", "progress", "stage", "timestamp"]
            }
        ]
        
        for test_case in test_responses:
            response = test_case["type"]
            response_dict = response.to_dict()
            
            # 验证必需的键存在
            for key in test_case["expected_keys"]:
                assert key in response_dict, f"缺少键: {key}"
            
            # 验证响应类型
            assert response_dict["type"] == response.response_type
            
            # 验证时间戳格式
            assert "timestamp" in response_dict
            assert isinstance(response_dict["timestamp"], str)
        
        print("流式响应格式兼容性测试通过")
    
    def test_circuit_breaker_functionality(self):
        """测试熔断器功能"""
        # 重置熔断器
        circuit_breaker.failure_count = 0
        circuit_breaker.state = "closed"
        
        # 测试正常调用
        def normal_function():
            return "success"
        
        result = circuit_breaker.call(normal_function)
        assert result == "success"
        assert circuit_breaker.state == "closed"
        
        # 测试失败调用
        def failing_function():
            raise Exception("测试失败")
        
        # 触发多次失败以打开熔断器
        for i in range(6):  # 超过failure_threshold(5)
            try:
                circuit_breaker.call(failing_function)
            except Exception:
                pass
        
        # 验证熔断器已打开
        assert circuit_breaker.state == "open"
        
        # 测试熔断器打开时的行为
        with pytest.raises(Exception, match="Circuit breaker is open"):
            circuit_breaker.call(normal_function)
        
        print("熔断器功能测试通过")
    
    def test_rate_limiter_functionality(self):
        """测试速率限制器功能"""
        # 重置速率限制器
        rate_limiter.requests.clear()
        
        # 测试正常请求
        user_id = "test_user"
        
        # 发送允许的请求
        for i in range(10):
            assert rate_limiter.is_allowed(user_id) is True
        
        # 验证剩余请求数
        remaining = rate_limiter.get_remaining_requests(user_id)
        assert remaining == 90  # 100 - 10 = 90
        
        # 测试超过限制的请求
        for i in range(91):  # 超过剩余数量
            rate_limiter.is_allowed(user_id)
        
        # 现在应该被限制
        assert rate_limiter.is_allowed(user_id) is False
        
        print("速率限制器功能测试通过")
    
    def test_error_handling_statistics(self):
        """测试错误处理统计"""
        # 创建一些任务
        for i in range(3):
            conversation_id = f"stats-test-{i}"
            task_manager.create_task_context(conversation_id, f"user-{i}")
        
        # 更新任务状态
        task_manager.update_task_status("stats-test-0", "running")
        task_manager.update_task_status("stats-test-1", "completed")
        task_manager.update_task_status("stats-test-2", "error", "测试错误")
        
        # 获取统计信息
        stats = get_error_handling_statistics()
        
        # 验证统计信息
        assert "task_statistics" in stats
        assert "circuit_breaker" in stats
        assert "rate_limiting" in stats
        assert "timestamp" in stats
        
        task_stats = stats["task_statistics"]
        assert task_stats["total_tasks"] == 3
        assert task_stats["running_tasks"] == 1
        assert task_stats["completed_tasks"] == 1
        assert task_stats["error_tasks"] == 1
        
        # 清理
        for i in range(3):
            conversation_id = f"stats-test-{i}"
            task_manager.cleanup_task(conversation_id)
        
        print("错误处理统计测试通过")
    
    def test_complete_pipeline_workflow(self, client):
        """测试完整的Pipeline工作流"""
        # 这是一个端到端的测试，模拟完整的用户交互流程
        
        # 1. 创建对话
        create_data = {
            "user_id": "integration_test_user",
            "mode": "workflow"
        }
        
        response = client.post("/api/v1/conversations", json=create_data)
        assert response.status_code == 200
        
        result = response.json()
        conversation_id = result["data"]["conversation_id"]
        
        # 2. 发送消息 - 需要Mock实际的Pipeline实现
        with patch('app.core.pipeline.PipelineInterface') as mock_pipeline_class:
            mock_pipeline = Mock()
            mock_pipeline_class.return_value = mock_pipeline
            
            # Mock流式响应
            async def mock_complete_stream(*args, **kwargs):
                # 状态响应
                yield StreamResponse(
                    conversation_id=conversation_id,
                    response_type="status",
                    stage="initialization"
                )
                
                # 进度响应
                yield StreamResponse(
                    conversation_id=conversation_id,
                    response_type="progress",
                    progress=0.5,
                    stage="processing"
                )
                
                # 内容响应
                yield StreamResponse(
                    conversation_id=conversation_id,
                    response_type="content",
                    content="这是完整的测试回复"
                )
                
                # 完成状态
                yield StreamResponse(
                    conversation_id=conversation_id,
                    response_type="status",
                    stage="completed"
                )
            
            mock_pipeline.send_message = mock_complete_stream
            
            # 发送流式消息
            stream_data = {
                "conversation_id": conversation_id,
                "message": "完整测试消息",
                "user_id": "integration_test_user",
                "mode": "workflow"
            }
            
            stream_response = client.post(
                f"/api/v1/conversations/{conversation_id}/stream",
                json=stream_data
            )
            
            assert stream_response.status_code == 200
            
            # 验证流式响应内容
            content = stream_response.content.decode('utf-8')
            assert "data: " in content
            assert "[DONE]" in content
            
            # 解析流式响应
            lines = content.strip().split('\n')
            data_lines = [line for line in lines if line.startswith("data: ") and line != "data: [DONE]"]
            
            # 验证响应数量
            assert len(data_lines) >= 4  # 至少有4个响应
            
            # 验证响应格式
            for line in data_lines:
                data_str = line[6:]  # 去掉 "data: " 前缀
                try:
                    data = json.loads(data_str)
                    assert "type" in data
                    assert "timestamp" in data
                    assert data["type"] in ["status", "progress", "content", "error"]
                except json.JSONDecodeError:
                    pytest.fail(f"Invalid JSON in response: {data_str}")
        
        print("完整Pipeline工作流测试通过")


class TestConfigurationReport:
    """配置报告测试类"""
    
    def test_configuration_report_generation(self):
        """测试配置报告生成"""
        # 生成配置报告
        validation = print_configuration_report()
        
        # 验证报告包含必要信息
        assert "config_validation" in validation
        assert "url_consistency" in validation
        assert "timeout_consistency" in validation
        assert "chunk_size_consistency" in validation
        
        # 验证配置有效性
        config_validation = validation["config_validation"]
        assert config_validation["backend_url_valid"] is True
        assert config_validation["timeout_reasonable"] is True
        assert config_validation["chunk_size_valid"] is True
        assert config_validation["mode_valid"] is True
        assert config_validation["endpoints_valid"] is True
        
        print("配置报告生成测试通过")
    
    def test_environment_fix_suggestions(self):
        """测试环境修复建议"""
        from app.config.pipeline_config import generate_env_fix_suggestions
        
        suggestions = generate_env_fix_suggestions()
        
        # 验证建议包含必要的配置
        suggestion_text = " ".join(suggestions.values())
        assert "BACKEND_BASE_URL" in suggestion_text
        assert "REQUEST_TIMEOUT=300" in suggestion_text
        assert "STREAM_CHUNK_SIZE=1024" in suggestion_text
        assert "DEBUG_MODE=true" in suggestion_text
        
        print("环境修复建议测试通过")


def run_all_tests():
    """运行所有测试"""
    print("开始运行完整集成测试...")
    print("=" * 60)
    
    # 运行配置测试
    print("\n1. 运行配置兼容性测试...")
    test_config = TestCompleteIntegration()
    test_config.test_configuration_compatibility()
    
    # 运行错误处理测试
    print("\n2. 运行错误处理测试...")
    test_config.test_error_handling_robustness()
    
    # 运行并发测试
    print("\n3. 运行并发任务隔离测试...")
    test_config.test_concurrent_task_isolation()
    
    # 运行响应格式测试
    print("\n4. 运行响应格式兼容性测试...")
    test_config.test_stream_response_format_compatibility()
    
    # 运行熔断器测试
    print("\n5. 运行熔断器功能测试...")
    test_config.test_circuit_breaker_functionality()
    
    # 运行速率限制器测试
    print("\n6. 运行速率限制器功能测试...")
    test_config.test_rate_limiter_functionality()
    
    # 运行统计测试
    print("\n7. 运行错误处理统计测试...")
    test_config.test_error_handling_statistics()
    
    # 运行配置报告测试
    print("\n8. 运行配置报告测试...")
    test_report = TestConfigurationReport()
    test_report.test_configuration_report_generation()
    test_report.test_environment_fix_suggestions()
    
    print("\n" + "=" * 60)
    print("所有测试完成！")
    print("✓ 配置兼容性测试通过")
    print("✓ 错误处理鲁棒性测试通过")
    print("✓ 并发任务隔离测试通过")
    print("✓ 响应格式兼容性测试通过")
    print("✓ 熔断器功能测试通过")
    print("✓ 速率限制器功能测试通过")
    print("✓ 错误处理统计测试通过")
    print("✓ 配置报告测试通过")


if __name__ == "__main__":
    run_all_tests() 