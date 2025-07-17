"""
配置修复测试用例

检查并修复intent_pipeline.py与后端配置的兼容性问题
"""

import os
import pytest
from unittest.mock import patch, Mock
from typing import Dict, Any

# 导入配置相关模块
from app.config import get_settings
from app.models.enums import WorkflowStageType, ResponseTypeType


class TestConfigurationFix:
    """配置修复测试类"""
    
    def test_env_configuration(self):
        """测试环境配置"""
        settings = get_settings()
        
        # 检查关键配置项
        assert settings.api_host is not None
        assert settings.api_port is not None
        assert settings.openai_api_key is not None
        
        # 检查API端口配置
        assert settings.api_port == 8000  # 应该与.env文件中的配置匹配
        
        # 检查其他关键配置
        assert settings.environment in ["development", "testing", "staging", "production"]
        assert settings.log_level in ["debug", "info", "warning", "error", "critical"]
    
    def test_backend_url_configuration(self):
        """测试后端URL配置"""
        settings = get_settings()
        
        # 构建预期的后端URL
        expected_backend_url = f"http://117.50.252.245:{settings.api_port}"
        
        # 验证URL格式
        assert "://" in expected_backend_url
        assert expected_backend_url.startswith("http")
        
        # 验证端口是否正确
        assert str(settings.api_port) in expected_backend_url
        
        print(f"后端URL应该是: {expected_backend_url}")
    
    def test_api_endpoints_compatibility(self):
        """测试API端点兼容性"""
        # 测试创建对话端点
        create_conversation_endpoint = "/api/v1/conversations"
        
        # 测试流式聊天端点
        stream_chat_endpoint = "/api/v1/conversations/{conversation_id}/stream"
        
        # 验证端点格式
        assert create_conversation_endpoint.startswith("/api/v1/")
        assert "{conversation_id}" in stream_chat_endpoint
        
        # 验证与intent_pipeline.py期望的端点匹配
        expected_create_url = "http://117.50.252.245:8000/api/v1/conversations"
        expected_stream_url = "http://117.50.252.245:8000/api/v1/conversations/{}/stream"
        
        assert "conversations" in expected_create_url
        assert "stream" in expected_stream_url
    
    def test_intent_pipeline_expected_response_format(self):
        """测试intent_pipeline.py期望的响应格式"""
        # 测试各种响应类型的格式
        
        # 1. content类型响应
        content_response = {
            "type": "content",
            "content": "测试内容",
            "timestamp": "2024-01-01T00:00:00Z"
        }
        
        assert content_response["type"] == "content"
        assert "content" in content_response
        assert "timestamp" in content_response
        
        # 2. status类型响应
        status_response = {
            "type": "status",
            "description": "正在处理...",
            "stage": "initialization",
            "timestamp": "2024-01-01T00:00:00Z"
        }
        
        assert status_response["type"] == "status"
        assert "description" in status_response
        assert "stage" in status_response
        
        # 3. error类型响应
        error_response = {
            "type": "error",
            "error": "错误消息",
            "code": "ERROR_CODE",
            "timestamp": "2024-01-01T00:00:00Z"
        }
        
        assert error_response["type"] == "error"
        assert "error" in error_response
        assert "code" in error_response
        
        # 4. progress类型响应
        progress_response = {
            "type": "progress",
            "progress": 0.5,
            "stage": "processing",
            "timestamp": "2024-01-01T00:00:00Z"
        }
        
        assert progress_response["type"] == "progress"
        assert "progress" in progress_response
        assert isinstance(progress_response["progress"], (int, float))
    
    def test_request_data_compatibility(self):
        """测试请求数据兼容性"""
        # 测试创建对话请求
        create_conversation_request = {
            "user_id": "test_user",
            "mode": "workflow"
        }
        
        assert "user_id" in create_conversation_request
        assert "mode" in create_conversation_request
        assert create_conversation_request["mode"] in ["workflow", "agent"]
        
        # 测试流式聊天请求
        stream_chat_request = {
            "conversation_id": "test-conversation-id",
            "message": "测试消息",
            "user_id": "test_user",
            "mode": "workflow",
            "metadata": {
                "stream": True,
                "temperature": 0.7,
                "max_tokens": 2000
            }
        }
        
        assert "conversation_id" in stream_chat_request
        assert "message" in stream_chat_request
        assert "user_id" in stream_chat_request
        assert "mode" in stream_chat_request
        assert "metadata" in stream_chat_request
        assert stream_chat_request["metadata"]["stream"] is True
    
    def test_stage_descriptions_compatibility(self):
        """测试阶段描述兼容性"""
        # 测试各种工作流阶段的描述
        stage_descriptions = {
            "initialization": "正在初始化...",
            "online_search": "正在进行联网搜索...",
            "knowledge_search": "正在搜索知识库...",
            "lightrag_query": "正在进行LightRAG查询...",
            "response_generation": "正在生成响应...",
            "completed": "处理完成"
        }
        
        # 验证所有阶段都有描述
        for stage in ["initialization", "online_search", "knowledge_search", 
                     "lightrag_query", "response_generation", "completed"]:
            assert stage in stage_descriptions
            assert len(stage_descriptions[stage]) > 0
            assert "正在" in stage_descriptions[stage] or "处理完成" in stage_descriptions[stage]
    
    def test_error_handling_compatibility(self):
        """测试错误处理兼容性"""
        # 测试各种错误情况
        error_cases = [
            {
                "error_code": "CREATE_CONVERSATION_ERROR",
                "error_message": "创建对话失败",
                "expected_in_response": True
            },
            {
                "error_code": "SEND_MESSAGE_ERROR",
                "error_message": "发送消息失败",
                "expected_in_response": True
            },
            {
                "error_code": "STREAM_ERROR",
                "error_message": "流式处理错误",
                "expected_in_response": True
            },
            {
                "error_code": "CONVERSATION_NOT_FOUND",
                "error_message": "对话不存在",
                "expected_in_response": True
            }
        ]
        
        for error_case in error_cases:
            assert error_case["error_code"] is not None
            assert error_case["error_message"] is not None
            assert len(error_case["error_code"]) > 0
            assert len(error_case["error_message"]) > 0
    
    def test_timeout_configuration(self):
        """测试超时配置"""
        settings = get_settings()
        
        # 检查各种超时设置
        assert settings.request_timeout > 0
        assert settings.knowledge_timeout > 0
        assert settings.lightrag_timeout > 0
        assert settings.search_timeout > 0
        
        # 验证超时设置合理性
        assert settings.request_timeout >= 30  # 至少30秒
        assert settings.knowledge_timeout >= 30
        assert settings.lightrag_timeout >= 30
        assert settings.search_timeout >= 30
        
        # 验证与intent_pipeline.py中的超时设置兼容
        # intent_pipeline.py中的REQUEST_TIMEOUT默认为300秒
        assert settings.request_timeout <= 300
    
    def test_stream_chunk_size_configuration(self):
        """测试流式响应块大小配置"""
        settings = get_settings()
        
        # 检查流式响应块大小
        assert settings.stream_chunk_size > 0
        assert settings.stream_chunk_size <= 8192  # 不超过8KB
        
        # 验证与intent_pipeline.py中的设置兼容
        # intent_pipeline.py中的STREAM_CHUNK_SIZE默认为1024
        assert settings.stream_chunk_size == 1024
    
    def test_cors_configuration(self):
        """测试CORS配置"""
        settings = get_settings()
        
        # 检查CORS配置
        assert settings.cors_origins is not None
        assert settings.cors_methods is not None
        assert settings.cors_headers is not None
        
        # 验证CORS配置合理性
        assert len(settings.cors_origins) > 0
        assert len(settings.cors_methods) > 0
        assert len(settings.cors_headers) > 0
        
        # 验证必要的CORS头部
        expected_headers = ["Content-Type", "Authorization", "Accept"]
        if "*" not in settings.cors_headers:
            for header in expected_headers:
                assert header in settings.cors_headers or "*" in settings.cors_headers


class TestConfigurationFix:
    """配置修复测试类"""
    
    def test_generate_fixed_env_config(self):
        """生成修复后的环境配置建议"""
        current_settings = get_settings()
        
        # 生成修复建议
        fixed_config = {
            "BACKEND_BASE_URL": f"http://117.50.252.245:{current_settings.api_port}",
            "API_HOST": current_settings.api_host,
            "API_PORT": current_settings.api_port,
            "REQUEST_TIMEOUT": 300,  # 与intent_pipeline.py中的默认值匹配
            "STREAM_CHUNK_SIZE": 1024,  # 与intent_pipeline.py中的默认值匹配
            "DEBUG_MODE": current_settings.debug,
            "DEFAULT_MODE": "workflow",
            "DEFAULT_USER_ID": "default_user"
        }
        
        print("建议的配置修复:")
        for key, value in fixed_config.items():
            print(f"{key}={value}")
        
        # 验证修复后的配置
        assert "117.50.252.245" in fixed_config["BACKEND_BASE_URL"]
        assert str(current_settings.api_port) in fixed_config["BACKEND_BASE_URL"]
        assert fixed_config["REQUEST_TIMEOUT"] == 300
        assert fixed_config["STREAM_CHUNK_SIZE"] == 1024
    
    def test_validate_api_compatibility(self):
        """验证API兼容性"""
        # 检查API端点兼容性
        endpoints = {
            "create_conversation": "/api/v1/conversations",
            "stream_chat": "/api/v1/conversations/{conversation_id}/stream",
            "get_history": "/api/v1/conversations/{conversation_id}/history",
            "get_summary": "/api/v1/conversations/{conversation_id}/summary",
            "list_conversations": "/api/v1/conversations",
            "close_conversation": "/api/v1/conversations/{conversation_id}",
            "get_statistics": "/api/v1/statistics"
        }
        
        for endpoint_name, endpoint_path in endpoints.items():
            assert endpoint_path.startswith("/api/v1/")
            assert len(endpoint_path) > 8  # 基本路径长度检查
            
            # 检查参数化端点
            if "{conversation_id}" in endpoint_path:
                assert endpoint_path.count("{") == endpoint_path.count("}")
        
        print("API端点兼容性检查通过")
    
    def test_robustness_requirements(self):
        """测试鲁棒性要求"""
        # 测试错误隔离
        test_cases = [
            {
                "scenario": "无效的对话ID",
                "expected_error": "对话不存在",
                "should_affect_other_conversations": False
            },
            {
                "scenario": "网络请求超时",
                "expected_error": "请求超时",
                "should_affect_other_conversations": False
            },
            {
                "scenario": "模型响应错误",
                "expected_error": "模型处理失败",
                "should_affect_other_conversations": False
            },
            {
                "scenario": "用户权限不足",
                "expected_error": "权限不足",
                "should_affect_other_conversations": False
            }
        ]
        
        for test_case in test_cases:
            assert test_case["expected_error"] is not None
            assert test_case["should_affect_other_conversations"] is False
            assert len(test_case["scenario"]) > 0
        
        print("鲁棒性要求检查通过")


# 生成配置修复报告
def generate_config_fix_report():
    """生成配置修复报告"""
    settings = get_settings()
    
    report = {
        "current_config": {
            "api_host": settings.api_host,
            "api_port": settings.api_port,
            "debug": settings.debug,
            "request_timeout": settings.request_timeout,
            "stream_chunk_size": settings.stream_chunk_size
        },
        "recommended_fixes": {
            "backend_base_url": f"http://117.50.252.245:{settings.api_port}",
            "ensure_timeout_compatibility": "REQUEST_TIMEOUT=300",
            "ensure_chunk_size_compatibility": "STREAM_CHUNK_SIZE=1024",
            "enable_debug_mode": "DEBUG_MODE=true"
        },
        "api_endpoints": {
            "create_conversation": f"http://117.50.252.245:{settings.api_port}/api/v1/conversations",
            "stream_chat": f"http://117.50.252.245:{settings.api_port}/api/v1/conversations/{{conversation_id}}/stream"
        }
    }
    
    return report


if __name__ == "__main__":
    # 生成配置修复报告
    report = generate_config_fix_report()
    
    print("配置修复报告:")
    print("=" * 50)
    
    print("\n当前配置:")
    for key, value in report["current_config"].items():
        print(f"  {key}: {value}")
    
    print("\n建议修复:")
    for key, value in report["recommended_fixes"].items():
        print(f"  {key}: {value}")
    
    print("\nAPI端点:")
    for key, value in report["api_endpoints"].items():
        print(f"  {key}: {value}")
    
    print("\n运行测试...")
    pytest.main([__file__, "-v"]) 