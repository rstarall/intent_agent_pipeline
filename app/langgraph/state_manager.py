"""
LangGraph状态管理器模块

定义Agent系统的状态结构和状态管理逻辑。
"""

from typing import TypedDict, List, Dict, Any, Optional, Annotated
from datetime import datetime
import operator

from ..models import GlobalContext


class AgentState(TypedDict):
    """LangGraph Agent状态定义"""
    
    # 基础信息
    user_question: str                          # 用户问题
    conversation_history: List[Dict[str, Any]]  # 对话历史
    current_stage: str                          # 当前阶段
    final_answer: str                           # 最终回答
    
    # 检索结果
    online_search_results: Annotated[List[Dict[str, Any]], operator.add]     # 在线搜索结果
    knowledge_search_results: Annotated[List[Dict[str, Any]], operator.add]  # 知识库搜索结果
    lightrag_results: Annotated[List[Dict[str, Any]], operator.add]          # LightRAG结果
    
    # Agent决策和控制
    master_decision: str                        # 总控制者决策
    need_more_info: bool                       # 是否需要更多信息
    optimized_queries: Dict[str, str]          # 优化后的查询
    
    # 摘要和上下文
    online_summary: str                        # 在线搜索摘要
    knowledge_summary: str                     # 知识库摘要
    lightrag_summary: str                      # LightRAG摘要
    
    # 元数据
    metadata: Dict[str, Any]                   # 元数据信息
    execution_path: Annotated[List[str], operator.add]  # 执行路径
    agent_outputs: Dict[str, Any]              # Agent输出记录


class StateManager:
    """状态管理器"""
    
    def __init__(self):
        """初始化状态管理器"""
        pass
    
    @staticmethod
    def create_initial_state(
        user_question: str,
        conversation_history: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> AgentState:
        """
        创建初始状态
        
        Args:
            user_question: 用户问题
            conversation_history: 对话历史
            metadata: 元数据
            
        Returns:
            AgentState: 初始状态
        """
        return AgentState(
            # 基础信息
            user_question=user_question,
            conversation_history=conversation_history,
            current_stage="master_agent",
            final_answer="",
            
            # 检索结果
            online_search_results=[],
            knowledge_search_results=[],
            lightrag_results=[],
            
            # Agent决策和控制
            master_decision="",
            need_more_info=True,
            optimized_queries={},
            
            # 摘要和上下文
            online_summary="",
            knowledge_summary="",
            lightrag_summary="",
            
            # 元数据
            metadata=metadata or {},
            execution_path=[],
            agent_outputs={}
        )
    
    @staticmethod
    def update_stage(state: AgentState, new_stage: str) -> AgentState:
        """
        更新当前阶段
        
        Args:
            state: 当前状态
            new_stage: 新阶段
            
        Returns:
            AgentState: 更新后的状态
        """
        state["current_stage"] = new_stage
        state["execution_path"].append(new_stage)
        return state
    
    @staticmethod
    def add_search_results(
        state: AgentState,
        result_type: str,
        results: List[Dict[str, Any]]
    ) -> AgentState:
        """
        添加搜索结果
        
        Args:
            state: 当前状态
            result_type: 结果类型 (online, knowledge, lightrag)
            results: 搜索结果
            
        Returns:
            AgentState: 更新后的状态
        """
        if result_type == "online":
            state["online_search_results"].extend(results)
        elif result_type == "knowledge":
            state["knowledge_search_results"].extend(results)
        elif result_type == "lightrag":
            state["lightrag_results"].extend(results)
        
        return state
    
    @staticmethod
    def update_summaries(
        state: AgentState,
        online_summary: Optional[str] = None,
        knowledge_summary: Optional[str] = None,
        lightrag_summary: Optional[str] = None
    ) -> AgentState:
        """
        更新摘要信息
        
        Args:
            state: 当前状态
            online_summary: 在线搜索摘要
            knowledge_summary: 知识库摘要
            lightrag_summary: LightRAG摘要
            
        Returns:
            AgentState: 更新后的状态
        """
        if online_summary is not None:
            state["online_summary"] = online_summary
        if knowledge_summary is not None:
            state["knowledge_summary"] = knowledge_summary
        if lightrag_summary is not None:
            state["lightrag_summary"] = lightrag_summary
        
        return state
    
    @staticmethod
    def set_master_decision(
        state: AgentState,
        decision: str,
        need_more_info: bool
    ) -> AgentState:
        """
        设置总控制者决策
        
        Args:
            state: 当前状态
            decision: 决策结果
            need_more_info: 是否需要更多信息
            
        Returns:
            AgentState: 更新后的状态
        """
        state["master_decision"] = decision
        state["need_more_info"] = need_more_info
        return state
    
    @staticmethod
    def set_optimized_queries(
        state: AgentState,
        queries: Dict[str, str]
    ) -> AgentState:
        """
        设置优化后的查询
        
        Args:
            state: 当前状态
            queries: 优化后的查询字典
            
        Returns:
            AgentState: 更新后的状态
        """
        state["optimized_queries"] = queries
        return state
    
    @staticmethod
    def set_final_answer(state: AgentState, answer: str) -> AgentState:
        """
        设置最终回答
        
        Args:
            state: 当前状态
            answer: 最终回答
            
        Returns:
            AgentState: 更新后的状态
        """
        state["final_answer"] = answer
        return state
    
    @staticmethod
    def record_agent_output(
        state: AgentState,
        agent_name: str,
        output: Dict[str, Any]
    ) -> AgentState:
        """
        记录Agent输出
        
        Args:
            state: 当前状态
            agent_name: Agent名称
            output: Agent输出
            
        Returns:
            AgentState: 更新后的状态
        """
        state["agent_outputs"][agent_name] = {
            "output": output,
            "timestamp": datetime.now().isoformat()
        }
        return state
    
    @staticmethod
    def get_all_search_results(state: AgentState) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取所有搜索结果
        
        Args:
            state: 当前状态
            
        Returns:
            Dict[str, List[Dict[str, Any]]]: 所有搜索结果
        """
        return {
            "online": state["online_search_results"],
            "knowledge": state["knowledge_search_results"],
            "lightrag": state["lightrag_results"]
        }
    
    @staticmethod
    def get_all_summaries(state: AgentState) -> Dict[str, str]:
        """
        获取所有摘要
        
        Args:
            state: 当前状态
            
        Returns:
            Dict[str, str]: 所有摘要
        """
        return {
            "online": state["online_summary"],
            "knowledge": state["knowledge_summary"],
            "lightrag": state["lightrag_summary"]
        }
    
    @staticmethod
    def has_sufficient_info(state: AgentState) -> bool:
        """
        判断是否有足够的信息
        
        Args:
            state: 当前状态
            
        Returns:
            bool: 是否有足够信息
        """
        # 检查是否有任何搜索结果
        has_results = (
            len(state["online_search_results"]) > 0 or
            len(state["knowledge_search_results"]) > 0 or
            len(state["lightrag_results"]) > 0
        )
        
        # 检查是否有摘要
        has_summaries = (
            state["online_summary"] or
            state["knowledge_summary"] or
            state["lightrag_summary"]
        )
        
        return has_results and has_summaries
    
    @staticmethod
    def to_global_context(state: AgentState) -> GlobalContext:
        """
        将状态转换为全局上下文
        
        Args:
            state: 当前状态
            
        Returns:
            GlobalContext: 全局上下文
        """
        from ..models import OnlineSearchContext, KnowledgeSearchContext, LightRagContext
        
        # 创建各种上下文
        online_context = OnlineSearchContext()
        online_context.context_list = state["online_search_results"]
        online_context.context_summary = state["online_summary"]
        
        knowledge_context = KnowledgeSearchContext()
        knowledge_context.context_list = state["knowledge_search_results"]
        knowledge_context.context_summary = state["knowledge_summary"]
        
        lightrag_context = LightRagContext()
        lightrag_context.context_list = state["lightrag_results"]
        lightrag_context.context_summary = state["lightrag_summary"]
        
        # 创建全局上下文
        global_context = GlobalContext(
            online_search_context=online_context,
            knowledge_search_context=knowledge_context,
            lightrag_context=lightrag_context,
            current_stage=state["current_stage"],
            user_question=state["user_question"],
            final_answer=state["final_answer"],
            metadata=state["metadata"]
        )
        
        return global_context
