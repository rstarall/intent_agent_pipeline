"""
枚举类型定义模块

定义系统中使用的各种枚举类型，包括任务状态、响应类型、Agent类型等。
"""

from enum import Enum
from typing import Literal


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"           # 等待执行
    RUNNING = "running"           # 执行中
    COMPLETED = "completed"       # 已完成
    ERROR = "error"              # 执行错误
    CANCELLED = "cancelled"       # 已取消


class ResponseType(Enum):
    """响应类型枚举"""
    STATUS = "status"           # 状态信息
    CONTENT = "content"         # 聊天内容
    PROGRESS = "progress"       # 进度信息
    ERROR = "error"            # 错误信息


class MessageRole(Enum):
    """消息角色枚举"""
    USER = "user"              # 用户消息
    ASSISTANT = "assistant"    # 助手消息
    SYSTEM = "system"          # 系统消息


class ExecutionMode(Enum):
    """执行模式枚举"""
    WORKFLOW = "workflow"      # 工作流模式
    AGENT = "agent"           # 代理模式


class AgentType(Enum):
    """Agent类型枚举"""
    MASTER = "master_agent"                    # 总控制者Agent
    QUERY_OPTIMIZER = "query_optimizer"       # 问题优化Agent
    ONLINE_SEARCH = "online_search"           # 在线搜索Agent
    LIGHTRAG = "lightrag_agent"               # LightRAG Agent
    KNOWLEDGE_SEARCH = "knowledge_search"     # 知识库检索Agent
    SUMMARY = "summary_agent"                 # 内容摘要Agent
    FINAL_OUTPUT = "final_output"             # 最终输出Agent


class WorkflowStage(Enum):
    """工作流阶段枚举"""
    INITIALIZATION = "initialization"             # 初始化阶段
    EXPANDING_QUESTION = "expanding_question"     # 问题扩写与优化
    ANALYZING_QUESTION = "analyzing_question"     # 问题分析与规划
    TASK_SCHEDULING = "task_scheduling"           # 任务分解与调度
    EXECUTING_TASKS = "executing_tasks"           # 并行任务执行
    ONLINE_SEARCH = "online_search"               # 在线搜索阶段
    KNOWLEDGE_SEARCH = "knowledge_search"         # 知识库搜索阶段
    LIGHTRAG_QUERY = "lightrag_query"             # LightRAG查询阶段
    REPORT_GENERATION = "report_generation"       # 报告生成阶段(workflow)
    RESPONSE_GENERATION = "response_generation"   # 响应生成阶段(Agent)
    GENERATING_ANSWER = "generating_answer"       # 结果整合与回答
    AGENT_WORKFLOW = "agent_workflow"             # Agent工作流阶段



class SearchType(Enum):
    """搜索类型枚举"""
    ONLINE_SEARCH = "online_search"           # 在线搜索
    KNOWLEDGE_SEARCH = "knowledge_search"     # 知识库搜索
    LIGHTRAG_SEARCH = "lightrag_search"       # LightRAG搜索


class LightRagMode(Enum):
    """LightRAG模式枚举"""
    NAIVE = "naive"           # 简单模式
    LOCAL = "local"           # 本地模式
    GLOBAL = "global"         # 全局模式
    HYBRID = "hybrid"         # 混合模式
    MIX = "mix"              # 混合模式（默认）



