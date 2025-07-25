"""
数据模型模块

导出所有数据模型和枚举类型，提供统一的数据结构定义。
"""

# 枚举类型
from .enums import (
    TaskStatus, ResponseType, MessageRole, ExecutionMode,
    AgentType, WorkflowStage, SearchType, LightRagMode
)

# 消息相关模型
from .message import (
    Message, ConversationHistory, ChatRequest, ChatResponse, CreateConversationRequest
)

# 上下文相关模型
from .context import (
    OnlineSearchContext, KnowledgeSearchContext, LightRagContext,
    GlobalContext, TaskConfig, ParallelTasksConfig
)

# 响应相关模型
from .response import (
    StreamResponse, APIResponse, HealthCheckResponse, SearchResult
)

__all__ = [
    # 枚举类型
    "TaskStatus", "ResponseType", "MessageRole", "ExecutionMode",
    "AgentType", "WorkflowStage", "SearchType", "LightRagMode",

    # 消息相关模型
    "Message", "ConversationHistory", "ChatRequest", "ChatResponse", "CreateConversationRequest",

    # 上下文相关模型
    "OnlineSearchContext", "KnowledgeSearchContext", "LightRagContext",
    "GlobalContext", "TaskConfig", "ParallelTasksConfig",

    # 响应相关模型
    "StreamResponse", "APIResponse", "HealthCheckResponse", "SearchResult"
]
