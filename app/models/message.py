"""
消息数据模型模块

定义系统中使用的消息相关数据结构，包括消息、对话历史等。
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from .enums import MessageRole, MessageRoleType


class Message(BaseModel):
    """消息数据模型"""
    
    role: MessageRoleType = Field(..., description="消息角色")
    content: str = Field(..., description="消息内容")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    
    class Config:
        """Pydantic配置"""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """从字典创建消息对象"""
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


class ConversationHistory(BaseModel):
    """对话历史数据模型"""
    
    conversation_id: str = Field(..., description="对话ID")
    user_id: str = Field(..., description="用户ID")
    messages: List[Message] = Field(default_factory=list, description="消息列表")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="对话元数据")
    
    def add_message(self, message: Message) -> None:
        """添加消息到历史记录"""
        self.messages.append(message)
        self.updated_at = datetime.now()
    
    def get_recent_messages(self, limit: int = 10) -> List[Message]:
        """获取最近的消息"""
        return self.messages[-limit:] if limit > 0 else self.messages
    
    def get_messages_by_role(self, role: MessageRoleType) -> List[Message]:
        """根据角色获取消息"""
        return [msg for msg in self.messages if msg.role == role]
    
    def to_langchain_format(self) -> List[Dict[str, str]]:
        """转换为LangChain格式的消息列表"""
        return [
            {"role": msg.role, "content": msg.content}
            for msg in self.messages
        ]
    
    class Config:
        """Pydantic配置"""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ChatRequest(BaseModel):
    """聊天请求数据模型"""
    
    conversation_id: str = Field(..., description="对话ID")
    message: str = Field(..., description="用户消息")
    user_id: str = Field(..., description="用户ID")
    mode: Optional[str] = Field(default="workflow", description="执行模式")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="请求元数据")
    
    # 支持从request body中获取用户信息
    user: Optional[Dict[str, Any]] = Field(None, description="用户信息，包含token等")
    
    def get_user_token(self) -> Optional[str]:
        """获取用户token"""
        if self.user:
            return self.user.get("token")
        return None


class CreateConversationRequest(BaseModel):
    """创建对话请求数据模型"""
    
    user_id: str = Field(..., description="用户ID")
    mode: str = Field(default="workflow", description="执行模式")
    conversation_id: Optional[str] = Field(None, description="可选的对话ID，如果提供则使用该ID，否则自动生成")
    
    # 支持从request body中获取用户信息
    user: Optional[Dict[str, Any]] = Field(None, description="用户信息，包含token等")
    
    def get_user_token(self) -> Optional[str]:
        """获取用户token"""
        if self.user:
            return self.user.get("token")
        return None


class ChatResponse(BaseModel):
    """聊天响应数据模型"""
    
    conversation_id: str = Field(..., description="对话ID")
    message: str = Field(..., description="响应消息")
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="响应元数据")
    
    class Config:
        """Pydantic配置"""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
