"""
Pipeline主接口模块

统一Workflow和Agent两种执行模式的接口。
"""

import uuid
from typing import Dict, List, Optional, AsyncIterator, Any
from datetime import datetime

from .base_task import BaseConversationTask
from .workflow_task import WorkflowTask
from .agent_task import AgentTask
from ..models import (
    Message, ConversationHistory, StreamResponse, 
    ExecutionModeType, MessageRole
)
from ..config import get_logger


class PipelineInterface:
    """Pipeline主接口类"""
    
    def __init__(self):
        """初始化Pipeline接口"""
        self.logger = get_logger("PipelineInterface")
        self.active_conversations: Dict[str, BaseConversationTask] = {}
    
    def create_conversation(self, user_id: str, mode: ExecutionModeType = "workflow") -> str:
        """
        创建新对话会话
        
        Args:
            user_id: 用户ID
            mode: 执行模式 ("workflow" 或 "agent")
            
        Returns:
            conversation_id: 对话唯一标识
        """
        conversation_id = str(uuid.uuid4())
        
        try:
            # 根据模式创建对应的任务实例
            if mode == "workflow":
                task = WorkflowTask(user_id, conversation_id)
            elif mode == "agent":
                task = AgentTask(user_id, conversation_id)
            else:
                raise ValueError(f"不支持的执行模式: {mode}")
            
            # 保存到活跃对话字典
            self.active_conversations[conversation_id] = task
            
            self.logger.info(
                "创建新对话会话",
                conversation_id=conversation_id,
                user_id=user_id,
                mode=mode
            )
            
            return conversation_id
            
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "user_id": user_id,
                    "mode": mode,
                    "conversation_id": conversation_id
                }
            )
            raise
    
    async def send_message(
        self, 
        conversation_id: str, 
        message: str,
        user_id: Optional[str] = None
    ) -> AsyncIterator[StreamResponse]:
        """
        发送消息并获取流式响应
        
        Args:
            conversation_id: 对话ID
            message: 用户消息
            user_id: 用户ID（可选，用于验证）
            
        Yields:
            StreamResponse: 流式响应
        """
        try:
            # 获取对话任务
            task = self._get_conversation_task(conversation_id)
            
            # 验证用户ID（如果提供）
            if user_id and task.user_id != user_id:
                raise ValueError("用户ID不匹配")
            
            # 添加用户消息到历史
            user_message = Message(
                role="user",
                content=message,
                metadata={"source": "user_input"}
            )
            task.add_message(user_message)
            
            self.logger.info(
                "接收用户消息",
                conversation_id=conversation_id,
                message_length=len(message),
                mode=task.mode
            )
            
            # 流式执行任务并返回响应
            async for response in task.stream_response():
                yield response
                
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "message_length": len(message) if message else 0
                }
            )
            
            # 发送错误响应
            error_response = StreamResponse.create_error_response(
                conversation_id=conversation_id,
                error_code="SEND_MESSAGE_ERROR",
                error_message=f"发送消息失败: {str(e)}"
            )
            yield error_response
    
    def get_conversation_history(self, conversation_id: str) -> List[Message]:
        """
        获取对话历史
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            List[Message]: 消息列表
        """
        try:
            task = self._get_conversation_task(conversation_id)
            return task.history.messages
            
        except Exception as e:
            self.logger.error_with_context(
                e,
                {"conversation_id": conversation_id}
            )
            raise
    
    def get_conversation_summary(self, conversation_id: str) -> Dict[str, Any]:
        """
        获取对话摘要信息
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            Dict[str, Any]: 对话摘要
        """
        try:
            task = self._get_conversation_task(conversation_id)
            
            # 获取基础摘要
            summary = task.get_conversation_summary()
            
            # 如果是Agent任务，添加额外信息
            if isinstance(task, AgentTask):
                summary.update(task.get_execution_summary())
            
            return summary
            
        except Exception as e:
            self.logger.error_with_context(
                e,
                {"conversation_id": conversation_id}
            )
            raise
    
    def list_active_conversations(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        列出活跃对话
        
        Args:
            user_id: 用户ID（可选，用于过滤）
            
        Returns:
            List[Dict[str, Any]]: 对话摘要列表
        """
        try:
            conversations = []
            
            for conversation_id, task in self.active_conversations.items():
                # 如果指定了用户ID，则过滤
                if user_id and task.user_id != user_id:
                    continue
                
                summary = {
                    "conversation_id": conversation_id,
                    "user_id": task.user_id,
                    "mode": task.mode,
                    "status": task.status,
                    "current_stage": task.current_stage,
                    "message_count": len(task.history.messages),
                    "created_at": task.created_at.isoformat(),
                    "updated_at": task.updated_at.isoformat()
                }
                
                conversations.append(summary)
            
            return conversations
            
        except Exception as e:
            self.logger.error_with_context(e, {"user_id": user_id})
            raise
    
    def close_conversation(self, conversation_id: str) -> bool:
        """
        关闭对话会话
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            bool: 是否成功关闭
        """
        try:
            if conversation_id in self.active_conversations:
                task = self.active_conversations[conversation_id]
                
                # 更新任务状态
                if task.status == "running":
                    task.update_status("cancelled")
                
                # 从活跃对话中移除
                del self.active_conversations[conversation_id]
                
                self.logger.info(
                    "关闭对话会话",
                    conversation_id=conversation_id,
                    user_id=task.user_id,
                    final_status=task.status
                )
                
                return True
            
            return False
            
        except Exception as e:
            self.logger.error_with_context(
                e,
                {"conversation_id": conversation_id}
            )
            return False
    
    def _get_conversation_task(self, conversation_id: str) -> BaseConversationTask:
        """
        获取对话任务实例
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            BaseConversationTask: 任务实例
            
        Raises:
            ValueError: 如果对话不存在
        """
        if conversation_id not in self.active_conversations:
            raise ValueError(f"对话不存在: {conversation_id}")
        
        return self.active_conversations[conversation_id]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取Pipeline统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        try:
            total_conversations = len(self.active_conversations)
            workflow_count = sum(1 for task in self.active_conversations.values() 
                               if task.mode == "workflow")
            agent_count = sum(1 for task in self.active_conversations.values() 
                            if task.mode == "agent")
            
            status_counts = {}
            for task in self.active_conversations.values():
                status_counts[task.status] = status_counts.get(task.status, 0) + 1
            
            return {
                "total_conversations": total_conversations,
                "workflow_conversations": workflow_count,
                "agent_conversations": agent_count,
                "status_distribution": status_counts,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error_with_context(e, {})
            raise
