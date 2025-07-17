"""
基于意图识别的问答Pipeline

这是一个支持workflow和agent两种模式的智能问答pipeline，
能够根据用户选择的模式调用相应的后端接口，支持流式输出和多轮对话。
"""

import json
import os
import asyncio
import requests
from typing import List, Dict, Any, Union, Generator, Iterator, Optional, Callable
from pydantic import BaseModel, Field

# 常量定义
DEFAULT_WORKFLOW_URL = "http://127.0.0.1:8000/api/v1/conversations/{}/stream"
DEFAULT_AGENT_URL = "http://127.0.0.1:8000/api/v1/conversations/{}/stream"
DEFAULT_CREATE_CONVERSATION_URL = "http://127.0.0.1:8000/api/v1/conversations"

# 执行模式常量
WORKFLOW_MODE = "workflow"
AGENT_MODE = "agent"

# 响应类型常量
STATUS_TYPE = "status"
CONTENT_TYPE = "content"
PROGRESS_TYPE = "progress"
ERROR_TYPE = "error"

# HTTP请求头
DEFAULT_HEADERS = {
    'accept': 'text/event-stream',
    'Content-Type': 'application/json',
}

# 状态消息
STATUS_MESSAGES = {
    "initializing": "正在初始化对话...",
    "creating_conversation": "正在创建对话会话...",
    "sending_message": "正在发送消息...",
    "processing": "正在处理您的问题...",
    "streaming": "正在获取流式响应...",
    "completed": "处理完成",
    "error": "处理过程中出现错误"
}


class Pipeline:
    """意图识别问答Pipeline"""

    class Valves(BaseModel):
        """Pipeline配置参数"""

        # 后端服务配置
        BACKEND_BASE_URL: str = Field(
            default="http://117.50.252.245:8888",
            description="后端服务基础URL"
        )

        # 默认执行模式
        DEFAULT_MODE: str = Field(
            default=WORKFLOW_MODE,
            description="默认执行模式 (workflow/agent)"
        )

        # 用户ID配置
        DEFAULT_USER_ID: str = Field(
            default="default_user",
            description="默认用户ID"
        )

        # 请求超时配置
        REQUEST_TIMEOUT: int = Field(
            default=300,
            description="请求超时时间（秒）"
        )

        # 流式响应配置
        STREAM_CHUNK_SIZE: int = Field(
            default=1024,
            description="流式响应块大小"
        )

        # 调试模式
        DEBUG_MODE: bool = Field(
            default=False,
            description="是否启用调试模式"
        )

    def __init__(self):
        """初始化Pipeline"""
        self.id = "intent_pipeline"
        self.name = "Intent Recognition Pipeline"
        self.description = "基于意图识别的智能问答Pipeline，支持workflow和agent两种模式"

        # 初始化配置参数
        self.valves = self.Valves(
            **{k: os.getenv(k, v.default) for k, v in self.Valves.model_fields.items()}
        )

        # 对话会话缓存
        self._conversation_cache: Dict[str, str] = {}

        # 构建API端点URL
        self._build_api_urls()

    def _build_api_urls(self) -> None:
        """构建API端点URL"""
        base_url = self.valves.BACKEND_BASE_URL.rstrip('/')
        self.create_conversation_url = f"{base_url}/api/v1/conversations"
        self.stream_chat_url = f"{base_url}/api/v1/conversations/{{}}/stream"

    async def on_startup(self):
        """Pipeline启动时调用"""
        print(f"on_startup: {__name__}")
        if self.valves.DEBUG_MODE:
            print(f"Pipeline配置: {self.valves.model_dump()}")

    async def on_shutdown(self):
        """Pipeline关闭时调用"""
        print(f"on_shutdown: {__name__}")
        # 清理对话缓存
        self._conversation_cache.clear()

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: List[dict],
        body: dict,
        __event_emitter__= None,
        __event_call__=None
    ) -> Union[str, Generator, Iterator]:
        """
        Pipeline主要处理方法

        Args:
            user_message: 用户消息
            model_id: 模型ID
            messages: 消息历史
            body: 请求体
            __event_emitter__: 事件发射器
            __event_call__: 事件调用器

        Returns:
            流式响应生成器
        """
        # 获取用户token
        user_token = body.get("user", {}).get("token")

        # 从body中获取执行模式和用户ID
        mode = body.get("mode", self.valves.DEFAULT_MODE)
        user_id = body.get("user_id", self.valves.DEFAULT_USER_ID)

        # 验证执行模式
        if mode not in [WORKFLOW_MODE, AGENT_MODE]:
            mode = self.valves.DEFAULT_MODE

        # 生成对话缓存键
        cache_key = f"{user_id}_{mode}_{model_id}"

        try:
            # 异步处理流式响应
            return self._process_stream_response(
                user_message=user_message,
                messages=messages,
                mode=mode,
                user_id=user_id,
                cache_key=cache_key,
                user_token=user_token,
                __event_emitter__= __event_emitter__
            )
        except Exception as e:
            error_msg = f"Pipeline处理失败: {str(e)}"
            if self.valves.DEBUG_MODE:
                print(f"Error in pipe: {error_msg}")
            return self._create_error_response(error_msg)

    def _process_stream_response(
        self,
        user_message: str,
        messages: List[dict],
        mode: str,
        user_id: str,
        cache_key: str,
        user_token: str = None,
        __event_emitter__= None
    ) -> Generator[str, None, None]:
        """
        处理流式响应

        Args:
            user_message: 用户消息
            messages: 消息历史
            mode: 执行模式
            user_id: 用户ID
            cache_key: 缓存键
            user_token: 用户认证token
            __event_emitter__: 事件发射器

        Yields:
            流式响应内容
        """
        conversation_id = None

        try:
            # 发送初始化状态
            yield from self._emit_status(
                __event_emitter__,
                STATUS_MESSAGES["initializing"]
            )

            # 获取或创建对话ID
            conversation_id = self._get_or_create_conversation(
                user_id, mode, cache_key, user_token, __event_emitter__
            )

            if not conversation_id:
                yield from self._create_error_response("无法创建对话会话")
                return

            # 发送消息并获取流式响应
            yield from self._send_message_and_stream(
                conversation_id=conversation_id,
                user_message=user_message,
                user_id=user_id,
                user_token=user_token,
                __event_emitter__=__event_emitter__
            )

        except Exception as e:
            error_msg = f"流式处理错误: {str(e)}"
            if self.valves.DEBUG_MODE:
                print(f"Stream processing error: {error_msg}")

            yield from self._emit_status(
                __event_emitter__,
                STATUS_MESSAGES["error"]
            )
            yield from self._create_error_response(error_msg)

    def _get_or_create_conversation(
        self,
        user_id: str,
        mode: str,
        cache_key: str,
        user_token: str = None,
        __event_emitter__=None
    ) -> Optional[str]:
        """
        获取或创建对话会话

        Args:
            user_id: 用户ID
            mode: 执行模式
            cache_key: 缓存键
            user_token: 用户认证token
            __event_emitter__: 事件发射器

        Returns:
            对话ID，失败时返回None
        """
        try:
            # 检查缓存中是否已有对话ID
            if cache_key in self._conversation_cache:
                conversation_id = self._conversation_cache[cache_key]
                if self.valves.DEBUG_MODE:
                    print(f"使用缓存的对话ID: {conversation_id}")
                return conversation_id

            # 发送创建对话状态
            list(self._emit_status(
                __event_emitter__,
                STATUS_MESSAGES["creating_conversation"]
            ))

            # 创建新对话
            conversation_id = self._create_new_conversation(user_id, mode, user_token)

            if conversation_id:
                # 缓存对话ID
                self._conversation_cache[cache_key] = conversation_id
                if self.valves.DEBUG_MODE:
                    print(f"创建新对话ID: {conversation_id}")

            return conversation_id

        except Exception as e:
            if self.valves.DEBUG_MODE:
                print(f"获取或创建对话失败: {str(e)}")
            return None

    def _create_new_conversation(self, user_id: str, mode: str, user_token: str = None) -> Optional[str]:
        """
        创建新对话会话

        Args:
            user_id: 用户ID
            mode: 执行模式
            user_token: 用户认证token

        Returns:
            对话ID，失败时返回None
        """
        try:
            # 构建请求数据
            request_data = {
                "user_id": user_id,
                "mode": mode
            }

            # 构建请求头
            headers = {'Content-Type': 'application/json'}
            if user_token:
                headers['Authorization'] = f'Bearer {user_token}'

            # 发送POST请求创建对话
            response = requests.post(
                self.create_conversation_url,
                json=request_data,
                headers=headers,
                timeout=self.valves.REQUEST_TIMEOUT
            )

            response.raise_for_status()

            # 解析响应
            result = response.json()
            if result.get("success") and result.get("data"):
                return result["data"].get("conversation_id")

            return None

        except Exception as e:
            if self.valves.DEBUG_MODE:
                print(f"创建对话请求失败: {str(e)}")
            return None

    def _send_message_and_stream(
        self,
        conversation_id: str,
        user_message: str,
        user_id: str,
        user_token: str = None,
        __event_emitter__=None
    ) -> Generator[str, None, None]:
        """
        发送消息并处理流式响应

        Args:
            conversation_id: 对话ID
            user_message: 用户消息
            user_id: 用户ID
            user_token: 用户认证token
            __event_emitter__: 事件发射器

        Yields:
            流式响应内容
        """
        try:
            # 发送消息状态
            yield from self._emit_status(
                __event_emitter__,
                STATUS_MESSAGES["sending_message"]
            )

            # 构建请求数据
            request_data = {
                "conversation_id": conversation_id,
                "message": user_message,
                "user_id": user_id
            }

            # 构建请求头
            headers = DEFAULT_HEADERS.copy()
            if user_token:
                headers['Authorization'] = f'Bearer {user_token}'

            # 构建流式聊天URL
            stream_url = self.stream_chat_url.format(conversation_id)

            # 发送流式请求
            response = requests.post(
                stream_url,
                json=request_data,
                headers=headers,
                stream=True,
                timeout=self.valves.REQUEST_TIMEOUT
            )

            response.raise_for_status()

            # 发送处理状态
            yield from self._emit_status(
                __event_emitter__,
                STATUS_MESSAGES["streaming"]
            )

            # 处理流式响应
            yield from self._process_stream_lines(
                response, __event_emitter__
            )

        except requests.exceptions.RequestException as e:
            error_msg = f"请求错误: {str(e)}"
            if self.valves.DEBUG_MODE:
                print(f"Request error: {error_msg}")
            yield from self._create_error_response(error_msg)

        except Exception as e:
            error_msg = f"发送消息失败: {str(e)}"
            if self.valves.DEBUG_MODE:
                print(f"Send message error: {error_msg}")
            yield from self._create_error_response(error_msg)

    def _process_stream_lines(
        self,
        response: requests.Response,
        __event_emitter__=None
    ) -> Generator[str, None, None]:
        """
        处理流式响应行

        Args:
            response: HTTP响应对象
            __event_emitter__: 事件发射器

        Yields:
            处理后的响应内容
        """
        try:
            for line in response.iter_lines(decode_unicode=True):
                if not line or not line.strip():
                    continue

                # 处理SSE格式的数据
                if line.startswith("data: "):
                    data_content = line[6:].strip()

                    # 检查结束标记
                    if data_content == "[DONE]":
                        yield from self._emit_status(
                            __event_emitter__,
                            STATUS_MESSAGES["completed"]
                        )
                        break

                    # 解析JSON数据
                    try:
                        data = json.loads(data_content)
                        yield from self._handle_stream_data(data, __event_emitter__)
                    except json.JSONDecodeError:
                        if self.valves.DEBUG_MODE:
                            print(f"JSON解析失败: {data_content}")
                        continue

        except Exception as e:
            error_msg = f"处理流式数据失败: {str(e)}"
            if self.valves.DEBUG_MODE:
                print(f"Stream processing error: {error_msg}")
            yield from self._create_error_response(error_msg)

    def _handle_stream_data(
        self,
        data: Dict[str, Any],
        __event_emitter__=None
    ) -> Generator[str, None, None]:
        """
        处理流式数据

        Args:
            data: 流式数据
            __event_emitter__: 事件发射器

        Yields:
            处理后的内容
        """
        try:
            data_type = data.get("type", "")

            if data_type == CONTENT_TYPE:
                # 内容响应 - 直接输出内容
                content = data.get("content", "")
                if content:
                    yield content

            elif data_type == STATUS_TYPE:
                # 状态响应 - 发送状态事件
                description = data.get("description", "")
                stage = data.get("stage", "")

                if description:
                    yield from self._emit_status(__event_emitter__, description)
                elif stage:
                    yield from self._emit_status(__event_emitter__, f"当前阶段: {stage}")

            elif data_type == PROGRESS_TYPE:
                # 进度响应 - 发送进度事件
                progress = data.get("progress", 0)
                stage = data.get("stage", "")

                progress_msg = f"进度: {int(progress * 100)}%"
                if stage:
                    progress_msg += f" - {stage}"

                yield from self._emit_status(__event_emitter__, progress_msg)

            elif data_type == ERROR_TYPE:
                # 错误响应 - 输出错误信息
                error_msg = data.get("error", "未知错误")
                yield from self._create_error_response(error_msg)

            else:
                # 其他类型 - 调试输出
                if self.valves.DEBUG_MODE:
                    print(f"未知数据类型: {data_type}, 数据: {data}")

        except Exception as e:
            if self.valves.DEBUG_MODE:
                print(f"处理流式数据项失败: {str(e)}")

    def _emit_status(
        self,
        __event_emitter__,
        description: str,
        done: bool = False
    ) -> Generator[str, None, None]:
        """
        发送状态事件

        Args:
            __event_emitter__: 事件发射器
            description: 状态描述
            done: 是否完成

        Yields:
            空生成器（用于兼容）
        """
        if __event_emitter__:
            try:
                # 使用asyncio运行异步事件发射器
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                loop.run_until_complete(__event_emitter__({
                    "type": "status",
                    "data": {
                        "description": description,
                        "done": done,
                    },
                }))

                loop.close()

            except Exception as e:
                if self.valves.DEBUG_MODE:
                    print(f"发送状态事件失败: {str(e)}")

        # 返回空生成器以保持一致性
        if False:  # 永远不会执行，但使函数成为生成器
            yield

    def _create_error_response(self, error_msg: str) -> Generator[str, None, None]:
        """
        创建错误响应

        Args:
            error_msg: 错误消息

        Yields:
            错误响应内容
        """
        yield f"\n❌ 错误: {error_msg}\n"


# 示例使用方法（可选）
if __name__ == "__main__":
    """
    Pipeline使用示例
    """

    # 创建Pipeline实例
    pipeline = Pipeline()

    # 示例消息
    test_messages = [
        {"role": "user", "content": "你好，请介绍一下人工智能的发展历史"}
    ]

    # 示例请求体
    test_body = {
        "mode": "workflow",  # 或 "agent"
        "user_id": "test_user"
    }

    print("Intent Pipeline 测试示例")
    print("=" * 50)
    print(f"消息: {test_messages[-1]['content']}")
    print(f"模式: {test_body['mode']}")
    print(f"用户ID: {test_body['user_id']}")
    print("=" * 50)

    try:
        # 调用pipeline
        response_generator = pipeline.pipe(
            user_message=test_messages[-1]['content'],
            model_id="intent-model",
            messages=test_messages,
            body=test_body
        )

        # 处理响应
        print("响应:")
        for response in response_generator:
            if isinstance(response, str):
                print(response, end="")

        print("\n" + "=" * 50)
        print("测试完成")

    except Exception as e:
        print(f"测试失败: {str(e)}")

    finally:
        # 清理
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(pipeline.on_shutdown())
        loop.close()