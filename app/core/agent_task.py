"""
Agent任务类模块

实现基于LangGraph的智能代理对话任务。
"""

from typing import Dict, List, Optional, Any, AsyncIterator
from datetime import datetime

from .base_task import BaseConversationTask
from ..models import Message, GlobalContext
from ..langgraph import LangGraphManager
from ..config import get_logger


class AgentTask(BaseConversationTask):
    """智能代理对话任务"""
    
    def __init__(self, user_id: str, conversation_id: Optional[str] = None):
        """初始化Agent任务"""
        super().__init__(user_id, conversation_id, mode="agent")
        
        # 初始化LangGraph管理器
        self.langgraph_manager = LangGraphManager()
        
        # 全局上下文
        self.global_context = GlobalContext()
        
        # Agent执行状态
        self.current_agent = ""
        self.execution_steps: List[Dict[str, Any]] = []
    
    async def execute(self) -> None:
        """执行Agent工作流的主要逻辑"""
        try:
            # 获取用户最新问题
            user_messages = self.history.get_messages_by_role("user")
            if not user_messages:
                raise ValueError("没有找到用户问题")
            
            user_question = user_messages[-1].content
            
            # 初始化全局上下文
            self.global_context.user_question = user_question
            self.global_context.conversation_history = self.history.messages
            
            # 执行LangGraph工作流
            await self._execute_agent_workflow()
            
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "conversation_id": self.conversation_id,
                    "current_agent": self.current_agent,
                    "user_id": self.user_id
                }
            )
            raise
    
    async def _execute_agent_workflow(self) -> None:
        """执行Agent工作流"""
        self.update_stage("agent_workflow")
        await self.emit_status("agent_workflow", progress=0.1)
        await self.emit_content("启动智能代理工作流...")
        
        # 准备LangGraph状态
        initial_state = {
            "user_question": self.global_context.user_question,
            "conversation_history": [msg.to_dict() for msg in self.global_context.conversation_history],
            "online_search_results": [],
            "knowledge_search_results": [],
            "lightrag_results": [],
            "current_stage": "master_agent",
            "final_answer": "",
            "metadata": {
                "conversation_id": self.conversation_id,
                "user_id": self.user_id,
                "start_time": datetime.now().isoformat()
            }
        }
        
        # 执行LangGraph工作流
        config = {
            "configurable": {
                "thread_id": self.conversation_id,
                "checkpoint_ns": f"agent_task_{self.conversation_id}"
            }
        }
        
        try:
            # 流式执行LangGraph
            async for chunk in self.langgraph_manager.stream_workflow(initial_state, config):
                await self._process_langgraph_chunk(chunk)
            
            # 获取最终状态
            final_state = await self.langgraph_manager.get_final_state(config)
            await self._process_final_result(final_state)
            
        except Exception as e:
            self.logger.error(f"LangGraph执行失败: {str(e)}")
            await self.emit_error(
                error_code="LANGGRAPH_ERROR",
                error_message=f"智能代理执行失败: {str(e)}"
            )
            raise
    
    async def _process_langgraph_chunk(self, chunk: Dict[str, Any]) -> None:
        """处理LangGraph流式输出块"""
        try:
            # 解析chunk内容
            node_name = chunk.get("node", "")
            node_output = chunk.get("output", {})
            
            if node_name:
                self.current_agent = node_name
                self.update_stage(f"agent_{node_name}")
                
                # 记录执行步骤
                step = {
                    "agent": node_name,
                    "timestamp": datetime.now().isoformat(),
                    "output": node_output
                }
                self.execution_steps.append(step)
                
                # 发送状态更新
                await self.emit_status(
                    f"agent_{node_name}",
                    agent_name=node_name,
                    metadata={"step_count": len(self.execution_steps)}
                )
                
                # 处理不同Agent的输出
                await self._handle_agent_output(node_name, node_output)
                
        except Exception as e:
            self.logger.error(f"处理LangGraph chunk失败: {str(e)}")
    
    async def _handle_agent_output(self, agent_name: str, output: Dict[str, Any]) -> None:
        """处理特定Agent的输出"""
        try:
            if agent_name == "master_agent":
                await self._handle_master_agent_output(output)
            elif agent_name == "query_optimizer":
                await self._handle_query_optimizer_output(output)
            elif agent_name == "parallel_search":
                await self._handle_parallel_search_output(output)
            elif agent_name == "summary_agent":
                await self._handle_summary_agent_output(output)
            elif agent_name == "final_output":
                await self._handle_final_output_output(output)
            
        except Exception as e:
            self.logger.error(f"处理Agent {agent_name} 输出失败: {str(e)}")
    
    async def _handle_master_agent_output(self, output: Dict[str, Any]) -> None:
        """处理总控制者Agent输出"""
        decision = output.get("decision", "")
        reasoning = output.get("reasoning", "")
        
        if reasoning:
            await self.emit_content(f"🤖 总控制者分析: {reasoning}")
        
        if decision == "continue":
            await self.emit_content("需要收集更多信息，启动检索流程...")
        elif decision == "finish":
            await self.emit_content("信息充足，准备生成最终回答...")
    
    async def _handle_query_optimizer_output(self, output: Dict[str, Any]) -> None:
        """处理问题优化Agent输出"""
        optimized_queries = output.get("optimized_queries", {})
        
        if optimized_queries:
            await self.emit_content("🔍 问题优化完成，生成专门化查询:")
            for agent_type, query in optimized_queries.items():
                await self.emit_content(f"  • {agent_type}: {query}")
    
    async def _handle_parallel_search_output(self, output: Dict[str, Any]) -> None:
        """处理并行搜索输出"""
        search_results = output.get("search_results", {})
        
        if search_results:
            await self.emit_content("📊 并行检索完成:")
            for search_type, results in search_results.items():
                result_count = len(results) if isinstance(results, list) else 1
                await self.emit_content(f"  • {search_type}: 获得 {result_count} 个结果")
    
    async def _handle_summary_agent_output(self, output: Dict[str, Any]) -> None:
        """处理摘要Agent输出"""
        summaries = output.get("summaries", {})
        
        if summaries:
            await self.emit_content("📝 信息摘要生成完成:")
            for source, summary in summaries.items():
                if summary:
                    await self.emit_content(f"  • {source}: {summary[:100]}...")
    
    async def _handle_final_output_output(self, output: Dict[str, Any]) -> None:
        """处理最终输出Agent输出"""
        final_answer = output.get("final_answer", "")
        
        if final_answer:
            # 添加助手回答到历史
            assistant_message = Message(
                role="assistant",
                content=final_answer,
                metadata={
                    "agent_mode": True,
                    "execution_steps": len(self.execution_steps),
                    "agents_used": list(set(step["agent"] for step in self.execution_steps))
                }
            )
            self.add_message(assistant_message)
            
            await self.emit_content(final_answer)
    
    async def _process_final_result(self, final_state: Dict[str, Any]) -> None:
        """处理最终结果"""
        try:
            final_answer = final_state.get("final_answer", "")
            
            if final_answer and not any(msg.role == "assistant" for msg in self.history.messages[-1:]):
                # 如果还没有添加最终回答，则添加
                assistant_message = Message(
                    role="assistant",
                    content=final_answer,
                    metadata={
                        "agent_mode": True,
                        "final_state": True,
                        "execution_steps": len(self.execution_steps)
                    }
                )
                self.add_message(assistant_message)
            
            await self.emit_status("agent_workflow", status="completed", progress=1.0)
            
            self.logger.info(
                "Agent工作流执行完成",
                conversation_id=self.conversation_id,
                execution_steps=len(self.execution_steps),
                final_answer_length=len(final_answer)
            )
            
        except Exception as e:
            self.logger.error(f"处理最终结果失败: {str(e)}")
            await self.emit_error(
                error_code="FINAL_RESULT_ERROR",
                error_message=f"处理最终结果失败: {str(e)}"
            )
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """获取执行摘要"""
        return {
            **self.get_conversation_summary(),
            "agent_mode": True,
            "current_agent": self.current_agent,
            "execution_steps": len(self.execution_steps),
            "agents_used": list(set(step["agent"] for step in self.execution_steps)),
            "global_context_summary": self.global_context.get_all_contexts_summary()
        }
