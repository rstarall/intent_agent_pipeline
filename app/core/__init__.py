"""
核心业务逻辑模块

提供基础任务类、工作流任务、Agent任务和Pipeline主接口。
"""

from .base_task import BaseConversationTask
from .workflow_task import WorkflowTask
from .agent_task import AgentTask
from .pipeline import PipelineInterface

__all__ = [
    "BaseConversationTask",
    "WorkflowTask",
    "AgentTask",
    "PipelineInterface"
]
