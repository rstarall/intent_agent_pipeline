"""
基础对话任务类模块

定义对话任务的基础接口和流式响应机制。
"""

import uuid
import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, AsyncIterator, Any, Union

from ..models import (
    Message, ConversationHistory, StreamResponse, 
    TaskStatus, ExecutionMode
)
from ..models.enums import WorkflowStage
from ..config import get_logger


class BaseConversationTask(ABC):
    """对话任务基类"""
    
    def __init__(
        self,
        user_id: str,
        conversation_id: Optional[str] = None,
        mode: str = "workflow"
    ):
        """
        初始化对话任务
        
        Args:
            user_id: 用户ID
            conversation_id: 对话唯一标识，如果为None则自动生成
            mode: 执行模式
        """
        self.user_id = user_id
        self.conversation_id = conversation_id or str(uuid.uuid4())
        self.mode = mode
        self.history = ConversationHistory(
            conversation_id=self.conversation_id,
            user_id=user_id
        )
        self.current_stage = ""
        self.status: str = "pending"
        self.progress: float = 0.0
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.metadata: Dict[str, Any] = {}
        
        # 知识库配置（默认为空，等待外部传入）
        self.knowledge_bases: List[Dict[str, str]] = []
        
        # 知识库API URL
        self.knowledge_api_url: Optional[str] = None
        
        # 日志器
        self.logger = get_logger(f"{self.__class__.__name__}")
        
        # 流式响应队列
        self._response_queue: asyncio.Queue = asyncio.Queue()
        self._is_streaming = False
        
        # 任务执行完成标志
        self._task_completed = False
        self._task_error = None
    
    def add_message(self, message: Message) -> None:
        """添加消息到历史记录"""
        self.history.add_message(message)
        self.updated_at = datetime.now()
        
        self.logger.info(
            "添加消息到对话历史",
            conversation_id=self.conversation_id,
            role=message.role,
            content_length=len(message.content)
        )
    
    def update_status(self, status: str) -> None:
        """更新任务状态"""
        old_status = self.status
        self.status = status
        self.updated_at = datetime.now()
        
        self.logger.info(
            "任务状态更新",
            conversation_id=self.conversation_id,
            old_status=old_status,
            new_status=status
        )
    
    def update_stage(self, stage: Union[WorkflowStage, str]) -> None:
        """更新当前阶段"""
        old_stage = self.current_stage
        # 如果传入的是枚举，取其值；如果是字符串，直接使用
        self.current_stage = stage.value if isinstance(stage, WorkflowStage) else stage
        self.updated_at = datetime.now()
        
        self.logger.info(
            "任务阶段更新",
            conversation_id=self.conversation_id,
            old_stage=old_stage,
            new_stage=self.current_stage
        )
    
    async def emit_response(self, response: StreamResponse) -> None:
        """发送流式响应"""
        if self._is_streaming:
            await self._response_queue.put(response)
            
            self.logger.debug(
                "发送流式响应",
                conversation_id=self.conversation_id,
                response_type=response.response_type,
                stage=response.stage
            )
    
    def update_progress(self, progress: float) -> None:
        """更新进度"""
        self.progress = progress
        self.updated_at = datetime.now()
        
        self.logger.info(
            "任务进度更新",
            conversation_id=self.conversation_id,
            stage=self.current_stage,
            progress=progress
        )
    
    async def emit_content(
        self,
        content: str,
        stage: Optional[Union[WorkflowStage, str]] = None,
        status: Optional[str] = None,
        progress: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """发送内容响应"""
        # 如果没有提供stage，使用当前阶段
        if stage is None:
            current_stage = self.current_stage
        else:
            # 如果传入的是枚举，取其值；如果是字符串，直接使用
            current_stage = stage.value if isinstance(stage, WorkflowStage) else stage
        
        # 如果没有提供status，使用当前状态
        current_status = status or self.status
        response = StreamResponse.create_content_response(
            conversation_id=self.conversation_id,
            content=content,
            stage=current_stage,
            status=current_status,
            progress=progress,
            metadata=metadata
        )
        await self.emit_response(response)
    
    async def emit_error(
        self,
        error_code: str,
        error_message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """发送错误响应"""
        response = StreamResponse.create_error_response(
            conversation_id=self.conversation_id,
            error_code=error_code,
            error_message=error_message,
            metadata=metadata
        )
        await self.emit_response(response)
    
    async def stream_response(self, user_token: Optional[str] = None) -> AsyncIterator[StreamResponse]:
        """流式返回状态和消息内容"""
        self._is_streaming = True
        self._task_completed = False
        self._task_error = None
        
        # 保存用户token以供子类使用
        self.user_token = user_token
        
        try:
            # 启动任务执行
            execution_task = asyncio.create_task(self._execute_task())
            
            # 简化的流式响应处理
            while not self._task_completed:
                try:
                    # 等待响应队列中的数据，设置较短的超时
                    try:
                        response = await asyncio.wait_for(
                            self._response_queue.get(),
                            timeout=0.5
                        )
                        yield response
                    except asyncio.TimeoutError:
                        # 超时检查任务状态
                        if execution_task.done():
                            self._task_completed = True
                            
                            # 检查任务是否有异常
                            if execution_task.exception():
                                self._task_error = execution_task.exception()
                            
                            # 处理剩余的响应
                            while not self._response_queue.empty():
                                try:
                                    response = await asyncio.wait_for(
                                        self._response_queue.get(),
                                        timeout=0.1
                                    )
                                    yield response
                                except asyncio.TimeoutError:
                                    break
                            
                            break
                        else:
                            # 任务还在运行，继续等待
                            continue
                            
                except Exception as e:
                    self.logger.error(f"处理响应时出错: {str(e)}")
                    break
            
            # 如果任务有错误，发送错误响应
            if self._task_error:
                error_response = StreamResponse.create_error_response(
                    conversation_id=self.conversation_id,
                    error_code="EXECUTION_ERROR",
                    error_message=f"任务执行失败: {str(self._task_error)}"
                )
                yield error_response
            
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "conversation_id": self.conversation_id,
                    "stage": self.current_stage,
                    "status": self.status
                }
            )
            
            # 发送错误响应
            error_response = StreamResponse.create_error_response(
                conversation_id=self.conversation_id,
                error_code="STREAM_ERROR",
                error_message=f"流式响应错误: {str(e)}"
            )
            yield error_response
            
        finally:
            self._is_streaming = False
    
    async def _execute_task(self) -> None:
        """执行任务的内部方法"""
        try:
            self.update_status("running")
            await self.execute()
            self.update_status("completed")
            
        except Exception as e:
            self.update_status("error")
            self._task_error = e
            self.logger.error_with_context(
                e,
                {
                    "conversation_id": self.conversation_id,
                    "stage": self.current_stage
                }
            )
            
            # 发送错误信息
            await self.emit_error(
                error_code="EXECUTION_ERROR",
                error_message=f"任务执行错误: {str(e)}"
            )
        finally:
            self._task_completed = True
    
    @abstractmethod
    async def execute(self) -> None:
        """
        执行任务的抽象方法
        
        子类必须实现此方法来定义具体的执行逻辑。
        """
        pass

    def get_conversation_summary(self) -> Dict[str, Any]:
        """获取对话摘要"""
        return {
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "mode": self.mode,
            "status": self.status,
            "current_stage": self.current_stage,
            "message_count": len(self.history.messages),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata
        }
