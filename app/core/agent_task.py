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
        self.update_stage("analyzing_question")
        self.current_agent = "QuestionAnalyzer"
        await self.emit_status("analyzing_question", progress=0.1)
        
        user_question = self.global_context.user_question
        
        # 构建知识库描述
        kb_info = ""
        if self.knowledge_bases:
            kb_list = []
            for kb in self.knowledge_bases:
                kb_list.append(f"- {kb.get('name', '未知')}: {kb.get('description', '无描述')}")
            kb_info = "\n\n可用知识库：\n" + "\n".join(kb_list)
        else:
            kb_info = "\n\n注意：未配置特定知识库，将使用默认检索策略"
        
        # 构建问题分析提示
        analyze_prompt = f"""
        作为一个智能问答助手，我需要深入理解用户的问题。
        
        用户问题：{user_question}
        {kb_info}
        
        请分析这个问题的：
        1. 核心意图是什么？
        2. 问题的复杂程度如何？
        3. 需要哪些类型的信息来回答？
        4. 是否需要实时信息？
        5. 问题的关键词和概念
        6. 应该使用哪些知识库？
        
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
        
        await self.emit_status("analyzing_question", status="completed", progress=0.25)
    
    async def _agent_stage_plan_tasks(self) -> None:
        """Agent阶段2：任务规划"""
        self.update_stage("task_scheduling")
        self.current_agent = "TaskPlanner"
        await self.emit_status("task_scheduling", progress=0.3)
        
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
        
        # 如果有知识库配置，输出知识库选择信息
        if self.knowledge_bases:
            await self.emit_content("\n📚 系统将基于问题内容智能选择最相关的知识库")
        
        # 使用流式响应进行任务规划
        planning_result = await self._generate_with_stream(
            plan_prompt,
            temperature=0.4,
            stage_name="任务规划"
        )
        
        # 保存规划结果
        self.global_context.task_plan = planning_result
        
        await self.emit_status("task_scheduling", status="completed", progress=0.5)
    
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
        self.update_stage("response_generation")
        self.current_agent = "ResultIntegrator"
        await self.emit_status("response_generation", progress=0.9)
        
        # 构建检索结果的详细上下文
        results_context = self._build_results_context()
        history_context = self._build_history_context()
        
        # 构建结果整合提示
        integrate_prompt = f"""
        基于检索到的信息，为用户提供全面准确的回答。
        
        用户原始问题：{self.global_context.user_question}
        
        问题分析结果：
        {self.global_context.question_analysis}
        
        检索结果：
        {results_context}
        
        对话历史：
        {history_context}
        
        基于检索到的信息和分析结果，请提供一个全面、深入、有洞察力的回答。
        
        **回答框架**：
        
        1. **直接回答**（开门见山）：
           - 先用1-2句话直接回答用户的核心问题
           - 然后展开详细说明，层层深入
        
        2. **信息整合与分析**（主体部分）：
           - 综合多个来源的信息，构建完整知识体系
           - 分析不同信息之间的关联、互补或矛盾
           - 提供多维度的视角（如理论与实践、优势与局限等）
           - 适当加入背景知识帮助理解
        
        3. **深入探讨**（根据问题类型扩展）：
           - 原理机制：解释事物运作的底层逻辑
           - 比较分析：对比不同方案或观点的异同
           - 案例说明：用具体例子说明抽象概念
           - 趋势洞察：分析当前状况和未来可能
           - 实践建议：提供可操作的指导意见
        
        4. **引用规范**（严格执行）：
           - 在陈述具体事实或数据时标注[1]、[2]等
           - 引用编号必须与检索结果编号对应
           - 在回答末尾设置"**参考来源：**"专区
           - 格式：[编号] 来源类型 - "标题" - 内容摘要（在线搜索需包含URL）
        
        5. **总结与延伸**（画龙点睛）：
           - **核心要点**：用bullet points总结2-3个关键信息
           - **思考延伸**：提出1-2个值得进一步探讨的问题
           - **知识边界**：诚实说明哪些方面信息有限
           - **行动建议**：如适用，给出下一步建议
        
        **写作原则**：
        - 结构清晰：善用小标题、编号、段落划分
        - 深浅结合：专业分析配合通俗解释
        - 论据充分：每个观点都有依据支撑
        - 思维开放：展现多元视角，避免绝对化表述
        - 价值导向：不仅回答"是什么"，更探讨"为什么"和"怎么办"
        
        **红线要求**：
        - 所有信息必须来自检索结果，不得凭空创造
        - URL必须是检索结果中的真实链接
        - 遇到信息冲突时明确指出并分析可能原因
        - 保持学术诚信和批判性思维
        
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
                "stages": ["understanding", "planning", "executing", "integrating"],
                "search_types_used": list(self.task_results.keys()),
                "total_results": sum(len(r.get("results", [])) for r in self.task_results.values() if isinstance(r, dict))
            }
        )
        self.history.add_message(assistant_message)
        
        await self.emit_content("\n✅ **任务完成**")
        await self.emit_status("response_generation", status="completed", progress=1.0)
        
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
                self.update_stage("agent_workflow")
                
                # 记录执行步骤
                step = {
                    "agent": node_name,
                    "timestamp": datetime.now().isoformat(),
                    "output": node_output
                }
                self.execution_steps.append(step)
                
                # 发送状态更新
                await self.emit_status(
                    "agent_workflow",
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
            await self.emit_content("\n📊 **并行检索结果：**")
            
            # 定义任务类型的中文名称
            type_names = {
                "online_search": "在线搜索",
                "knowledge_search": "知识库检索", 
                "lightrag_search": "知识图谱"
            }
            
            success_count = 0
            total_count = len(search_results)
            
            for search_type, results in search_results.items():
                type_name = type_names.get(search_type, search_type)
                
                # 检查是否有错误
                if isinstance(results, dict) and "error" in results:
                    await self.emit_content(f"\n❌ **{type_name}** - 检索失败")
                    await self.emit_content(f"   错误信息: {results.get('error', '未知错误')}")
                    self.logger.error(f"Agent模式 - {search_type} 检索失败: {results.get('error')}")
                else:
                    # 计算结果数量
                    if isinstance(results, list):
                        result_count = len(results)
                    elif isinstance(results, dict) and "results" in results:
                        result_count = len(results.get("results", []))
                    else:
                        result_count = 0
                    
                    if result_count > 0:
                        await self.emit_content(f"\n✅ **{type_name}** - 检索成功")
                        await self.emit_content(f"   获得 {result_count} 个结果")
                        success_count += 1
                        self.logger.info(f"Agent模式 - {search_type} 检索成功，获得 {result_count} 个结果")
                    else:
                        # 虽然技术上成功了，但没有找到结果
                        await self.emit_content(f"\n⚠️ **{type_name}** - 未找到相关结果")
                        self.logger.warning(f"Agent模式 - {search_type} 返回了空结果")
            
            # 总结反馈
            await self.emit_content(f"\n📈 **检索总结：**")
            await self.emit_content(f"- 成功: {success_count}/{total_count} 个任务")
            await self.emit_content(f"- 失败: {total_count - success_count}/{total_count} 个任务")
    
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
                "completed",
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
    
    def _use_default_task_config(self) -> None:
        """使用默认任务配置"""
        default_query = self.global_context.user_question or "默认查询"
        self.planned_tasks = [
            TaskConfig(type="online_search", query=default_query),
            TaskConfig(type="knowledge_search", query=default_query),
            TaskConfig(type="lightrag_search", query=default_query)
        ]
    
    async def _execute_online_search(self, query: str) -> Dict[str, Any]:
        """执行在线搜索"""
        try:
            self.logger.info(f"Agent模式 - 开始执行在线搜索: {query}")
            results = await self.search_service.search_online(query)
            self.logger.info(f"Agent模式 - 在线搜索成功，获得 {len(results)} 个结果")
            return {"type": "online_search", "query": query, "results": results}
        except Exception as e:
            error_msg = f"在线搜索失败: {str(e)}"
            self.logger.error(f"Agent模式 - {error_msg}")
            return {"type": "online_search", "query": query, "error": error_msg}
    
    async def _execute_knowledge_search(self, query: str) -> Dict[str, Any]:
        """执行知识库搜索"""
        try:
            self.logger.info(f"Agent模式 - 开始执行知识库搜索: {query}")
            
            # 如果有用户token，使用新的query_doc_by_name方法
            if hasattr(self, 'user_token') and self.user_token:
                knowledge_base_name = "test"  # 默认知识库名称
                self.logger.info(f"Agent模式 - 使用query_doc_by_name方法，知识库名称: {knowledge_base_name}")
                results = await self.knowledge_service.query_doc_by_name(
                    token=self.user_token,
                    knowledge_base_name=knowledge_base_name,
                    query=query,
                    k=5,
                    api_url=self.knowledge_api_url
                )
                self.logger.info(f"Agent模式 - 知识库搜索成功 (query_doc_by_name)")
                return {"type": "knowledge_search", "query": query, "results": results}
            else:
                # 使用原有的方法
                self.logger.info(f"Agent模式 - 使用search_cosmetics_knowledge方法")
                results = await self.knowledge_service.search_cosmetics_knowledge(
                    query=query,
                    api_url=self.knowledge_api_url
                )
                result_count = len(results) if isinstance(results, list) else 0
                self.logger.info(f"Agent模式 - 知识库搜索成功，获得 {result_count} 个结果")
                return {"type": "knowledge_search", "query": query, "results": results}
        except Exception as e:
            error_msg = f"知识库搜索失败: {str(e)}"
            self.logger.error(f"Agent模式 - {error_msg}")
            return {"type": "knowledge_search", "query": query, "error": error_msg}
    
    async def _execute_lightrag_search(self, query: str) -> Dict[str, Any]:
        """执行LightRAG搜索"""
        try:
            self.logger.info(f"Agent模式 - 开始执行LightRAG搜索: {query}")
            results = await self.lightrag_service.search_lightrag(query, mode="mix")
            self.logger.info(f"Agent模式 - LightRAG搜索成功，获得 {len(results)} 个结果")
            return {"type": "lightrag_search", "query": query, "results": results}
        except Exception as e:
            # 更安全的异常消息提取，避免访问不存在的键
            try:
                error_msg = f"LightRAG搜索失败: {str(e)}"
            except Exception as str_error:
                # 如果str(e)失败，提供备用错误消息
                error_msg = f"LightRAG搜索失败: {type(e).__name__}异常，详情: {repr(e)}"
            
            self.logger.error(f"Agent模式 - {error_msg}")
            return {"type": "lightrag_search", "query": query, "error": error_msg}
    
    def _build_execution_summary(self) -> str:
        """构建执行结果摘要"""
        summary_parts = []
        
        for task_type, result in self.task_results.items():
            if "error" in result:
                summary_parts.append(f"{task_type}: 检索失败 - {result['error']}")
            else:
                # 统计结果数量
                if "results" in result and isinstance(result["results"], list):
                    count = len(result["results"])
                    summary_parts.append(f"{task_type}: 成功获取 {count} 个结果")
                    
                    # 提取关键信息
                    key_info = []
                    for item in result["results"][:3]:  # 只取前3个
                        if hasattr(item, 'title') and hasattr(item, 'content'):
                            content_preview = item.content[:100] + "..." if len(item.content) > 100 else item.content
                            key_info.append(f"  - {item.title}: {content_preview}")
                    
                    if key_info:
                        summary_parts.extend(key_info)
        
        return "\n\n".join(summary_parts)
    
    def _make_serializable(self, obj: Any) -> Any:
        """将对象转换为可序列化的格式"""
        if isinstance(obj, SearchResult):
            return obj.to_dict()
        elif isinstance(obj, list):
            return [self._make_serializable(item) for item in obj]
        elif isinstance(obj, dict):
            return {key: self._make_serializable(value) for key, value in obj.items()}
        else:
            return obj
    
    def _build_results_context(self) -> str:
        """构建检索结果上下文（优化格式以便引用）"""
        context_parts = []
        
        # 定义任务类型的中文名称
        type_names = {
            "online_search": "在线搜索",
            "knowledge_search": "知识库检索", 
            "lightrag_search": "知识图谱"
        }
        
        # 全局引用计数器
        ref_counter = 1
        
        for task_type, result in self.task_results.items():
            type_name = type_names.get(task_type, task_type)
            
            if "error" in result:
                context_parts.append(f"\n【{type_name}】\n状态：检索失败\n错误信息：{result['error']}\n")
            else:
                context_parts.append(f"\n【{type_name}】")
                context_parts.append(f"查询：{result.get('query', '未知')}")
                
                if "results" in result and isinstance(result["results"], list):
                    context_parts.append(f"结果数量：{len(result['results'])}个\n")
                    
                    # 格式化每个结果，便于引用
                    for item in result["results"]:
                        if hasattr(item, 'to_dict'):
                            item_dict = item.to_dict()
                        else:
                            item_dict = item if isinstance(item, dict) else {}
                        
                        # 使用全局引用编号
                        context_parts.append(f"[{ref_counter}] {type_name}结果:")
                        context_parts.append(f"  标题：{item_dict.get('title', '无标题')}")
                        
                        # 限制内容长度
                        content = item_dict.get('content', '无内容')
                        if len(content) > 300:
                            content = content[:300] + "..."
                        context_parts.append(f"  内容：{content}")
                        
                        # 特别标注URL信息（在线搜索必须有URL）
                        url = item_dict.get('url', '')
                        if url:
                            context_parts.append(f"  **URL：{url}**")
                        elif task_type == "online_search":
                            context_parts.append(f"  URL：无（搜索结果未提供链接）")
                        
                        # 添加来源信息
                        if item_dict.get('source'):
                            context_parts.append(f"  来源类型：{item_dict['source']}")
                        
                        # 添加元数据中的重要信息
                        metadata = item_dict.get('metadata', {})
                        if metadata.get('engine'):
                            context_parts.append(f"  搜索引擎：{metadata['engine']}")
                        if metadata.get('publishedDate'):
                            context_parts.append(f"  发布时间：{metadata['publishedDate']}")
                        
                        context_parts.append("")  # 空行分隔
                        ref_counter += 1
        
        return "\n".join(context_parts) if context_parts else "无检索结果"
    
    def _build_history_context(self) -> str:
        """构建历史对话上下文"""
        recent_messages = self.history.get_recent_messages(limit=5)
        context_parts = []
        
        for msg in recent_messages:
            context_parts.append(f"{msg.role}: {msg.content}")
        
        return "\n".join(context_parts) if context_parts else "无历史对话"
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """获取执行摘要"""
        return {
            **self.get_conversation_summary(),
            "agent_mode": True,
            "current_agent": self.current_agent,
            "execution_steps": len(self.execution_steps),
            "agents_used": list(set(step["agent"] for step in self.execution_steps)),
            "global_context_summary": self.global_context.get_all_contexts_summary(),
            "task_results_summary": {
                task_type: {
                    "has_error": "error" in result,
                    "result_count": len(result.get("results", [])) if "results" in result else 0
                }
                for task_type, result in self.task_results.items()
            }
        }
