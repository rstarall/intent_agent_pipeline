"""
工作流任务类模块

实现固定流程的多轮对话任务，包含5个阶段的执行流程：
阶段0：问题扩写与优化
阶段1：问题分析与规划  
阶段2：任务分解与调度
阶段3：并行任务执行
阶段4：结果整合与回答
"""

import json
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any

from .base_task import BaseConversationTask
from .prompts import (
    build_question_expansion_prompt,
    build_expert_analysis_prompt,
    build_universal_task_planning_prompt, 
    build_comprehensive_synthesis_prompt,
    build_knowledge_base_selection_prompt,
    PromptConfig
)
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
        self.expanded_question = ""  # 扩写后的问题
        self.optimized_question = ""
        self.parallel_tasks_config: Optional[ParallelTasksConfig] = None
        self.task_results: Dict[str, Any] = {}
        self.final_answer = ""
    
    async def execute(self) -> None:
        """执行工作流的主要逻辑"""
        try:
            # DEBUG: 打印当前的知识库配置
            print("\n" + "="*80)
            print("[DEBUG] WorkflowTask.execute 开始执行:")
            print(f"  conversation_id: {self.conversation_id}")
            print(f"  knowledge_bases: {self.knowledge_bases}")
            print(f"  knowledge_api_url: {self.knowledge_api_url}")
            print("="*80 + "\n")
            
            # 获取用户最新问题
            user_messages = self.history.get_messages_by_role("user")
            if not user_messages:
                await self.emit_error("NO_USER_MESSAGE", "没有找到用户问题")
                return
            
            user_question = user_messages[-1].content
            
            # 阶段0：问题扩写与优化
            await self._stage_0_expand_question(user_question)
            
            # 阶段1：问题分析与规划
            await self._stage_1_analyze_question(self.expanded_question)
            
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
        content_prefix: str = "",
        json_mode: bool = False
    ) -> str:
        """
        使用流式响应生成LLM回复，同时收集完整响应用于后续处理
        
        Args:
            prompt: 提示词
            temperature: 温度参数
            max_tokens: 最大令牌数
            system_message: 系统消息
            content_prefix: 内容前缀（用于区分不同阶段）
            json_mode: 是否为JSON模式
            
        Returns:
            完整的LLM响应内容
        """
        full_response = ""
        
        # 如果是JSON模式，添加系统消息
        if json_mode and not system_message:
            system_message = "You are a helpful assistant that always responds with valid JSON. Never include any text before or after the JSON object."
        
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
    
    async def _stage_0_expand_question(self, user_question: str) -> None:
        """阶段0：问题扩写与优化"""
        self.update_stage("expanding_question")
        await self.emit_status("expanding_question", progress=0.05)
        await self.emit_content("🔍 **启动问题扩写与优化...**\n")
        
        # 构建历史对话上下文
        history_context = self._build_history_context()
        
        # 获取最近的历史问题
        recent_questions = self._get_recent_user_questions()
        
        # 使用问题扩写提示词
        expansion_prompt = build_question_expansion_prompt(
            user_question, 
            history_context, 
            recent_questions
        )
        
        await self.emit_content("正在基于历史上下文进行问题扩写...\n")
        
        try:
            # 使用generate_json_response获取扩写结果
            expansion_data = await self.llm_service.generate_json_response(
                expansion_prompt,
                temperature=PromptConfig.EXPANSION_TEMPERATURE
            )
            
            # 提取扩写后的问题
            self.expanded_question = expansion_data.get("expanded_question", user_question)
            expansion_reasoning = expansion_data.get("expansion_reasoning", "")
            context_relevance = expansion_data.get("context_relevance", "medium")
            original_intent = expansion_data.get("original_intent", "")
            
            # 验证扩写质量
            if not self.expanded_question or len(self.expanded_question.strip()) < PromptConfig.MIN_EXPANSION_LENGTH:
                self.expanded_question = user_question  # 使用原问题作为后备
                await self.emit_content("⚠️ 问题扩写异常，使用原问题继续执行\n")
            
            # 显示扩写结果
            await self.emit_content(f"**✨ 问题扩写完成**\n")
            await self.emit_content(f"- **原始问题**: {user_question}\n")
            await self.emit_content(f"- **扩写后问题**: {self.expanded_question}\n")
            await self.emit_content(f"- **扩写理由**: {expansion_reasoning}\n")
            await self.emit_content(f"- **上下文关联度**: {context_relevance}\n")
            await self.emit_content(f"- **用户意图**: {original_intent}\n\n")
            
        except Exception as e:
            self.logger.error_with_context(e, {"stage": "expansion", "question": user_question})
            # 如果扩写失败，使用原问题
            self.expanded_question = user_question
            await self.emit_content("⚠️ 问题扩写失败，使用原问题继续执行\n")
        
        await self.emit_status("expanding_question", status="completed", progress=0.1)
    
    async def _stage_1_analyze_question(self, user_question: str) -> None:
        """阶段1：专家级问题分析与规划"""
        self.update_stage("analyzing_question")
        await self.emit_status("analyzing_question", progress=0.15)
        await self.emit_content("🔍 **启动专家级问题分析...**\n")
        
        # 构建历史对话上下文
        history_context = self._build_history_context()
        
        # 使用SOTA专家分析提示词
        analysis_prompt = build_expert_analysis_prompt(user_question, history_context)
        
        await self.emit_content("正在进行多维度专业分析，请稍候...\n")
        
        try:
            # 使用generate_json_response获取结构化分析结果
            analysis_data = await self.llm_service.generate_json_response(
                analysis_prompt,
                temperature=PromptConfig.ANALYSIS_TEMPERATURE
            )
            
            if analysis_data and "expert_analysis" in analysis_data:
                expert_analysis = analysis_data["expert_analysis"]
                
                # 格式化显示专家分析结果
                await self.emit_content("## 🎯 **专家分析结果**\n")
                await self.emit_content(f"{expert_analysis}\n")
                
                # 保存分析结果供后续阶段使用
                self.optimized_question = user_question  # 保持原问题，因为分析已经包含了优化思路
                self.expert_analysis = expert_analysis
                
                await self.emit_content("\n✅ **专家分析完成** - 已生成深度专业分析\n")
                await self.emit_status("analyzing_question", status="completed", progress=0.25)
                
            else:
                # 分析数据格式异常，使用原始问题
                self.logger.warning("专家分析返回数据格式异常")
                self.optimized_question = user_question
                self.expert_analysis = f"基于问题：{user_question}，需要进行全面的信息检索和分析。"
                await self.emit_content("\n⚠️ 分析过程中遇到格式问题，已使用原始问题继续处理\n")
                await self.emit_status("analyzing_question", status="completed", progress=0.25)
                
        except Exception as e:
            # 如果专家分析失败，使用原始问题和基础分析
            self.logger.warning(f"专家分析生成失败: {str(e)}")
            self.optimized_question = user_question
            self.expert_analysis = f"针对用户问题：{user_question}，需要进行多角度的信息收集和专业分析，以提供全面准确的回答。"
            await self.emit_content(f"\n⚠️ 专家分析过程遇到问题，已切换到基础模式继续处理\n")
            await self.emit_status("analyzing_question", status="completed", progress=0.25)
    
    async def _stage_2_task_scheduling(self) -> None:
        """阶段2：智能任务分解与调度"""
        self.update_stage("task_scheduling")
        await self.emit_status("task_scheduling", progress=0.3)
        await self.emit_content("📋 **启动智能任务规划...**\n")
        
        # 获取专家分析结果
        expert_analysis = getattr(self, 'expert_analysis', '需要进行全面的信息检索和分析')
        
        # 构建历史上下文
        history_context = self._build_history_context()
        
        # 使用通用任务规划提示词
        planning_prompt = build_universal_task_planning_prompt(self.optimized_question, expert_analysis, history_context)
        
        await self.emit_content("正在设计最优检索策略，请稍候...\n")
        
        try:
            # 使用generate_json_response获取结构化任务配置
            schedule_data = await self.llm_service.generate_json_response(
                planning_prompt,
                temperature=PromptConfig.PLANNING_TEMPERATURE
            )
            
            if schedule_data and "tasks" in schedule_data and isinstance(schedule_data["tasks"], list):
                tasks_config = schedule_data["tasks"]
                
                # 验证任务配置格式
                valid_tasks = []
                for task in tasks_config:
                    if isinstance(task, dict) and "type" in task and "query" in task:
                        # 确保任务类型有效
                        if task["type"] in ["online_search", "knowledge_search", "lightrag_search"]:
                            valid_tasks.append(TaskConfig(**task))
                        else:
                            self.logger.warning(f"无效的任务类型: {task.get('type')}")
                
                if valid_tasks:
                    # 格式化显示任务规划结果
                    await self.emit_content("## 🎯 **检索策略规划**\n")
                    
                    type_names = {
                        "online_search": "🌐 在线搜索",
                        "knowledge_search": "📚 知识库检索",
                        "lightrag_search": "🔗 知识图谱"
                    }
                    
                    for i, task in enumerate(valid_tasks, 1):
                        type_name = type_names.get(task.type, task.type)
                        await self.emit_content(f"**{i}. {type_name}**\n")
                        await self.emit_content(f"   查询策略: {task.query}\n\n")
                    
                    self.parallel_tasks_config = ParallelTasksConfig(
                        tasks=valid_tasks,
                        max_concurrency=3,
                        timeout=60
                    )
                    
                    await self.emit_content(f"✅ **任务规划完成** - 已生成 {len(valid_tasks)} 个并行检索任务\n")
                    
                    # 如果有知识库配置，显示选择的知识库
                    if self.knowledge_bases and any(task.type == "knowledge_search" for task in valid_tasks):
                        await self.emit_content("\n📚 **知识库配置：**\n")
                        await self.emit_content("系统将根据问题内容智能选择最相关的知识库进行检索\n")
                        
                        # 如果使用了自定义的知识库API URL
                        if self.knowledge_api_url:
                            await self.emit_content(f"🔗 使用自定义知识库API: {self.knowledge_api_url}\n")
                    
                    await self.emit_status("task_scheduling", status="completed", progress=0.4)
                else:
                    # 没有有效任务，使用默认配置
                    self.logger.warning("没有生成有效的任务配置")
                    self._use_default_task_config()
                    await self.emit_content("⚠️ 任务配置验证失败，使用默认检索策略\n")
                    await self.emit_status("task_scheduling", status="completed", progress=0.4)
            else:
                # JSON格式异常，使用默认配置
                self.logger.warning("任务规划返回数据格式异常")
                self._use_default_task_config()
                await self.emit_content("⚠️ 任务规划数据格式异常，使用默认检索策略\n")
                await self.emit_status("task_scheduling", status="completed", progress=0.4)
                
        except Exception as e:
            # 如果任务规划失败，使用默认配置
            self.logger.warning(f"任务规划生成失败: {str(e)}")
            self._use_default_task_config()
            await self.emit_content(f"⚠️ 任务规划过程遇到问题，使用默认检索策略\n")
            await self.emit_status("task_scheduling", status="completed", progress=0.4)
    
    def _use_default_task_config(self) -> None:
        """使用默认任务配置"""
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
        
        # 处理结果并实时反馈
        await self.emit_content("\n\n📊 **检索结果：**")
        
        # 定义任务类型的中文名称
        type_names = {
            "online_search": "在线搜索",
            "knowledge_search": "知识库检索", 
            "lightrag_search": "知识图谱"
        }
        
        success_count = 0
        for i, (task_type, _) in enumerate(tasks):
            result = results[i]
            type_name = type_names.get(task_type, task_type)
            
            if isinstance(result, Exception):
                # 处理错误情况
                error_msg = str(result)
                self.logger.error(f"任务 {task_type} 执行失败: {error_msg}")
                self.task_results[task_type] = {"error": error_msg}
                
                # 向前端发送错误反馈
                await self.emit_content(f"\n❌ **{type_name}** - 检索失败")
                await self.emit_content(f"   错误信息: {error_msg}")
            else:
                # 处理成功情况
                self.task_results[task_type] = result
                
                # 计算结果数量
                result_count = 0
                if isinstance(result, dict):
                    if "results" in result:
                        raw_results = result["results"]
                        if isinstance(raw_results, list):
                            # 处理列表格式的结果（在线搜索、传统知识库搜索）
                            result_count = len(raw_results)
                        elif isinstance(raw_results, dict) and "documents" in raw_results:
                            # 处理query_doc的返回格式
                            docs = raw_results.get("documents", [])
                            if docs and isinstance(docs[0], list):
                                result_count = len(docs[0])
                        elif isinstance(raw_results, dict):
                            # 如果是其他字典格式，尝试从常见字段获取计数
                            if "data" in raw_results:
                                data = raw_results["data"]
                                result_count = len(data) if isinstance(data, list) else 1
                            elif raw_results:  # 非空字典就认为有结果
                                result_count = 1
                
                # 向前端发送成功反馈
                if result_count > 0:
                    await self.emit_content(f"\n✅ **{type_name}** - 检索成功")
                    await self.emit_content(f"   获得 {result_count} 个结果")
                    success_count += 1
                else:
                    # 虽然技术上成功了，但没有找到结果
                    await self.emit_content(f"\n⚠️ **{type_name}** - 未找到相关结果")
                    await self.emit_content(f"   查询: {result.get('query', '未知')}")
                    self.logger.warning(f"{task_type} 返回了空结果")
        
        # 总结反馈
        await self.emit_content(f"\n\n📈 **检索总结：**")
        await self.emit_content(f"- 成功: {success_count}/{len(tasks)} 个任务")
        await self.emit_content(f"- 失败: {len(tasks) - success_count}/{len(tasks)} 个任务")
        
        # 生成结构化的搜索结果报告
        await self._generate_search_results_report()
        
        await self.emit_status("executing_tasks", status="completed", progress=0.8)
    
    async def _stage_4_generate_answer(self, user_question: str) -> None:
        """阶段4：专业综合分析与详细回答"""
        self.update_stage("generating_answer")
        await self.emit_status("generating_answer", progress=0.85)
        await self.emit_content("\n\n## 💡 **专业综合分析**\n")
        
        try:
            # 构建检索结果上下文和历史上下文
            results_context = self._build_results_context()
            history_context = self._build_history_context()
            
            # 使用综合分析提示词模板
            synthesis_prompt = build_comprehensive_synthesis_prompt(
                user_question,
                self.expanded_question, 
                self.optimized_question, 
                results_context, 
                history_context
            )
            
            # 使用流式响应生成最终回答
            self.final_answer = await self._generate_with_stream(
                synthesis_prompt,
                temperature=PromptConfig.SYNTHESIS_TEMPERATURE,
                max_tokens=PromptConfig.MAX_SYNTHESIS_TOKENS
            )
            
            # 验证回答质量
            if not self.final_answer or len(self.final_answer.strip()) < 100:
                # 如果回答过短，提供基础回答
                basic_answer = self._generate_basic_answer(user_question, results_context)
                self.final_answer = basic_answer
                await self.emit_content(f"\n⚠️ 专业分析生成异常，已提供基础回答\n")
                await self.emit_content(basic_answer)
            
            # 添加助手回答到历史记录
            assistant_message = Message(
                role="assistant",
                content=self.final_answer,
                metadata={
                    "stage": "comprehensive_analysis", 
                    "sources": list(self.task_results.keys()),
                    "analysis_type": "expert_synthesis"
                }
            )
            self.history.add_message(assistant_message)
            
            await self.emit_status("generating_answer", status="completed", progress=1.0)
            
        except Exception as e:
            error_msg = f"生成专业分析时发生错误: {str(e)}"
            self.logger.error(error_msg)
            
            # 生成备用回答
            try:
                results_context = self._build_results_context()
                fallback_answer = self._generate_basic_answer(user_question, results_context)
                self.final_answer = fallback_answer
                
                await self.emit_content(f"\n⚠️ {error_msg}\n")
                await self.emit_content("已切换到基础分析模式：\n\n")
                await self.emit_content(fallback_answer)
                
            except Exception as fallback_error:
                # 最后的兜底方案
                self.final_answer = "很抱歉，我目前无法为您提供完整的分析。这可能是由于系统负载或网络问题。请稍后再试，或者重新描述您的问题。"
                await self.emit_error("ANSWER_GENERATION_ERROR", self.final_answer)
    
    def _generate_basic_answer(self, user_question: str, results_context: str) -> str:
        """生成基础回答作为备用方案"""
        basic_answer = f"""
## 基础分析回答

**您的问题：** {user_question}

**基于检索信息的回答：**

根据我们收集到的信息，针对您的问题，可以从以下几个方面来回答：

### 核心信息
{self._extract_key_information(results_context)}

### 详细说明
{self._extract_detailed_information(results_context)}

### 参考来源
{self._extract_source_references(results_context)}

---
*注：这是基础分析模式的回答。如需更深入的专业分析，请重新提问。*
"""
        return basic_answer
    
    def _extract_key_information(self, results_context: str) -> str:
        """从检索结果中提取关键信息"""
        if not results_context or results_context.strip() == "无检索结果":
            return "暂时没有获取到相关信息。"
        
        # 简单提取前300字符作为核心信息
        key_info = results_context[:300]
        if len(results_context) > 300:
            key_info += "..."
        
        return key_info
    
    def _extract_detailed_information(self, results_context: str) -> str:
        """从检索结果中提取详细信息"""
        if not results_context or results_context.strip() == "无检索结果":
            return "由于信息获取限制，无法提供详细说明。建议您尝试更具体的问题描述或稍后再试。"
        
        # 提取更多内容作为详细信息
        detailed_info = results_context[300:800] if len(results_context) > 300 else "详细信息正在处理中..."
        
        return detailed_info
    
    def _extract_source_references(self, results_context: str) -> str:
        """从检索结果中提取来源引用"""
        sources = []
        
        # 简单的来源提取逻辑
        for task_type, result in self.task_results.items():
            if "error" not in result:
                type_name = {"online_search": "在线搜索", "knowledge_search": "知识库", "lightrag_search": "知识图谱"}.get(task_type, task_type)
                sources.append(f"- {type_name}: 已检索相关信息")
        
        return "\n".join(sources) if sources else "- 系统内部知识库"
    
    async def _execute_online_search(self, query: str) -> Dict[str, Any]:
        """执行在线搜索"""
        try:
            self.logger.info(f"开始执行在线搜索: {query}")
            results = await self.search_service.search_online(query)
            self.logger.info(f"在线搜索成功，获得 {len(results)} 个结果")
            return {"type": "online_search", "query": query, "results": results}
        except Exception as e:
            error_msg = f"在线搜索失败: {str(e)}"
            self.logger.error(error_msg)
            return {"type": "online_search", "query": query, "error": error_msg}
    
    async def _execute_knowledge_search(self, query: str) -> Dict[str, Any]:
        """执行知识库搜索（包含智能选择知识库的子阶段）"""
        try:
            self.logger.info(f"开始执行知识库搜索: {query}")
            
            # 如果有用户token，使用新的query_doc方法
            if hasattr(self, 'user_token') and self.user_token:
                # 子阶段：智能选择知识库
                collection_name = await self._select_knowledge_base(query)
                
                if not collection_name:
                    # 如果选择失败，使用默认值
                    collection_name = "test"
                    self.logger.warning("知识库选择失败，使用默认知识库: test")
                
                # 最终验证：确保不会使用无效的知识库名称
                valid_names = [kb.get('name') for kb in self.knowledge_bases] if self.knowledge_bases else []
                if collection_name not in valid_names and collection_name != "test":
                    self.logger.warning(f"检测到无效的知识库名称 '{collection_name}'，强制使用 'test'")
                    await self.emit_content(f"\n⚠️ 最终验证发现知识库名称 '{collection_name}' 无效，已强制使用默认库 'test'")
                    collection_name = "test"
                
                self.logger.info(f"使用query_doc方法，collection: {collection_name}")
                
                # 尝试使用选定的知识库，如果失败则回退到默认值
                try:
                    results = await self.knowledge_service.query_doc_by_name(
                        token=self.user_token,
                        knowledge_base_name=collection_name,
                        query=query,
                        k=5,
                        api_url=self.knowledge_api_url
                    )
                    self.logger.info(f"知识库搜索成功 (query_doc_by_name)")
                    return {"type": "knowledge_search", "query": query, "results": results, "collection_name": collection_name}
                except Exception as e:
                    # 如果是collection不存在的错误或未找到知识库，尝试使用默认知识库
                    error_str = str(e)
                    if ("Collection" in error_str and "does not exist" in error_str) or \
                       ("未找到名称为" in error_str and "的知识库" in error_str):
                        self.logger.warning(f"知识库 {collection_name} 不存在或未找到，尝试使用默认知识库: test")
                        await self.emit_content(f"\n⚠️ 知识库 {collection_name} 不存在，使用默认知识库")
                        
                        try:
                            results = await self.knowledge_service.query_doc_by_name(
                                token=self.user_token,
                                knowledge_base_name="test",
                                query=query,
                                k=5,
                                api_url=self.knowledge_api_url
                            )
                            self.logger.info(f"使用默认知识库搜索成功")
                            return {"type": "knowledge_search", "query": query, "results": results, "collection_name": "test"}
                        except Exception as fallback_error:
                            # 如果默认知识库也失败，抛出原始错误
                            raise fallback_error
                    else:
                        # 其他错误直接抛出
                        raise
            else:
                # 使用原有的方法，传递knowledge_api_url
                self.logger.info(f"使用search_cosmetics_knowledge方法")
                results = await self.knowledge_service.search_cosmetics_knowledge(
                    query=query,
                    api_url=self.knowledge_api_url
                )
                result_count = len(results) if isinstance(results, list) else 0
                self.logger.info(f"知识库搜索成功，获得 {result_count} 个结果")
                return {"type": "knowledge_search", "query": query, "results": results}
        except Exception as e:
            error_msg = f"知识库搜索失败: {str(e)}"
            self.logger.error(error_msg)
            return {"type": "knowledge_search", "query": query, "error": error_msg}
    
    async def _select_knowledge_base(self, query: str) -> Optional[str]:
        """智能选择最合适的知识库"""
        try:
            # 打印当前的知识库配置，便于调试
            self.logger.info(f"开始知识库选择流程，查询: {query}")
            self.logger.info(f"当前知识库配置: {self.knowledge_bases}")
            
            # 向用户显示调试信息
            await self.emit_content(f"\n🔍 **知识库选择调试信息**")
            await self.emit_content(f"   查询内容: {query}")
            await self.emit_content(f"   可用知识库数量: {len(self.knowledge_bases) if self.knowledge_bases else 0}")
            
            # 如果没有配置知识库，直接返回默认值
            if not self.knowledge_bases or len(self.knowledge_bases) == 0:
                self.logger.info("没有配置知识库，使用默认值: test")
                await self.emit_content(f"   未配置知识库，使用默认: test")
                return "test"
            
            # 显示可用的知识库列表
            kb_names = [kb.get('name', '未知') for kb in self.knowledge_bases]
            await self.emit_content(f"   可用知识库: {', '.join(kb_names)}")
            
            # 如果只有一个知识库，直接使用
            if len(self.knowledge_bases) == 1:
                selected_name = self.knowledge_bases[0].get('name', 'test')
                self.logger.info(f"只有一个知识库，直接选择: {selected_name}")
                await self.emit_content(f"   仅有一个知识库，直接选择: {selected_name}")
                return selected_name
            
            # 使用新的知识库选择提示词
            selection_prompt = build_knowledge_base_selection_prompt(query, self.knowledge_bases)
            
            # 调用LLM选择知识库
            result = await self.llm_service.generate_json_response(
                selection_prompt,
                temperature=PromptConfig.SELECTION_TEMPERATURE
            )
            
            if result and isinstance(result, dict):
                selected_name = result.get("collection_name", "").strip()
                reason = result.get("reason", "")
                
                # 验证选择的知识库是否存在
                valid_names = [kb.get('name') for kb in self.knowledge_bases]
                self.logger.info(f"LLM返回的知识库名称: '{selected_name}', 可用选项: {valid_names}")
                
                # 严格验证选择的名称
                if selected_name and selected_name in valid_names:
                    self.logger.info(f"智能选择知识库: {selected_name}, 原因: {reason}")
                    # 向前端发送选择结果
                    await self.emit_content(f"\n🎯 **知识库选择**: {selected_name}")
                    if reason:
                        await self.emit_content(f"   选择原因: {reason}")
                    return selected_name
                else:
                    # 检查是否选择了常见的无效名称
                    invalid_names = ["default", "default_kb", "默认", "default_collection"]
                    if selected_name in invalid_names:
                        self.logger.warning(f"LLM使用了禁止的知识库名称: '{selected_name}'，这是常见的错误")
                        await self.emit_content(f"\n⚠️ 系统检测到无效的知识库名称 '{selected_name}'")
                    else:
                        self.logger.warning(f"LLM选择了无效的知识库: '{selected_name}'，可用选项: {valid_names}")
                        await self.emit_content(f"\n⚠️ LLM选择了无效的知识库名称 '{selected_name}'")
                    
                    # 使用第一个可用的知识库作为回退
                    fallback_kb = valid_names[0] if valid_names else "test"
                    self.logger.info(f"自动回退到第一个可用知识库: {fallback_kb}")
                    await self.emit_content(f"   已自动选择: {fallback_kb}")
                    return fallback_kb
            else:
                self.logger.warning("LLM未能返回有效的知识库选择结果")
                # 返回第一个可用的知识库
                valid_names = [kb.get('name') for kb in self.knowledge_bases]
                fallback_kb = valid_names[0] if valid_names else "test"
                self.logger.info(f"使用第一个可用知识库作为回退: {fallback_kb}")
                await self.emit_content(f"\n⚠️ 知识库选择失败，使用默认选择: {fallback_kb}")
                return fallback_kb
                
        except Exception as e:
            self.logger.error(f"选择知识库时发生错误: {str(e)}")
            return None
    
    async def _execute_lightrag_search(self, query: str) -> Dict[str, Any]:
        """执行LightRAG搜索"""
        try:
            self.logger.info(f"开始执行LightRAG搜索: {query}")
            results = await self.lightrag_service.search_lightrag(query, mode="mix")
            self.logger.info(f"LightRAG搜索成功，获得 {len(results)} 个结果")
            return {"type": "lightrag_search", "query": query, "results": results}
        except Exception as e:
            # 更安全的异常消息提取，避免访问不存在的键
            try:
                error_msg = f"LightRAG搜索失败: {str(e)}"
            except Exception as str_error:
                # 如果str(e)失败，提供备用错误消息
                error_msg = f"LightRAG搜索失败: {type(e).__name__}异常，详情: {repr(e)}"
            
            self.logger.error(error_msg)
            return {"type": "lightrag_search", "query": query, "error": error_msg}
    
    async def _generate_search_results_report(self) -> None:
        """生成结构化的搜索结果报告"""
        import json
        
        # 构建结构化的搜索结果
        search_report = {
            "timestamp": datetime.now().isoformat(),
            "query": self.optimized_question,
            "search_results": {
                "online_search": self._format_search_results("online_search"),
                "knowledge_search": self._format_search_results("knowledge_search"),
                "lightrag_search": self._format_search_results("lightrag_search")
            }
        }
        
        # 发送JSON结构
        await self.emit_content("\n\n## 📊 检索结果\n")
        await self.emit_content("```json\n" + json.dumps(search_report, ensure_ascii=False, indent=2) + "\n```")
    
    def _format_search_results(self, search_type: str) -> Dict[str, Any]:
        """格式化单个搜索类型的结果"""
        result = self.task_results.get(search_type, {})
        
        if "error" in result:
            return {
                "status": "error",
                "error": result["error"],
                "query": result.get("query", ""),
                "results": []
            }
        
        # 提取搜索结果
        search_results = []
        raw_results = result.get("results", [])
        
        # 处理不同类型的结果格式
        if isinstance(raw_results, list):
            for item in raw_results[:5]:  # 限制显示前5个结果
                if hasattr(item, 'to_dict'):
                    item_dict = item.to_dict()
                else:
                    item_dict = item if isinstance(item, dict) else {}
                
                formatted_result = {
                    "title": item_dict.get("title", "无标题"),
                    "content": item_dict.get("content", "")[:200] + "..." if len(item_dict.get("content", "")) > 200 else item_dict.get("content", ""),
                    "url": item_dict.get("url", ""),
                    "score": item_dict.get("score", 0.0)
                }
                search_results.append(formatted_result)
        elif isinstance(raw_results, dict) and "documents" in raw_results:
            # 处理query_doc格式
            docs = raw_results.get("documents", [])
            if docs and isinstance(docs[0], list):
                for i, doc in enumerate(docs[0][:5]):
                    formatted_result = {
                        "title": f"文档片段 {i+1}",
                        "content": doc[:200] + "..." if len(doc) > 200 else doc,
                        "url": "",
                        "score": 1.0
                    }
                    search_results.append(formatted_result)
        
        return {
            "status": "success",
            "query": result.get("query", ""),
            "result_count": len(search_results),
            "collection_name": result.get("collection_name", ""),
            "results": search_results
        }
    
    def _generate_markdown_report_deprecated(self, report: Dict[str, Any]) -> str:
        """生成Markdown格式的搜索报告"""
        md_lines = []
        
        # 标题和时间
        md_lines.append(f"**查询问题**: {report['query']}")
        md_lines.append(f"**查询时间**: {report['timestamp']}")
        md_lines.append("")
        
        # 各搜索类型的结果
        type_names = {
            "online_search": "🌐 在线搜索",
            "knowledge_search": "📚 知识库检索",
            "lightrag_search": "🔗 知识图谱"
        }
        
        for search_type, type_name in type_names.items():
            result_data = report["search_results"][search_type]
            md_lines.append(f"### {type_name}")
            
            if result_data["status"] == "error":
                md_lines.append(f"- **状态**: ❌ 失败")
                md_lines.append(f"- **错误**: {result_data['error']}")
            else:
                md_lines.append(f"- **状态**: ✅ 成功")
                md_lines.append(f"- **查询**: {result_data['query']}")
                md_lines.append(f"- **结果数**: {result_data['result_count']}")
                if result_data.get("collection_name"):
                    md_lines.append(f"- **知识库**: {result_data['collection_name']}")
                
                if result_data["results"]:
                    md_lines.append("\n**TOP 结果**:")
                    for i, res in enumerate(result_data["results"], 1):
                        md_lines.append(f"\n{i}. **{res['title']}**")
                        if res['content']:
                            md_lines.append(f"   > {res['content']}")
                        if res.get('url'):
                            md_lines.append(f"   > 链接: {res['url']}")
                        if res.get('score') > 0:
                            md_lines.append(f"   > 相关度: {res['score']:.2f}")
            
            md_lines.append("")
        
        return "\n".join(md_lines)
    
    def _build_history_context(self) -> str:
        """构建历史对话上下文"""
        recent_messages = self.history.get_recent_messages(limit=5)
        context_parts = []
        
        for msg in recent_messages:
            context_parts.append(f"{msg.role}: {msg.content}")
        
        return "\n".join(context_parts) if context_parts else "无历史对话"
    
    def _get_recent_user_questions(self, limit: int = 5) -> list:
        """获取最近的用户问题列表"""
        user_messages = self.history.get_messages_by_role("user")
        if not user_messages:
            return []
        
        # 获取最近的用户问题，排除当前问题
        recent_questions = []
        for msg in user_messages[-limit-1:-1]:  # 排除最后一条（当前问题）
            if msg.content.strip():
                recent_questions.append(msg.content.strip())
        
        return recent_questions
    
    async def _generate_json_with_fallback(
        self,
        prompt: str,
        schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.3,
        show_stream: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        生成JSON响应，带有流式显示和回退机制
        
        Args:
            prompt: 提示词
            schema: JSON模式
            temperature: 温度参数
            show_stream: 是否显示流式输出
            
        Returns:
            解析后的JSON数据，如果失败返回None
        """
        try:
            if show_stream:
                # 使用流式响应显示给用户
                result = await self._generate_with_stream(prompt, temperature=temperature)
            else:
                # 直接调用generate_json_response
                return await self.llm_service.generate_json_response(
                    prompt=prompt,
                    schema=schema,
                    temperature=temperature
                )
            
            # 尝试解析结果
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                # 尝试提取JSON部分
                import re
                json_match = re.search(r'\{.*\}', result, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                return None
                
        except Exception as e:
            self.logger.error(f"生成JSON响应失败: {e}")
            return None
    
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
