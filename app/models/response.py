"""
响应数据模型模块

定义系统中使用的各种响应数据结构，包括流式响应、API响应等。
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field

from .enums import (
    TaskStatus, ResponseType, AgentType, WorkflowStage
)


class StreamResponse(BaseModel):
    """流式响应数据模型"""
    
    conversation_id: str = Field(..., description="对话ID")
    response_type: str = Field(..., description="响应类型")
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间")
    
    # 状态信息字段
    stage: Optional[str] = Field(None, description="当前阶段")
    agent_name: Optional[str] = Field(None, description="Agent名称")
    status: Optional[str] = Field(None, description="任务状态")
    progress: Optional[float] = Field(None, description="执行进度 (0.0-1.0)")
    
    # 内容字段
    content: Optional[str] = Field(None, description="消息内容")
    metadata: Optional[Dict[str, Any]] = Field(None, description="附加信息")
    
    # 错误字段
    error_code: Optional[str] = Field(None, description="错误代码")
    error_message: Optional[str] = Field(None, description="错误消息")
    
    class Config:
        """Pydantic配置"""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        # 确保正确的UTF-8编码
        validate_assignment = True
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，符合intent_pipeline.py期望的结构"""
        data = {
            "type": self.response_type,
            "timestamp": self.timestamp.isoformat()
        }
        
        # 根据响应类型添加对应字段
        if self.response_type == "content":
            data["content"] = self.content or ""
            if self.stage:
                data["stage"] = self.stage
            if self.status:
                data["status"] = self.status
            if self.progress is not None:
                data["progress"] = self.progress
        elif self.response_type == "status":
            data["description"] = self._get_status_description()
            if self.stage:
                data["stage"] = self.stage
        elif self.response_type == "progress":
            data["progress"] = self.progress or 0.0
            if self.stage:
                data["stage"] = self.stage
        elif self.response_type == "error":
            data["error"] = self.error_message or "未知错误"
            if self.error_code:
                data["code"] = self.error_code
        
        # 添加元数据（如果有）
        if self.metadata:
            data.update(self.metadata)
        
        return data
    
    def _get_status_description(self) -> str:
        """获取状态描述"""
        if self.stage:
            # 与intent_pipeline.py中的STATUS_MESSAGES匹配
            stage_descriptions = {
                "initialization": "正在初始化对话...",
                "expanding_question": "正在扩写优化问题...",
                "analyzing_question": "正在分析问题...",
                "task_scheduling": "正在调度任务...",
                "executing_tasks": "正在执行任务...",
                "online_search": "正在进行联网搜索...",
                "knowledge_search": "正在搜索知识库...",
                "lightrag_query": "正在进行LightRAG查询...",
                "response_generation": "正在生成响应...",
                "generating_answer": "正在生成答案...",
                "completed": "处理完成",
                "processing": "正在处理您的问题...",
                "streaming": "正在获取流式响应...",
                "agent_workflow": "正在执行Agent工作流...",
                "error": "处理过程中出现错误"
            }
            return stage_descriptions.get(self.stage, f"当前阶段: {self.stage}")
        return "正在处理..."
    
    @classmethod
    def create_status_response(
        cls,
        conversation_id: str,
        stage: str,
        agent_name: Optional[str] = None,
        status: str = "running",
        progress: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "StreamResponse":
        """创建状态响应"""
        return cls(
            conversation_id=conversation_id,
            response_type="status",
            stage=stage,
            agent_name=agent_name,
            status=status,
            progress=progress,
            metadata=metadata or {}
        )
    
    @classmethod
    def create_content_response(
        cls,
        conversation_id: str,
        content: str,
        stage: Optional[str] = None,
        status: Optional[str] = None,
        progress: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "StreamResponse":
        """创建内容响应"""
        return cls(
            conversation_id=conversation_id,
            response_type="content",
            content=content,
            stage=stage,
            status=status,
            progress=progress,
            metadata=metadata or {}
        )
    
    @classmethod
    def create_error_response(
        cls,
        conversation_id: str,
        error_code: str,
        error_message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "StreamResponse":
        """创建错误响应"""
        return cls(
            conversation_id=conversation_id,
            response_type="error",
            error_code=error_code,
            error_message=error_message,
            metadata=metadata or {}
        )


class APIResponse(BaseModel):
    """通用API响应数据模型"""
    
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    data: Optional[Any] = Field(None, description="响应数据")
    error_code: Optional[str] = Field(None, description="错误代码")
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间")
    
    class Config:
        """Pydantic配置"""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    @classmethod
    def success_response(
        cls,
        message: str = "操作成功",
        data: Optional[Any] = None
    ) -> "APIResponse":
        """创建成功响应"""
        return cls(
            success=True,
            message=message,
            data=data
        )
    
    @classmethod
    def error_response(
        cls,
        message: str,
        error_code: Optional[str] = None,
        data: Optional[Any] = None
    ) -> "APIResponse":
        """创建错误响应"""
        return cls(
            success=False,
            message=message,
            error_code=error_code,
            data=data
        )


class HealthCheckResponse(BaseModel):
    """健康检查响应数据模型"""
    
    status: str = Field(..., description="服务状态")
    version: str = Field(..., description="版本号")
    timestamp: datetime = Field(default_factory=datetime.now, description="检查时间")
    services: Dict[str, str] = Field(default_factory=dict, description="依赖服务状态")
    
    class Config:
        """Pydantic配置"""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SearchResult(BaseModel):
    """搜索结果数据模型"""
    
    title: str = Field(..., description="标题")
    content: str = Field(..., description="内容")
    url: Optional[str] = Field(None, description="链接")
    score: Optional[float] = Field(None, description="相关性分数")
    source: str = Field(..., description="来源")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "title": self.title,
            "content": self.content,
            "url": self.url,
            "score": self.score,
            "source": self.source,
            "metadata": self.metadata
        }
