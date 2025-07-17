"""
Intent Pipeline 结构测试

测试 tests/intent_pipeline.py 中的 Pipeline 类的各个组件和方法
"""

import pytest
import json
import asyncio
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, Generator, List
import requests
from requests.exceptions import RequestException

# 导入被测试的模块
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipelines.intent_pipeline import Pipeline, WORKFLOW_MODE, AGENT_MODE, STATUS_TYPE, CONTENT_TYPE, PROGRESS_TYPE, ERROR_TYPE


class TestPipelineInitialization:
    """测试Pipeline初始化"""
    
    def test_pipeline_initialization(self):
        """测试Pipeline基本初始化"""
        pipeline = Pipeline()
        
        assert pipeline.id == "intent_pipeline"
        assert pipeline.name == "Intent Recognition Pipeline"
        assert "基于意图识别的智能问答Pipeline" in pipeline.description
        assert hasattr(pipeline, 'valves')
        assert isinstance(pipeline._conversation_cache, dict)
        assert len(pipeline._conversation_cache) == 0
    
    def test_valves_initialization(self):
        """测试Valves配置初始化"""
        pipeline = Pipeline()
        valves = pipeline.valves
        
        assert valves.BACKEND_BASE_URL == "http://117.50.252.245:8888"
        assert valves.DEFAULT_MODE == WORKFLOW_MODE
        assert valves.DEFAULT_USER_ID == "default_user"
        assert valves.REQUEST_TIMEOUT == 30  # 环境变量覆盖了默认值
        assert valves.STREAM_CHUNK_SIZE == 1024
        assert valves.DEBUG_MODE is False
    
    def test_api_urls_building(self):
        """测试API URL构建"""
        pipeline = Pipeline()
        
        expected_base = "http://117.50.252.245:8888"
        assert pipeline.create_conversation_url == f"{expected_base}/api/v1/conversations"
        assert pipeline.stream_chat_url == f"{expected_base}/api/v1/conversations/{{}}/stream"
    
    def test_environment_variable_override(self):
        """测试环境变量覆盖配置"""
        with patch.dict(os.environ, {'BACKEND_BASE_URL': 'http://custom.url:9999'}):
            pipeline = Pipeline()
            assert pipeline.valves.BACKEND_BASE_URL == 'http://custom.url:9999'


class TestPipelineLifecycle:
    """测试Pipeline生命周期方法"""
    
    @pytest.mark.asyncio
    async def test_on_startup(self):
        """测试启动方法"""
        pipeline = Pipeline()
        
        # 正常启动
        await pipeline.on_startup()
        
        # 调试模式启动
        pipeline.valves.DEBUG_MODE = True
        await pipeline.on_startup()
    
    @pytest.mark.asyncio
    async def test_on_shutdown(self):
        """测试关闭方法"""
        pipeline = Pipeline()
        pipeline._conversation_cache = {"test": "value"}
        
        await pipeline.on_shutdown()
        
        assert len(pipeline._conversation_cache) == 0


class TestPipeMainMethod:
    """测试Pipeline主要方法"""
    
    def setup_method(self):
        """设置测试方法"""
        self.pipeline = Pipeline()
        self.mock_event_emitter = Mock()
        self.mock_event_call = Mock()
        
        self.default_body = {
            "mode": WORKFLOW_MODE,
            "user_id": "test_user",
            "user": {"token": "test_token"}
        }
        
        self.default_messages = [
            {"role": "user", "content": "测试消息"}
        ]
    
    def test_pipe_basic_parameters(self):
        """测试pipe方法基本参数处理"""
        with patch.object(self.pipeline, '_process_stream_response') as mock_process:
            mock_process.return_value = iter(["test response"])
            
            result = self.pipeline.pipe(
                user_message="测试消息",
                model_id="test_model",
                messages=self.default_messages,
                body=self.default_body,
                __event_emitter__=self.mock_event_emitter
            )
            
            # 验证返回值是迭代器
            assert hasattr(result, '__iter__')
            
            # 验证调用了_process_stream_response
            mock_process.assert_called_once()
            args, kwargs = mock_process.call_args
            assert kwargs['user_message'] == "测试消息"
            assert kwargs['mode'] == WORKFLOW_MODE
            assert kwargs['user_id'] == "test_user"
    
    def test_pipe_mode_validation(self):
        """测试模式验证"""
        with patch.object(self.pipeline, '_process_stream_response') as mock_process:
            mock_process.return_value = iter(["test response"])
            
            # 测试无效模式，应该回退到默认模式
            body = self.default_body.copy()
            body["mode"] = "invalid_mode"
            
            self.pipeline.pipe(
                user_message="测试消息",
                model_id="test_model",
                messages=self.default_messages,
                body=body
            )
            
            args, kwargs = mock_process.call_args
            assert kwargs['mode'] == WORKFLOW_MODE  # 应该回退到默认模式
    
    def test_pipe_error_handling(self):
        """测试pipe方法错误处理"""
        with patch.object(self.pipeline, '_process_stream_response') as mock_process:
            mock_process.side_effect = Exception("测试错误")
            
            result = self.pipeline.pipe(
                user_message="测试消息",
                model_id="test_model",
                messages=self.default_messages,
                body=self.default_body
            )
            
            # 验证返回错误响应
            response_list = list(result)
            assert len(response_list) > 0
            assert "Pipeline处理失败" in response_list[0]


class TestConversationManagement:
    """测试对话管理"""
    
    def setup_method(self):
        """设置测试方法"""
        self.pipeline = Pipeline()
        self.mock_event_emitter = Mock()
    
    def test_get_cached_conversation(self):
        """测试获取缓存的对话"""
        # 设置缓存
        cache_key = "test_user_workflow_test_model"
        conversation_id = "test_conv_123"
        self.pipeline._conversation_cache[cache_key] = conversation_id
        
        result = self.pipeline._get_or_create_conversation(
            user_id="test_user",
            mode=WORKFLOW_MODE,
            cache_key=cache_key
        )
        
        assert result == conversation_id
    
    @patch('requests.post')
    def test_create_new_conversation_success(self, mock_post):
        """测试成功创建新对话"""
        # 模拟API响应
        mock_response = Mock()
        mock_response.json.return_value = {
            "success": True,
            "data": {"conversation_id": "new_conv_123"}
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        result = self.pipeline._create_new_conversation(
            user_id="test_user",
            mode=WORKFLOW_MODE
        )
        
        assert result == "new_conv_123"
        
        # 验证请求参数
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert kwargs['json'] == {"user_id": "test_user", "mode": WORKFLOW_MODE}
    
    @patch('requests.post')
    def test_create_new_conversation_failure(self, mock_post):
        """测试创建新对话失败"""
        # 模拟API失败响应
        mock_response = Mock()
        mock_response.json.return_value = {"success": False}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        result = self.pipeline._create_new_conversation(
            user_id="test_user",
            mode=WORKFLOW_MODE
        )
        
        assert result is None
    
    @patch('requests.post')
    def test_create_new_conversation_with_token(self, mock_post):
        """测试带token创建新对话"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "success": True,
            "data": {"conversation_id": "new_conv_123"}
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        self.pipeline._create_new_conversation(
            user_id="test_user",
            mode=WORKFLOW_MODE,
            user_token="test_token"
        )
        
        # 验证请求头包含认证信息
        args, kwargs = mock_post.call_args
        assert kwargs['headers']['Authorization'] == 'Bearer test_token'


class TestStreamProcessing:
    """测试流式处理"""
    
    def setup_method(self):
        """设置测试方法"""
        self.pipeline = Pipeline()
        self.mock_event_emitter = Mock()
    
    def test_handle_content_stream_data(self):
        """测试处理内容类型的流式数据"""
        data = {
            "type": CONTENT_TYPE,
            "content": "这是测试内容"
        }
        
        result = list(self.pipeline._handle_stream_data(data, self.mock_event_emitter))
        
        assert result == ["这是测试内容"]
    
    def test_handle_status_stream_data(self):
        """测试处理状态类型的流式数据"""
        data = {
            "type": STATUS_TYPE,
            "description": "正在处理中",
            "stage": "processing"
        }
        
        result = list(self.pipeline._handle_stream_data(data, self.mock_event_emitter))
        
        # 状态数据不应该产生内容输出
        assert len(result) == 0
    
    def test_handle_progress_stream_data(self):
        """测试处理进度类型的流式数据"""
        data = {
            "type": PROGRESS_TYPE,
            "progress": 0.5,
            "stage": "halfway"
        }
        
        result = list(self.pipeline._handle_stream_data(data, self.mock_event_emitter))
        
        # 进度数据不应该产生内容输出
        assert len(result) == 0
    
    def test_handle_error_stream_data(self):
        """测试处理错误类型的流式数据"""
        data = {
            "type": ERROR_TYPE,
            "error": "测试错误消息"
        }
        
        result = list(self.pipeline._handle_stream_data(data, self.mock_event_emitter))
        
        assert len(result) > 0
        assert "错误" in result[0]
        assert "测试错误消息" in result[0]
    
    def test_handle_unknown_stream_data(self):
        """测试处理未知类型的流式数据"""
        data = {
            "type": "unknown_type",
            "content": "fallback content"
        }
        
        result = list(self.pipeline._handle_stream_data(data, self.mock_event_emitter))
        
        # 应该尝试提取内容
        assert "fallback content" in result
    
    def test_process_stream_lines_with_sse(self):
        """测试处理SSE格式的流式数据"""
        mock_response = Mock()
        mock_response.iter_lines.return_value = [
            "data: " + json.dumps({"type": CONTENT_TYPE, "content": "测试内容1"}),
            "data: " + json.dumps({"type": CONTENT_TYPE, "content": "测试内容2"}),
            "data: [DONE]"
        ]
        
        result = list(self.pipeline._process_stream_lines(mock_response, self.mock_event_emitter))
        
        assert "测试内容1" in result
        assert "测试内容2" in result
    
    def test_process_stream_lines_with_invalid_json(self):
        """测试处理无效JSON的流式数据"""
        mock_response = Mock()
        mock_response.iter_lines.return_value = [
            "data: invalid json",
            "data: " + json.dumps({"type": CONTENT_TYPE, "content": "有效内容"})
        ]
        
        result = list(self.pipeline._process_stream_lines(mock_response, self.mock_event_emitter))
        
        # 应该跳过无效JSON，继续处理有效数据
        assert "有效内容" in result


class TestUtilityMethods:
    """测试工具方法"""
    
    def setup_method(self):
        """设置测试方法"""
        self.pipeline = Pipeline()
    
    def test_fix_encoding_normal_text(self):
        """测试正常文本编码修复"""
        normal_text = "这是正常的中文文本"
        result = self.pipeline._fix_encoding(normal_text)
        assert result == normal_text
    
    def test_fix_encoding_with_replacements(self):
        """测试带替换的文本编码修复"""
        problematic_text = "å½å©æ®µ"
        result = self.pipeline._fix_encoding(problematic_text)
        
        # 应该进行字符替换
        assert "å½" not in result
        assert "å" not in result
        assert "©" not in result
    
    def test_fix_encoding_non_string_input(self):
        """测试非字符串输入的编码修复"""
        result = self.pipeline._fix_encoding(123)
        assert result == "123"
    
    def test_create_error_response(self):
        """测试创建错误响应"""
        error_msg = "测试错误消息"
        result = list(self.pipeline._create_error_response(error_msg))
        
        assert len(result) == 1
        assert "❌ 错误" in result[0]
        assert error_msg in result[0]


class TestIntegrationScenarios:
    """测试集成场景"""
    
    def setup_method(self):
        """设置测试方法"""
        self.pipeline = Pipeline()
        self.mock_event_emitter = Mock()
    
    @patch('requests.post')
    def test_full_workflow_success(self, mock_post):
        """测试完整工作流成功场景"""
        # 模拟创建对话的响应
        create_response = Mock()
        create_response.json.return_value = {
            "success": True,
            "data": {"conversation_id": "test_conv_123"}
        }
        create_response.raise_for_status.return_value = None
        
        # 模拟流式响应
        stream_response = Mock()
        stream_response.iter_lines.return_value = [
            "data: " + json.dumps({"type": CONTENT_TYPE, "content": "测试"}),
            "data: " + json.dumps({"type": CONTENT_TYPE, "content": "响应"}),
            "data: [DONE]"
        ]
        stream_response.raise_for_status.return_value = None
        
        mock_post.side_effect = [create_response, stream_response]
        
        # 执行完整流程
        result = list(self.pipeline._process_stream_response(
            user_message="测试消息",
            messages=[{"role": "user", "content": "测试消息"}],
            mode=WORKFLOW_MODE,
            user_id="test_user",
            cache_key="test_key",
            __event_emitter__=self.mock_event_emitter
        ))
        
        # 验证结果包含响应内容
        content = "".join(result)
        assert "测试" in content
        assert "响应" in content
    
    @patch('requests.post')
    def test_full_workflow_with_cached_conversation(self, mock_post):
        """测试使用缓存对话的完整工作流"""
        # 设置缓存的对话ID
        cache_key = "test_key"
        self.pipeline._conversation_cache[cache_key] = "cached_conv_123"
        
        # 模拟流式响应
        stream_response = Mock()
        stream_response.iter_lines.return_value = [
            "data: " + json.dumps({"type": CONTENT_TYPE, "content": "缓存测试"}),
            "data: [DONE]"
        ]
        stream_response.raise_for_status.return_value = None
        
        mock_post.return_value = stream_response
        
        # 执行流程
        result = list(self.pipeline._process_stream_response(
            user_message="测试消息",
            messages=[{"role": "user", "content": "测试消息"}],
            mode=WORKFLOW_MODE,
            user_id="test_user",
            cache_key=cache_key,
            __event_emitter__=self.mock_event_emitter
        ))
        
        # 验证只调用了一次POST（流式请求），没有调用创建对话
        assert mock_post.call_count == 1
        
        # 验证结果
        content = "".join(result)
        assert "缓存测试" in content


class TestErrorHandling:
    """测试错误处理"""
    
    def setup_method(self):
        """设置测试方法"""
        self.pipeline = Pipeline()
        self.mock_event_emitter = Mock()
    
    @patch('requests.post')
    def test_request_timeout_error(self, mock_post):
        """测试请求超时错误"""
        mock_post.side_effect = requests.exceptions.Timeout("请求超时")
        
        result = list(self.pipeline._send_message_and_stream(
            conversation_id="test_conv",
            user_message="测试消息",
            user_id="test_user",
            __event_emitter__=self.mock_event_emitter
        ))
        
        # 验证错误响应
        error_content = "".join(result)
        assert "请求错误" in error_content
        assert "请求超时" in error_content
    
    @patch('requests.post')
    def test_http_error(self, mock_post):
        """测试HTTP错误"""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("HTTP 500")
        mock_post.return_value = mock_response
        
        result = list(self.pipeline._send_message_and_stream(
            conversation_id="test_conv",
            user_message="测试消息",
            user_id="test_user",
            __event_emitter__=self.mock_event_emitter
        ))
        
        # 验证错误响应
        error_content = "".join(result)
        assert "请求错误" in error_content
    
    def test_json_decode_error_handling(self):
        """测试JSON解码错误处理"""
        mock_response = Mock()
        mock_response.iter_lines.return_value = [
            "data: {invalid json}",
            "data: " + json.dumps({"type": CONTENT_TYPE, "content": "正常内容"})
        ]
        
        result = list(self.pipeline._process_stream_lines(mock_response, self.mock_event_emitter))
        
        # 应该跳过无效JSON，继续处理有效内容
        assert "正常内容" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 