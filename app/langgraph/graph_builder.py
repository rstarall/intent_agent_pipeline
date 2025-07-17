"""
LangGraph图构建器模块

构建和管理LangGraph工作流图。
"""

from typing import Dict, Any, Optional, AsyncIterator
import asyncio

try:
    from langgraph.graph import StateGraph, END
    from langgraph.checkpoint.memory import MemorySaver
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False

from .state_manager import AgentState, StateManager
from .node_definitions import NodeDefinitions
from .edge_conditions import EdgeConditions
from .checkpoints.memory_store import MemoryCheckpointStore
from .checkpoints.redis_store import RedisCheckpointStore
from ..config import get_settings, get_logger


class LangGraphManager:
    """LangGraph图管理器"""
    
    def __init__(self, checkpoint_type: str = "memory"):
        """
        初始化图管理器
        
        Args:
            checkpoint_type: 检查点类型 ("memory" 或 "redis")
        """
        if not LANGGRAPH_AVAILABLE:
            raise ImportError("LangGraph库未安装，请运行: pip install langgraph")
        
        self.settings = get_settings()
        self.logger = get_logger("LangGraphManager")
        
        self.checkpoint_type = checkpoint_type
        self.checkpointer = self._create_checkpointer()
        
        # 初始化组件
        self.node_definitions = NodeDefinitions()
        self.edge_conditions = EdgeConditions()
        
        # 构建图
        self.graph = self._build_graph()
    
    def _create_checkpointer(self):
        """创建检查点存储器"""
        try:
            if self.checkpoint_type == "redis":
                return RedisCheckpointStore()
            else:
                return MemoryCheckpointStore()
                
        except Exception as e:
            self.logger.warning(f"创建{self.checkpoint_type}检查点存储器失败，使用内存存储: {str(e)}")
            return MemoryCheckpointStore()
    
    def _build_graph(self) -> StateGraph:
        """构建LangGraph工作流图"""
        try:
            # 创建状态图
            workflow = StateGraph(AgentState)
            
            # 添加节点
            workflow.add_node("master_agent", self.node_definitions.master_agent_node)
            workflow.add_node("query_optimizer", self.node_definitions.query_optimizer_node)
            workflow.add_node("parallel_search", self.node_definitions.parallel_search_node)
            workflow.add_node("summary_agent", self.node_definitions.summary_agent_node)
            workflow.add_node("final_output", self.node_definitions.final_output_node)
            
            # 设置入口点
            workflow.set_entry_point("master_agent")
            
            # 添加条件边
            workflow.add_conditional_edges(
                "master_agent",
                self.edge_conditions.route_after_master,
                {
                    "query_optimizer": "query_optimizer",
                    "final_output": "final_output",
                    "end": END
                }
            )
            
            # 添加固定边
            workflow.add_edge("query_optimizer", "parallel_search")
            
            # 并行搜索后的条件边
            workflow.add_conditional_edges(
                "parallel_search",
                self.edge_conditions.route_after_parallel_search,
                {
                    "summary_agent": "summary_agent",
                    "master_agent": "master_agent"
                }
            )
            
            # 摘要后的条件边
            workflow.add_conditional_edges(
                "summary_agent",
                self.edge_conditions.route_after_summary,
                {
                    "master_agent": "master_agent",
                    "final_output": "final_output"
                }
            )
            
            # 最终输出到结束
            workflow.add_edge("final_output", END)
            
            # 编译图
            if isinstance(self.checkpointer, MemoryCheckpointStore):
                # 使用自定义内存存储器
                compiled_graph = workflow.compile()
            else:
                # 使用LangGraph内置检查点
                compiled_graph = workflow.compile(checkpointer=MemorySaver())
            
            self.logger.info("LangGraph工作流图构建完成")
            
            return compiled_graph
            
        except Exception as e:
            self.logger.error_with_context(e, {"operation": "build_graph"})
            raise
    
    async def stream_workflow(
        self,
        initial_state: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        流式执行工作流
        
        Args:
            initial_state: 初始状态
            config: 配置参数
            
        Yields:
            Dict[str, Any]: 流式输出块
        """
        try:
            # 转换为AgentState
            agent_state = StateManager.create_initial_state(
                user_question=initial_state.get("user_question", ""),
                conversation_history=initial_state.get("conversation_history", []),
                metadata=initial_state.get("metadata", {})
            )
            
            # 更新其他字段
            for key, value in initial_state.items():
                if key in agent_state:
                    agent_state[key] = value
            
            self.logger.info(
                "开始流式执行工作流",
                user_question=agent_state["user_question"],
                conversation_id=agent_state["metadata"].get("conversation_id")
            )
            
            # 流式执行
            async for chunk in self.graph.astream(agent_state, config=config or {}):
                # 处理输出块
                processed_chunk = self._process_stream_chunk(chunk)
                if processed_chunk:
                    yield processed_chunk
            
            self.logger.info("工作流执行完成")
            
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "operation": "stream_workflow",
                    "user_question": initial_state.get("user_question", ""),
                    "conversation_id": initial_state.get("metadata", {}).get("conversation_id")
                }
            )
            
            # 发送错误块
            yield {
                "node": "error",
                "output": {
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            }
    
    def _process_stream_chunk(self, chunk: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        处理流式输出块
        
        Args:
            chunk: 原始输出块
            
        Returns:
            Optional[Dict[str, Any]]: 处理后的输出块
        """
        try:
            # LangGraph的输出格式通常是 {node_name: state}
            if isinstance(chunk, dict) and len(chunk) == 1:
                node_name, state = next(iter(chunk.items()))
                
                # 提取有用的输出信息
                output = {}
                
                if "agent_outputs" in state and node_name in state["agent_outputs"]:
                    output = state["agent_outputs"][node_name].get("output", {})
                
                # 添加状态信息
                output.update({
                    "current_stage": state.get("current_stage", ""),
                    "execution_path": state.get("execution_path", []),
                    "final_answer": state.get("final_answer", "")
                })
                
                return {
                    "node": node_name,
                    "output": output
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"处理流式输出块失败: {str(e)}")
            return None
    
    async def get_final_state(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取最终状态
        
        Args:
            config: 配置参数
            
        Returns:
            Dict[str, Any]: 最终状态
        """
        try:
            # 这里需要根据实际的LangGraph API来实现
            # 由于我们使用自定义检查点存储，可能需要不同的实现方式
            
            thread_id = config.get("configurable", {}).get("thread_id")
            if thread_id and hasattr(self.checkpointer, 'get_latest_checkpoint'):
                if asyncio.iscoroutinefunction(self.checkpointer.get_latest_checkpoint):
                    latest = await self.checkpointer.get_latest_checkpoint(thread_id)
                else:
                    latest = self.checkpointer.get_latest_checkpoint(thread_id)
                
                if latest:
                    _, checkpoint_data = latest
                    return checkpoint_data.get("state", {})
            
            return {}
            
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "operation": "get_final_state",
                    "config": config
                }
            )
            return {}
    
    async def save_checkpoint(
        self,
        thread_id: str,
        checkpoint_id: str,
        state: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        保存检查点
        
        Args:
            thread_id: 线程ID
            checkpoint_id: 检查点ID
            state: 状态数据
            metadata: 元数据
            
        Returns:
            bool: 是否保存成功
        """
        try:
            if hasattr(self.checkpointer, 'save_checkpoint'):
                if asyncio.iscoroutinefunction(self.checkpointer.save_checkpoint):
                    return await self.checkpointer.save_checkpoint(
                        thread_id, checkpoint_id, state, metadata
                    )
                else:
                    return self.checkpointer.save_checkpoint(
                        thread_id, checkpoint_id, state, metadata
                    )
            
            return False
            
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "operation": "save_checkpoint",
                    "thread_id": thread_id,
                    "checkpoint_id": checkpoint_id
                }
            )
            return False
    
    async def load_checkpoint(
        self,
        thread_id: str,
        checkpoint_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        加载检查点
        
        Args:
            thread_id: 线程ID
            checkpoint_id: 检查点ID
            
        Returns:
            Optional[Dict[str, Any]]: 检查点数据
        """
        try:
            if hasattr(self.checkpointer, 'load_checkpoint'):
                if asyncio.iscoroutinefunction(self.checkpointer.load_checkpoint):
                    return await self.checkpointer.load_checkpoint(thread_id, checkpoint_id)
                else:
                    return self.checkpointer.load_checkpoint(thread_id, checkpoint_id)
            
            return None
            
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "operation": "load_checkpoint",
                    "thread_id": thread_id,
                    "checkpoint_id": checkpoint_id
                }
            )
            return None
    
    async def close(self):
        """关闭资源"""
        try:
            # 关闭服务连接
            if hasattr(self.node_definitions, 'llm_service'):
                await self.node_definitions.llm_service.close()
            if hasattr(self.node_definitions, 'knowledge_service'):
                await self.node_definitions.knowledge_service.close()
            if hasattr(self.node_definitions, 'lightrag_service'):
                await self.node_definitions.lightrag_service.close()
            if hasattr(self.node_definitions, 'search_service'):
                await self.node_definitions.search_service.close()
            
            # 关闭检查点存储器
            if hasattr(self.checkpointer, 'close'):
                if asyncio.iscoroutinefunction(self.checkpointer.close):
                    await self.checkpointer.close()
                else:
                    self.checkpointer.close()
            
            self.logger.info("LangGraph管理器资源已关闭")
            
        except Exception as e:
            self.logger.error(f"关闭资源失败: {str(e)}")
