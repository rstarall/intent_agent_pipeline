"""
LangGraph边条件定义模块

定义工作流中节点之间的条件路由逻辑。
"""

from typing import Literal
from .state_manager import AgentState, StateManager
from ..config import get_logger


class EdgeConditions:
    """边条件定义类"""
    
    def __init__(self):
        """初始化边条件"""
        self.logger = get_logger("EdgeConditions")
    
    def should_continue_search(self, state: AgentState) -> Literal["continue", "finish"]:
        """
        判断是否应该继续搜索
        
        Args:
            state: 当前状态
            
        Returns:
            Literal["continue", "finish"]: 路由决策
        """
        try:
            # 检查总控制者的决策
            master_decision = state.get("master_decision", "")
            need_more_info = state.get("need_more_info", True)
            
            self.logger.info(
                "检查是否继续搜索",
                master_decision=master_decision,
                need_more_info=need_more_info,
                conversation_id=state["metadata"].get("conversation_id")
            )
            
            # 如果总控制者明确决定完成，则结束
            if master_decision == "finish":
                return "finish"
            
            # 如果总控制者决定继续，则继续
            if master_decision == "continue":
                return "continue"
            
            # 如果没有明确决策，根据need_more_info判断
            if need_more_info:
                return "continue"
            else:
                return "finish"
                
        except Exception as e:
            self.logger.error(f"判断搜索条件失败: {str(e)}")
            # 默认继续搜索
            return "continue"
    
    def should_proceed_to_summary(self, state: AgentState) -> Literal["summary", "master"]:
        """
        判断是否应该进入摘要阶段
        
        Args:
            state: 当前状态
            
        Returns:
            Literal["summary", "master"]: 路由决策
        """
        try:
            # 检查是否有搜索结果
            all_results = StateManager.get_all_search_results(state)
            has_any_results = any(len(results) > 0 for results in all_results.values())
            
            self.logger.info(
                "检查是否进入摘要阶段",
                has_results=has_any_results,
                result_counts={k: len(v) for k, v in all_results.items()}
            )
            
            if has_any_results:
                return "summary"
            else:
                # 如果没有结果，回到总控制者重新决策
                return "master"
                
        except Exception as e:
            self.logger.error(f"判断摘要条件失败: {str(e)}")
            return "summary"
    
    def should_generate_final_answer(self, state: AgentState) -> Literal["final", "master"]:
        """
        判断是否应该生成最终答案
        
        Args:
            state: 当前状态
            
        Returns:
            Literal["final", "master"]: 路由决策
        """
        try:
            # 检查是否有摘要信息
            all_summaries = StateManager.get_all_summaries(state)
            has_any_summary = any(summary for summary in all_summaries.values())
            
            # 检查是否有足够信息
            has_sufficient_info = StateManager.has_sufficient_info(state)
            
            self.logger.info(
                "检查是否生成最终答案",
                has_summaries=has_any_summary,
                has_sufficient_info=has_sufficient_info,
                summaries={k: bool(v) for k, v in all_summaries.items()}
            )
            
            if has_any_summary or has_sufficient_info:
                return "final"
            else:
                # 如果信息不足，回到总控制者
                return "master"
                
        except Exception as e:
            self.logger.error(f"判断最终答案条件失败: {str(e)}")
            return "final"
    
    def check_max_iterations(self, state: AgentState, max_iterations: int = 5) -> Literal["continue", "force_finish"]:
        """
        检查是否达到最大迭代次数
        
        Args:
            state: 当前状态
            max_iterations: 最大迭代次数
            
        Returns:
            Literal["continue", "force_finish"]: 路由决策
        """
        try:
            execution_path = state.get("execution_path", [])
            master_agent_count = execution_path.count("master_agent")
            
            self.logger.info(
                "检查最大迭代次数",
                master_agent_count=master_agent_count,
                max_iterations=max_iterations,
                execution_path=execution_path
            )
            
            if master_agent_count >= max_iterations:
                self.logger.warning(
                    "达到最大迭代次数，强制结束",
                    iterations=master_agent_count
                )
                return "force_finish"
            else:
                return "continue"
                
        except Exception as e:
            self.logger.error(f"检查迭代次数失败: {str(e)}")
            return "continue"
    
    def route_after_master(self, state: AgentState) -> Literal["query_optimizer", "final_output", "end"]:
        """
        总控制者之后的路由决策
        
        Args:
            state: 当前状态
            
        Returns:
            Literal["query_optimizer", "final_output", "end"]: 路由决策
        """
        try:
            # 首先检查最大迭代次数
            if self.check_max_iterations(state) == "force_finish":
                return "final_output"
            
            # 检查总控制者决策
            decision = self.should_continue_search(state)
            
            if decision == "continue":
                return "query_optimizer"
            elif decision == "finish":
                return "final_output"
            else:
                return "end"
                
        except Exception as e:
            self.logger.error(f"总控制者后路由失败: {str(e)}")
            return "final_output"
    
    def route_after_parallel_search(self, state: AgentState) -> Literal["summary_agent", "master_agent"]:
        """
        并行搜索之后的路由决策
        
        Args:
            state: 当前状态
            
        Returns:
            Literal["summary_agent", "master_agent"]: 路由决策
        """
        try:
            decision = self.should_proceed_to_summary(state)
            
            if decision == "summary":
                return "summary_agent"
            else:
                return "master_agent"
                
        except Exception as e:
            self.logger.error(f"并行搜索后路由失败: {str(e)}")
            return "summary_agent"
    
    def route_after_summary(self, state: AgentState) -> Literal["master_agent", "final_output"]:
        """
        摘要之后的路由决策
        
        Args:
            state: 当前状态
            
        Returns:
            Literal["master_agent", "final_output"]: 路由决策
        """
        try:
            # 检查是否达到最大迭代次数
            if self.check_max_iterations(state) == "force_finish":
                return "final_output"
            
            # 检查是否有足够信息生成最终答案
            decision = self.should_generate_final_answer(state)
            
            if decision == "final":
                return "final_output"
            else:
                return "master_agent"
                
        except Exception as e:
            self.logger.error(f"摘要后路由失败: {str(e)}")
            return "master_agent"
    
    def is_workflow_complete(self, state: AgentState) -> bool:
        """
        检查工作流是否完成
        
        Args:
            state: 当前状态
            
        Returns:
            bool: 是否完成
        """
        try:
            # 检查是否有最终答案
            final_answer = state.get("final_answer", "")
            
            # 检查当前阶段
            current_stage = state.get("current_stage", "")
            
            # 如果有最终答案且当前阶段是final_output，则完成
            is_complete = bool(final_answer) and current_stage == "final_output"
            
            self.logger.info(
                "检查工作流完成状态",
                is_complete=is_complete,
                has_final_answer=bool(final_answer),
                current_stage=current_stage
            )
            
            return is_complete
            
        except Exception as e:
            self.logger.error(f"检查工作流完成状态失败: {str(e)}")
            return False
    
    def get_next_node_name(self, current_node: str, state: AgentState) -> str:
        """
        获取下一个节点名称（用于调试和日志）
        
        Args:
            current_node: 当前节点名称
            state: 当前状态
            
        Returns:
            str: 下一个节点名称
        """
        try:
            if current_node == "master_agent":
                next_node = self.route_after_master(state)
            elif current_node == "parallel_search":
                next_node = self.route_after_parallel_search(state)
            elif current_node == "summary_agent":
                next_node = self.route_after_summary(state)
            else:
                next_node = "unknown"
            
            self.logger.debug(
                "路由决策",
                current_node=current_node,
                next_node=next_node
            )
            
            return next_node
            
        except Exception as e:
            self.logger.error(f"获取下一节点失败: {str(e)}")
            return "unknown"
