"""
基础对话任务类模块

定义对话任务的基础接口和流式响应机制。
"""

import uuid
import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, AsyncIterator, Any

from ..models import (
    Message, ConversationHistory, StreamResponse, 
    TaskStatus, TaskStatusType, ExecutionModeType
)
from ..config import get_logger


class BaseConversationTask(ABC):
    """对话任务基类"""
    
    def __init__(
        self,
        user_id: str,
        conversation_id: Optional[str] = None,
        mode: ExecutionModeType = "workflow"
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
        self.status: TaskStatusType = "pending"
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.metadata: Dict[str, Any] = {}
        
        # 日志器
        self.logger = get_logger(f"{self.__class__.__name__}")
        
        # 流式响应队列
        self._response_queue: asyncio.Queue = asyncio.Queue()
        self._is_streaming = False
    
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
    
    def update_status(self, status: TaskStatusType) -> None:
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
    
    def update_stage(self, stage: str) -> None:
        """更新当前阶段"""
        old_stage = self.current_stage
        self.current_stage = stage
        self.updated_at = datetime.now()
        
        self.logger.info(
            "任务阶段更新",
            conversation_id=self.conversation_id,
            old_stage=old_stage,
            new_stage=stage
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
    
    async def emit_status(
        self,
        stage: str,
        status: TaskStatusType = "running",
        progress: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """发送状态响应"""
        response = StreamResponse.create_status_response(
            conversation_id=self.conversation_id,
            stage=stage,
            status=status,
            progress=progress,
            metadata=metadata
        )
        await self.emit_response(response)
    
    async def emit_content(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """发送内容响应"""
        response = StreamResponse.create_content_response(
            conversation_id=self.conversation_id,
            content=content,
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
        
        # 保存用户token以供子类使用
        self.user_token = user_token
        
        try:
            # 启动任务执行
            execution_task = asyncio.create_task(self._execute_task())
            
            # 流式返回响应
            while True:
                try:
                    # 等待响应或任务完成
                    done, pending = await asyncio.wait(
                        [
                            asyncio.create_task(self._response_queue.get()),
                            execution_task
                        ],
                        return_when=asyncio.FIRST_COMPLETED,
                        timeout=1.0
                    )
                    
                    if execution_task in done:
                        # 任务执行完成，处理剩余响应
                        while not self._response_queue.empty():
                            response = await self._response_queue.get()
                            yield response
                        break
                    
                    if done:
                        # 有新响应
                        for task in done:
                            if task != execution_task:
                                response = await task
                                yield response
                    
                    # 取消未完成的任务
                    for task in pending:
                        task.cancel()
                        
                except asyncio.TimeoutError:
                    # 超时检查任务是否完成
                    if execution_task.done():
                        break
                    continue
                    
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "conversation_id": self.conversation_id,
                    "stage": self.current_stage,
                    "status": self.status
                }
            )
            
            await self.emit_error(
                error_code="STREAM_ERROR",
                error_message=f"流式响应错误: {str(e)}"
            )
            
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
            self.logger.error_with_context(
                e,
                {
                    "conversation_id": self.conversation_id,
                    "stage": self.current_stage
                }
            )
            
            await self.emit_error(
                error_code="EXECUTION_ERROR",
                error_message=f"任务执行错误: {str(e)}"
            )
    
    @abstractmethod
    async def execute(self) -> None:
        """
        执行任务的抽象方法
        
        子类必须实现此方法来定义具体的执行逻辑。
        """
        pass
    
    def get_conversation_summary(self) -> Dict[str, Any]:
        """获取对话摘要信息"""
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
