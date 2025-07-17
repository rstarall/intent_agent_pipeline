"""
Agent任务类模块

实现基于LangGraph的智能代理对话任务，支持流式响应。
"""

from typing import Dict, List, Optional, Any, AsyncIterator
from datetime import datetime

from .base_task import BaseConversationTask
from ..models import Message, GlobalContext
from ..langgraph import LangGraphManager
from ..services import LLMService
from ..config import get_logger


class AgentTask(BaseConversationTask):
    """智能代理对话任务（支持流式响应）"""
    
    def __init__(self, user_id: str, conversation_id: Optional[str] = None):
        """初始化Agent任务"""
        super().__init__(user_id, conversation_id, mode="agent")
        
        # 初始化服务
        self.llm_service = LLMService()
        
        # 初始化LangGraph管理器
        self.langgraph_manager = LangGraphManager()
        
        # 全局上下文
        self.global_context = GlobalContext()
        
        # Agent执行状态
        self.current_agent = ""
        self.execution_steps: List[Dict[str, Any]] = []
        
        # Workflow完成状态标识
        self.workflow_completed = False
        self.final_answer_sent = False
    
    async def _generate_with_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_message: Optional[str] = None,
        stage_name: str = ""
    ) -> str:
        """
        使用流式响应生成LLM回复，同时收集完整响应用于后续处理
        
        Args:
            prompt: 提示词
            temperature: 温度参数
            max_tokens: 最大令牌数
            system_message: 系统消息
            stage_name: 阶段名称（用于日志）
            
        Returns:
            完整的LLM响应内容
        """
        full_response = ""
        
        self.logger.info(f"开始{stage_name}流式响应", conversation_id=self.conversation_id)
        
        # 使用流式响应
        async for chunk in self.llm_service.generate_stream_response(
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            system_message=system_message,
            conversation_history=self.history.get_recent_messages(limit=5)
        ):
            # 实时发送内容片段给用户
            await self.emit_content(chunk)
            
            # 收集完整响应
            full_response += chunk
        
        self.logger.info(f"完成{stage_name}流式响应", 
                        conversation_id=self.conversation_id,
                        response_length=len(full_response))
        
        return full_response
    
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
            
            # 执行LangGraph工作流（流式版本）
            await self._execute_agent_workflow_with_stream()
            
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "conversation_id": self.conversation_id,
                    "current_agent": self.current_agent,
                    "user_id": self.user_id
                }
            )
            await self.emit_error("AGENT_EXECUTION_ERROR", f"Agent执行错误: {str(e)}")
            raise
    
    async def _execute_agent_workflow_with_stream(self) -> None:
        """执行Agent工作流（流式版本）"""
        try:
            # 阶段1：问题理解与分析
            await self._agent_stage_understand_question()
            
            # 阶段2：任务规划
            await self._agent_stage_plan_tasks()
            
            # 阶段3：执行任务
            await self._agent_stage_execute_tasks()
            
            # 阶段4：结果整合
            await self._agent_stage_integrate_results()
            
        except Exception as e:
            self.logger.error_with_context(e, {"stage": "agent_workflow"})
            raise
    
    async def _agent_stage_understand_question(self) -> None:
        """Agent阶段1：问题理解与分析"""
        self.update_stage("understanding_question")
        self.current_agent = "QuestionAnalyzer"
        await self.emit_status("understanding_question", progress=0.1)
        
        user_question = self.global_context.user_question
        
        # 构建问题分析提示
        analyze_prompt = f"""
        作为一个智能问答助手，我需要深入理解用户的问题。
        
        用户问题：{user_question}
        
        请分析这个问题的：
        1. 核心意图是什么？
        2. 问题的复杂程度如何？
        3. 需要哪些类型的信息来回答？
        4. 是否需要实时信息？
        5. 问题的关键词和概念
        
        请提供详细的分析思路：
        """
        
        await self.emit_content("🤖 **QuestionAnalyzer**: 正在分析问题...")
        
        # 使用流式响应进行问题分析
        analysis_result = await self._generate_with_stream(
            analyze_prompt,
            temperature=0.3,
            stage_name="问题分析"
        )
        
        # 保存分析结果到全局上下文
        self.global_context.question_analysis = analysis_result
        
        await self.emit_status("understanding_question", status="completed", progress=0.25)
    
    async def _agent_stage_plan_tasks(self) -> None:
        """Agent阶段2：任务规划"""
        self.update_stage("planning_tasks")
        self.current_agent = "TaskPlanner"
        await self.emit_status("planning_tasks", progress=0.3)
        
        # 构建任务规划提示
        plan_prompt = f"""
        基于问题分析，制定解决方案。
        
        问题分析结果：
        {self.global_context.question_analysis}
        
        请制定一个详细的执行计划：
        1. 需要执行哪些具体任务？
        2. 任务的优先级和依赖关系？
        3. 每个任务的预期输出？
        4. 整体的解决思路？
        
        请详细说明执行策略：
        """
        
        await self.emit_content("\n🗂️ **TaskPlanner**: 正在制定执行计划...")
        
        # 使用流式响应进行任务规划
        planning_result = await self._generate_with_stream(
            plan_prompt,
            temperature=0.4,
            stage_name="任务规划"
        )
        
        # 保存规划结果
        self.global_context.task_plan = planning_result
        
        await self.emit_status("planning_tasks", status="completed", progress=0.5)
    
    async def _agent_stage_execute_tasks(self) -> None:
        """Agent阶段3：执行任务"""
        self.update_stage("executing_tasks")
        self.current_agent = "TaskExecutor"
        await self.emit_status("executing_tasks", progress=0.6)
        
        # 构建任务执行提示
        execute_prompt = f"""
        现在开始执行任务。
        
        原始问题：{self.global_context.user_question}
        问题分析：{self.global_context.question_analysis}
        执行计划：{self.global_context.task_plan}
        
        请按照计划执行任务，并提供：
        1. 每个任务的执行过程
        2. 发现的关键信息
        3. 遇到的问题和解决方案
        4. 中间结果和思考过程
        
        请详细展示执行过程：
        """
        
        await self.emit_content("\n⚙️ **TaskExecutor**: 正在执行任务...")
        
        # 使用流式响应执行任务
        execution_result = await self._generate_with_stream(
            execute_prompt,
            temperature=0.6,
            stage_name="任务执行"
        )
        
        # 保存执行结果
        self.global_context.execution_results = execution_result
        
        await self.emit_status("executing_tasks", status="completed", progress=0.8)
    
    async def _agent_stage_integrate_results(self) -> None:
        """Agent阶段4：结果整合"""
        self.update_stage("integrating_results")
        self.current_agent = "ResultIntegrator"
        await self.emit_status("integrating_results", progress=0.9)
        
        # 构建结果整合提示
        integrate_prompt = f"""
        现在需要整合所有信息，为用户提供最终答案。
        
        原始问题：{self.global_context.user_question}
        问题分析：{self.global_context.question_analysis}
        执行计划：{self.global_context.task_plan}
        执行结果：{self.global_context.execution_results}
        
        请基于以上信息，生成一个：
        1. 直接回答用户问题的答案
        2. 逻辑清晰、结构完整
        3. 包含必要的解释和依据
        4. 如果信息不足，请明确说明
        
        最终答案：
        """
        
        await self.emit_content("\n🔄 **ResultIntegrator**: 正在整合结果...")
        
        # 使用流式响应生成最终答案
        final_answer = await self._generate_with_stream(
            integrate_prompt,
            temperature=0.7,
            stage_name="结果整合"
        )
        
        # 保存最终答案
        self.global_context.final_answer = final_answer
        
        # 添加到历史记录
        assistant_message = Message(
            role="assistant",
            content=final_answer,
            metadata={
                "mode": "agent",
                "stages": ["understanding", "planning", "executing", "integrating"]
            }
        )
        self.history.add_message(assistant_message)
        
        await self.emit_content("\n✅ **任务完成**")
        await self.emit_status("integrating_results", status="completed", progress=1.0)
        
        self.workflow_completed = True
        self.final_answer_sent = True
    
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
        
        if final_answer and not self.final_answer_sent:
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
            
            # 发送最终答案
            await self.emit_content(final_answer)
            self.final_answer_sent = True
            
            # 标记workflow完成
            self.workflow_completed = True
            
            # 发送完成状态
            await self.emit_status(
                "final_output_completed",
                status="completed", 
                progress=1.0,
                metadata={
                    "final_answer_length": len(final_answer),
                    "total_steps": len(self.execution_steps)
                }
            )
    
    async def _process_final_result(self, final_state: Dict[str, Any]) -> None:
        """处理最终结果"""
        try:
            final_answer = final_state.get("final_answer", "")
            
            # 如果还没有发送最终答案，则处理
            if final_answer and not self.final_answer_sent:
                # 添加助手回答到历史
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
                
                # 发送最终答案
                await self.emit_content(final_answer)
                self.final_answer_sent = True
            
            # 标记workflow完成
            self.workflow_completed = True
            
            # 发送最终完成状态
            await self.emit_status(
                "agent_workflow", 
                status="completed", 
                progress=1.0,
                metadata={
                    "workflow_completed": True,
                    "final_answer_length": len(final_answer),
                    "total_execution_steps": len(self.execution_steps)
                }
            )
            
            self.logger.info(
                "Agent工作流执行完成",
                conversation_id=self.conversation_id,
                execution_steps=len(self.execution_steps),
                final_answer_length=len(final_answer),
                workflow_completed=self.workflow_completed
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
