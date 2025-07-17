"""
工作流任务类模块

实现固定流程的多轮对话任务，包含4个阶段的执行流程。
"""

import json
import asyncio
from typing import Dict, List, Optional, Any

from .base_task import BaseConversationTask
from ..models import Message, ParallelTasksConfig, TaskConfig, SearchResult
from ..services import (
    KnowledgeService, LightRagService, SearchService, LLMService
)


class WorkflowTask(BaseConversationTask):
    """固定工作流对话任务"""
    
    def __init__(self, user_id: str, conversation_id: Optional[str] = None):
        """初始化工作流任务"""
        super().__init__(user_id, conversation_id, mode="workflow")
        
        # 初始化服务
        self.knowledge_service = KnowledgeService()
        self.lightrag_service = LightRagService()
        self.search_service = SearchService()
        self.llm_service = LLMService()
        
        # 工作流状态
        self.optimized_question = ""
        self.parallel_tasks_config: Optional[ParallelTasksConfig] = None
        self.task_results: Dict[str, Any] = {}
        self.final_answer = ""
    
    async def execute(self) -> None:
        """执行工作流的主要逻辑"""
        try:
            # 获取用户最新问题
            user_messages = self.history.get_messages_by_role("user")
            if not user_messages:
                await self.emit_error("NO_USER_MESSAGE", "没有找到用户问题")
                return
            
            user_question = user_messages[-1].content
            
            # 阶段1：问题分析与规划
            await self._stage_1_analyze_question(user_question)
            
            # 阶段2：任务分解与调度
            await self._stage_2_task_scheduling()
            
            # 阶段3：并行任务执行
            await self._stage_3_execute_tasks()
            
            # 阶段4：结果整合与回答
            await self._stage_4_generate_answer(user_question)
            
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "conversation_id": self.conversation_id,
                    "stage": self.current_stage,
                    "user_id": self.user_id
                }
            )
            await self.emit_error("WORKFLOW_ERROR", f"工作流执行错误: {str(e)}")
            raise
    
    async def _generate_with_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_message: Optional[str] = None,
        content_prefix: str = ""
    ) -> str:
        """
        使用流式响应生成LLM回复，同时收集完整响应用于后续处理
        
        Args:
            prompt: 提示词
            temperature: 温度参数
            max_tokens: 最大令牌数
            system_message: 系统消息
            content_prefix: 内容前缀（用于区分不同阶段）
            
        Returns:
            完整的LLM响应内容
        """
        full_response = ""
        
        # 使用流式响应
        async for chunk in self.llm_service.generate_stream_response(
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            system_message=system_message,
            conversation_history=self.history.get_recent_messages(limit=5)
        ):
            # 实时发送内容片段给用户
            if content_prefix:
                await self.emit_content(f"{content_prefix}{chunk}")
            else:
                await self.emit_content(chunk)
            
            # 收集完整响应
            full_response += chunk
        
        return full_response
    
    async def _stage_1_analyze_question(self, user_question: str) -> None:
        """阶段1：问题分析与规划（流式版本）"""
        self.update_stage("analyzing_question")
        await self.emit_status("analyzing_question", progress=0.1)
        await self.emit_content("正在分析您的问题...")
        
        # 构建分析提示
        history_context = self._build_history_context()
        
        analyze_prompt = f"""
        请分析用户的问题，并进行优化和规划。
        
        用户问题：{user_question}
        
        对话历史：{history_context}
        
        请执行以下任务：
        1. 理解用户问题的核心意图
        2. 基于对话历史优化问题表述
        3. 制定回答该问题的执行计划
        
        请以JSON格式返回：
        {{
            "optimized_question": "优化后的问题",
            "analysis": "问题分析",
            "plan": "执行计划"
        }}
        """
        
        # 使用流式响应生成分析结果
        await self.emit_content("\n🔍 **分析思路：**\n")
        analysis_result = await self._generate_with_stream(
            analyze_prompt,
            temperature=0.3
        )
        
        try:
            analysis_data = json.loads(analysis_result)
            self.optimized_question = analysis_data.get("optimized_question", user_question)
            
            await self.emit_content(f"\n✅ **分析完成**")
            await self.emit_content(f"- 优化后问题: {self.optimized_question}")
            await self.emit_content(f"- 分析结果: {analysis_data.get('analysis', '')}")
            await self.emit_status("analyzing_question", status="completed", progress=0.25)
            
        except json.JSONDecodeError:
            self.optimized_question = user_question
            await self.emit_content("\n⚠️ JSON解析失败，使用原始问题进行后续处理")
    
    async def _stage_2_task_scheduling(self) -> None:
        """阶段2：任务分解与调度（流式版本）"""
        self.update_stage("task_scheduling")
        await self.emit_status("task_scheduling", progress=0.3)
        await self.emit_content("正在制定检索策略...")
        
        # 构建任务调度提示
        schedule_prompt = f"""
        基于优化后的问题，生成并行检索任务配置。
        
        优化后的问题：{self.optimized_question}
        
        可用的检索类型：
        1. online_search - 在线搜索最新信息
        2. knowledge_search - 化妆品专业知识库检索
        3. lightrag_search - LightRAG知识图谱检索
        
        请为每种检索类型生成合适的查询问题，以JSON格式返回：
        {{
            "tasks": [
                {{"type": "online_search", "query": "针对在线搜索优化的问题"}},
                {{"type": "knowledge_search", "query": "针对知识库检索优化的问题"}},
                {{"type": "lightrag_search", "query": "针对LightRAG检索优化的问题"}}
            ]
        }}
        """
        
        # 使用流式响应生成任务配置
        await self.emit_content("\n📋 **任务规划：**\n")
        schedule_result = await self._generate_with_stream(
            schedule_prompt,
            temperature=0.2
        )
        
        try:
            schedule_data = json.loads(schedule_result)
            tasks = [TaskConfig(**task) for task in schedule_data.get("tasks", [])]
            
            self.parallel_tasks_config = ParallelTasksConfig(
                tasks=tasks,
                max_concurrency=3,
                timeout=60
            )
            
            await self.emit_content(f"\n✅ **任务规划完成** - 已生成 {len(tasks)} 个并行检索任务")
            await self.emit_status("task_scheduling", status="completed", progress=0.4)
            
        except (json.JSONDecodeError, Exception) as e:
            # 使用默认任务配置
            default_tasks = [
                TaskConfig(type="online_search", query=self.optimized_question),
                TaskConfig(type="knowledge_search", query=self.optimized_question),
                TaskConfig(type="lightrag_search", query=self.optimized_question)
            ]
            
            self.parallel_tasks_config = ParallelTasksConfig(
                tasks=default_tasks,
                max_concurrency=3,
                timeout=60
            )
            
            await self.emit_content(f"\n⚠️ 任务配置解析失败，使用默认配置")
            await self.emit_status("task_scheduling", status="completed", progress=0.4)
    
    async def _stage_3_execute_tasks(self) -> None:
        """阶段3：并行任务执行"""
        self.update_stage("executing_tasks")
        await self.emit_status("executing_tasks", progress=0.5)
        await self.emit_content("正在执行并行检索任务...")
        
        if not self.parallel_tasks_config:
            raise ValueError("任务配置未生成")
        
        # 创建并行任务
        tasks = []
        for task_config in self.parallel_tasks_config.tasks:
            if task_config.type == "online_search":
                task = self._execute_online_search(task_config.query)
            elif task_config.type == "knowledge_search":
                task = self._execute_knowledge_search(task_config.query)
            elif task_config.type == "lightrag_search":
                task = self._execute_lightrag_search(task_config.query)
            else:
                continue
            
            tasks.append((task_config.type, task))
        
        # 并行执行任务
        results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
        
        # 处理结果
        for i, (task_type, _) in enumerate(tasks):
            result = results[i]
            if isinstance(result, Exception):
                self.logger.error(f"任务 {task_type} 执行失败: {str(result)}")
                self.task_results[task_type] = {"error": str(result)}
            else:
                self.task_results[task_type] = result
        
        await self.emit_content(f"并行检索完成，获得 {len(self.task_results)} 个结果")
        await self.emit_status("executing_tasks", status="completed", progress=0.8)
    
    async def _stage_4_generate_answer(self, user_question: str) -> None:
        """阶段4：结果整合与回答（流式版本）"""
        self.update_stage("generating_answer")
        await self.emit_status("generating_answer", progress=0.9)
        await self.emit_content("正在整合信息并生成回答...")
        
        try:
            # 构建整合提示
            results_context = self._build_results_context()
            history_context = self._build_history_context()
            
            integration_prompt = f"""
            基于检索到的信息，为用户提供全面准确的回答。
            
            用户原始问题：{user_question}
            优化后问题：{self.optimized_question}
            
            检索结果：
            {results_context}
            
            对话历史：
            {history_context}
            
            请基于以上信息，生成一个全面、准确、有用的回答。要求：
            1. 直接回答用户问题
            2. 整合多源信息
            3. 保持专业性和准确性
            4. 如果信息不足，请明确说明
            """
            
            # 使用流式响应生成最终回答
            await self.emit_content("\n💡 **正在生成回答：**\n")
            self.final_answer = await self._generate_with_stream(
                integration_prompt,
                temperature=0.7
            )
            
            # 如果没有获得有效回答，提供默认回答
            if not self.final_answer or len(self.final_answer.strip()) < 10:
                self.final_answer = "很抱歉，我目前无法为您提供完整的回答。这可能是由于网络问题或服务暂时不可用。请稍后再试。"
                await self.emit_content(f"\n⚠️ {self.final_answer}")
            
            # 添加助手回答到历史
            assistant_message = Message(
                role="assistant",
                content=self.final_answer,
                metadata={"stage": "final_answer", "sources": list(self.task_results.keys())}
            )
            self.history.add_message(assistant_message)
            
            await self.emit_content(f"\n✅ **回答生成完成**")
            await self.emit_status("generating_answer", status="completed", progress=1.0)
            
        except Exception as e:
            error_msg = f"生成回答时发生错误: {str(e)}"
            await self.emit_error("ANSWER_GENERATION_ERROR", error_msg)
            self.final_answer = f"抱歉，{error_msg}"
    
    async def _execute_online_search(self, query: str) -> Dict[str, Any]:
        """执行在线搜索"""
        try:
            results = await self.search_service.search_online(query)
            return {"type": "online_search", "query": query, "results": results}
        except Exception as e:
            return {"type": "online_search", "query": query, "error": str(e)}
    
    async def _execute_knowledge_search(self, query: str) -> Dict[str, Any]:
        """执行知识库搜索"""
        try:
            # 如果有用户token，使用新的query_doc方法
            if hasattr(self, 'user_token') and self.user_token:
                # 使用默认的collection_name，可以在配置中设置
                collection_name = "cosmetics_knowledge"  # 可配置
                results = await self.knowledge_service.query_doc(
                    token=self.user_token,
                    collection_name=collection_name,
                    query=query,
                    k=5
                )
                return {"type": "knowledge_search", "query": query, "results": results}
            else:
                # 使用原有的方法
                results = await self.knowledge_service.search_cosmetics_knowledge(query)
                return {"type": "knowledge_search", "query": query, "results": results}
        except Exception as e:
            return {"type": "knowledge_search", "query": query, "error": str(e)}
    
    async def _execute_lightrag_search(self, query: str) -> Dict[str, Any]:
        """执行LightRAG搜索"""
        try:
            results = await self.lightrag_service.search_lightrag(query, mode="mix")
            return {"type": "lightrag_search", "query": query, "results": results}
        except Exception as e:
            return {"type": "lightrag_search", "query": query, "error": str(e)}
    
    def _build_history_context(self) -> str:
        """构建历史对话上下文"""
        recent_messages = self.history.get_recent_messages(limit=5)
        context_parts = []
        
        for msg in recent_messages:
            context_parts.append(f"{msg.role}: {msg.content}")
        
        return "\n".join(context_parts) if context_parts else "无历史对话"
    
    def _build_results_context(self) -> str:
        """构建检索结果上下文"""
        context_parts = []
        
        for task_type, result in self.task_results.items():
            if "error" in result:
                context_parts.append(f"{task_type}: 检索失败 - {result['error']}")
            else:
                # 处理包含SearchResult对象的结果
                serializable_result = self._make_serializable(result)
                context_parts.append(f"{task_type}: {json.dumps(serializable_result, ensure_ascii=False)}")
        
        return "\n\n".join(context_parts) if context_parts else "无检索结果"
    
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
