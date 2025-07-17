"""
上下文数据模型模块

定义Agent系统中使用的各种上下文数据结构，用于跨Agent信息共享。
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pydantic import BaseModel, Field

from .message import Message


@dataclass
class OnlineSearchContext:
    """在线搜索上下文"""
    context_list: List[Dict[str, Any]] = field(default_factory=list)  # 搜索结果列表
    context_summary: str = ""                                         # 内容摘要
    search_queries: List[str] = field(default_factory=list)          # 历史查询
    last_updated: datetime = field(default_factory=datetime.now)     # 最后更新时间
    
    def add_search_result(self, query: str, results: List[Dict[str, Any]]) -> None:
        """添加搜索结果"""
        self.search_queries.append(query)
        self.context_list.extend(results)
        self.last_updated = datetime.now()
    
    def update_summary(self, summary: str) -> None:
        """更新内容摘要"""
        self.context_summary = summary
        self.last_updated = datetime.now()


@dataclass
class KnowledgeSearchContext:
    """知识库搜索上下文"""
    context_list: List[Dict[str, Any]] = field(default_factory=list)  # 知识库结果
    context_summary: str = ""                                         # 内容摘要
    search_queries: List[str] = field(default_factory=list)          # 历史查询
    confidence_scores: List[float] = field(default_factory=list)     # 置信度分数
    last_updated: datetime = field(default_factory=datetime.now)     # 最后更新时间
    
    def add_search_result(self, query: str, results: List[Dict[str, Any]], 
                         confidence: float = 0.0) -> None:
        """添加搜索结果"""
        self.search_queries.append(query)
        self.context_list.extend(results)
        self.confidence_scores.append(confidence)
        self.last_updated = datetime.now()
    
    def update_summary(self, summary: str) -> None:
        """更新内容摘要"""
        self.context_summary = summary
        self.last_updated = datetime.now()


@dataclass
class LightRagContext:
    """LightRAG上下文"""
    context_list: List[Dict[str, Any]] = field(default_factory=list)  # 回答结果列表
    context_summary: str = ""                                         # 内容摘要
    search_queries: List[str] = field(default_factory=list)          # 历史查询
    last_updated: datetime = field(default_factory=datetime.now)     # 最后更新时间
    
    def add_search_result(self, query: str, results: List[Dict[str, Any]]) -> None:
        """添加搜索结果"""
        self.search_queries.append(query)
        self.context_list.extend(results)
        self.last_updated = datetime.now()
    
    def update_summary(self, summary: str) -> None:
        """更新内容摘要"""
        self.context_summary = summary
        self.last_updated = datetime.now()


@dataclass
class GlobalContext:
    """全局上下文状态"""
    online_search_context: OnlineSearchContext = field(default_factory=OnlineSearchContext)
    knowledge_search_context: KnowledgeSearchContext = field(default_factory=KnowledgeSearchContext)
    lightrag_context: LightRagContext = field(default_factory=LightRagContext)
    conversation_history: List[Message] = field(default_factory=list)
    current_stage: str = ""
    user_question: str = ""
    final_answer: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_all_contexts_summary(self) -> str:
        """获取所有上下文的摘要"""
        summaries = []
        
        if self.online_search_context.context_summary:
            summaries.append(f"在线搜索摘要: {self.online_search_context.context_summary}")
        
        if self.knowledge_search_context.context_summary:
            summaries.append(f"知识库摘要: {self.knowledge_search_context.context_summary}")
        
        if self.lightrag_context.context_summary:
            summaries.append(f"LightRAG摘要: {self.lightrag_context.context_summary}")
        
        return "\n".join(summaries) if summaries else "暂无上下文信息"


class TaskConfig(BaseModel):
    """任务配置数据模型"""
    
    type: str = Field(..., description="任务类型")
    query: str = Field(..., description="查询问题")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="任务参数")
    priority: int = Field(default=1, description="任务优先级")
    timeout: int = Field(default=30, description="超时时间(秒)")


class ParallelTasksConfig(BaseModel):
    """并行任务配置数据模型"""
    
    tasks: List[TaskConfig] = Field(..., description="任务列表")
    max_concurrency: int = Field(default=3, description="最大并发数")
    timeout: int = Field(default=60, description="总超时时间(秒)")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "tasks": [task.dict() for task in self.tasks],
            "max_concurrency": self.max_concurrency,
            "timeout": self.timeout
        }
