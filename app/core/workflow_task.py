"""
工作流任务类模块

实现固定流程的多轮对话任务，包含4个阶段的执行流程。
"""

import json
import asyncio
from datetime import datetime
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
    
    async def _stage_1_analyze_question(self, user_question: str) -> None:
        """阶段1：问题分析与规划（流式版本）"""
        self.update_stage("analyzing_question")
        await self.emit_status("analyzing_question", progress=0.1)
        await self.emit_content("正在分析您的问题...")
        
        # 构建分析提示
        history_context = self._build_history_context()
        
        analyze_prompt = f"""
        请深入分析用户的问题，提取关键信息并优化问题表述。
        
        用户问题：{user_question}
        
        对话历史：{history_context}
        
        请执行以下分析任务：
        1. 识别关键概念和实体
           - 主要对象（如：洗面奶、防晒霜、特定成分）
           - 相关属性（如：成分、功效、使用方法、法规要求）
           - 限定条件（如：敏感肌、特定年龄、使用场景）
        
        2. 理解问题意图
           - 是寻求信息介绍？（what/是什么）
           - 是寻求使用建议？（how/怎么用）
           - 是寻求原因解释？（why/为什么）
           - 是寻求比较选择？（which/哪个好）
           - 是寻求法规标准？（规定/标准）
        
        3. 优化问题表述
           - 补充必要的上下文信息
           - 明确具体的查询重点
           - 保留所有重要细节
        
        4. 制定检索策略
           - 需要最新信息吗？（市场动态、新规定、新产品）
           - 需要专业知识吗？（成分解析、配方原理、技术标准）
           - 需要关联信息吗？（成分间相互作用、功效机理）
        
        请以JSON格式返回：
        {{
            "optimized_question": "包含所有关键信息的优化问题",
            "analysis": "详细的问题分析，包括识别的关键概念、问题意图等",
            "plan": "针对性的信息检索和回答策略"
        }}
        
        重要：请只返回JSON对象，不要包含任何其他文本或解释。
        """
        
        # 使用非流式响应生成JSON分析结果
        await self.emit_content("\n🔍 **分析思路：**\n")
        
        # 显示正在分析的提示
        await self.emit_content("正在深入分析问题，请稍候...")
        
        try:
            # 使用generate_json_response获取结构化数据
            analysis_data = await self.llm_service.generate_json_response(
                analyze_prompt,
                temperature=0.3
            )
            
            # 直接使用返回的字典数据
            self.optimized_question = analysis_data.get("optimized_question", user_question)
            
            # 格式化显示JSON结果
            import json
            formatted_json = json.dumps(analysis_data, ensure_ascii=False, indent=2)
            await self.emit_content(f"\n```json\n{formatted_json}\n```")
            
            await self.emit_content(f"\n✅ **分析完成**")
            await self.emit_content(f"- 优化后问题: {self.optimized_question}")
            await self.emit_content(f"- 分析结果: {analysis_data.get('analysis', '')}")
            await self.emit_status("analyzing_question", status="completed", progress=0.25)
            
        except Exception as e:
            # 如果JSON生成失败，使用原始问题
            self.logger.warning(
                "问题分析失败",
                error=str(e)
            )
            self.optimized_question = user_question
            await self.emit_content("\n⚠️ 问题分析失败，使用原始问题进行后续处理")
            await self.emit_status("analyzing_question", status="completed", progress=0.25)
    
    async def _stage_2_task_scheduling(self) -> None:
        """阶段2：任务分解与调度（流式版本）"""
        self.update_stage("task_scheduling")
        await self.emit_status("task_scheduling", progress=0.3)
        await self.emit_content("正在制定检索策略...")
        
        # 构建任务调度提示
        schedule_prompt = f"""
        基于优化后的问题，生成并行检索任务配置。
        
        用户问题：{self.optimized_question}
        
        可用的检索类型及其特点：
        1. online_search - 在线搜索最新信息，适合查找时效性强的内容、最新资讯、新闻动态
        2. knowledge_search - 专业知识库检索，适合查找专业知识、技术文档、规范标准
        3. lightrag_search - LightRAG知识图谱检索，适合查找概念关联、知识图谱、深层次关系
        
        生成查询的要求：
        1. 每个查询必须具体、明确，包含关键实体、概念和限定词
        2. 不同检索类型的查询应有针对性，充分利用各自的优势
        3. 查询应该覆盖问题的不同方面，但又有所侧重
        4. 避免过于宽泛的查询，如"化妆品法规"，而应该具体到问题的核心点
        5. 如果问题涉及时间敏感信息，online_search应包含时间限定词
        6. 如果问题涉及专业概念，knowledge_search应包含专业术语
        7. 如果问题涉及多个概念的关系，lightrag_search应体现关联性
        
        示例（仅供参考格式）：
        - 如果用户问"洗面奶的成分"，不要只查询"洗面奶成分"
        - online_search可以查询："2024年最新洗面奶成分安全标准 表面活性剂"
        - knowledge_search可以查询："洗面奶配方成分表 清洁剂 保湿剂 功能性原料"
        - lightrag_search可以查询："洗面奶成分功效关系 敏感肌适用成分"
        
        请为每种检索类型生成合适的查询，以JSON格式返回：
        {{
            "tasks": [
                {{"type": "online_search", "query": "根据问题生成的具体在线搜索查询"}},
                {{"type": "knowledge_search", "query": "根据问题生成的具体知识库查询"}},
                {{"type": "lightrag_search", "query": "根据问题生成的具体图谱查询"}}
            ]
        }}
        
        重要：请只返回JSON对象，不要包含任何其他文本或解释。
        """
        
        # 使用非流式响应生成JSON任务配置
        await self.emit_content("\n📋 **任务规划：**\n")
        
        # 显示正在规划的提示
        await self.emit_content("正在制定检索策略，请稍候...")
        
        try:
            # 使用generate_json_response获取结构化数据
            schedule_data = await self.llm_service.generate_json_response(
                schedule_prompt,
                temperature=0.2
            )
            
            # 直接使用返回的字典数据
            tasks = [TaskConfig(**task) for task in schedule_data.get("tasks", [])]
            
            # 格式化显示JSON结果
            import json
            formatted_json = json.dumps(schedule_data, ensure_ascii=False, indent=2)
            await self.emit_content(f"\n```json\n{formatted_json}\n```")
            
            self.parallel_tasks_config = ParallelTasksConfig(
                tasks=tasks,
                max_concurrency=3,
                timeout=60
            )
            
            await self.emit_content(f"\n✅ **任务规划完成** - 已生成 {len(tasks)} 个并行检索任务")
            
            # 如果有知识库配置，显示选择的知识库
            if self.knowledge_bases and any(task.type == "knowledge_search" for task in tasks):
                await self.emit_content("\n📚 **知识库选择：**")
                await self.emit_content("系统将根据问题内容智能选择最相关的知识库进行检索")
                
                # 如果使用了自定义的知识库API URL
                if self.knowledge_api_url:
                    await self.emit_content(f"🔗 使用自定义知识库API: {self.knowledge_api_url}")
            
            await self.emit_status("task_scheduling", status="completed", progress=0.4)
            
        except Exception as e:
            # 如果JSON生成失败，使用默认配置
            self.logger.warning(
                "任务规划失败",
                error=str(e)
            )
            self._use_default_task_config()
            await self.emit_content(f"\n⚠️ 任务规划失败，使用默认配置")
            await self.emit_status("task_scheduling", status="completed", progress=0.4)
                
        except Exception as e:
            # 其他异常也使用默认配置
            self.logger.error(f"任务配置处理异常: {e}")
            self._use_default_task_config()
            await self.emit_content(f"\n⚠️ 任务配置处理失败，使用默认配置")
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
                    if "results" in result and isinstance(result["results"], list):
                        result_count = len(result["results"])
                    elif "documents" in result:  # 处理query_doc的返回格式
                        docs = result.get("documents", [])
                        if docs and isinstance(docs[0], list):
                            result_count = len(docs[0])
                
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
        """阶段4：结果整合与回答（流式版本）"""
        self.update_stage("generating_answer")
        await self.emit_status("generating_answer", progress=0.9)
        await self.emit_content("\n\n## 💡 最终回答\n")
        
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
            
            基于检索到的信息，请提供一个全面、深入、有价值的回答。
            
            **回答要求**：
            
            1. **核心内容**（必须包含）：
               - 直接回答用户的问题，确保准确性
               - 整合多个来源的信息，形成完整观点
               - 分析不同来源信息的关联性和互补性
            
            2. **深度分析**（根据问题性质选择性包含）：
               - 背景知识：如果有助于理解，简要介绍相关背景
               - 原理解释：涉及技术或科学问题时，解释基本原理
               - 多角度分析：从不同维度分析问题（如优缺点、适用场景等）
               - 发展趋势：如果相关，可以提及领域的发展方向
               - 实际应用：结合实际场景说明应用价值
            
            3. **引用规范**（严格遵守）：
               - 在引用具体信息时使用上标数字[1]、[2]等
               - 确保引用编号与检索结果中的编号一致
               - 在回答末尾必须添加"**参考来源：**"部分
               - 每个引用包含：
                 * 引用编号
                 * 来源类型（在线搜索/知识库检索/知识图谱）
                 * 标题
                 * **在线搜索必须包含完整URL链接**
                 * 关键内容摘要
            
            4. **总结提升**（在回答末尾）：
               - 核心要点总结：提炼最重要的2-3个关键信息
               - 延伸思考：提出1-2个相关的思考问题或建议
               - 信息完整性说明：如果某些方面信息不足，明确指出
            
            5. **写作风格**：
               - 逻辑清晰：使用段落和要点组织内容
               - 专业准确：使用领域内的专业术语
               - 易于理解：复杂概念要有通俗解释
               - 客观中立：如有争议观点，平衡呈现不同看法
            
            **特别注意**：
            - 绝对不能编造信息或虚假URL
            - 所有观点必须基于检索结果
            - 如果信息存在冲突，要明确指出并分析原因
            - 保持批判性思维，不盲目接受单一来源信息
            """
            
            # 使用流式响应生成最终回答
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
            
            await self.emit_status("generating_answer", status="completed", progress=1.0)
            
        except Exception as e:
            error_msg = f"生成回答时发生错误: {str(e)}"
            await self.emit_error("ANSWER_GENERATION_ERROR", error_msg)
            self.final_answer = f"抱歉，{error_msg}"
    
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
            # 打印当前的知识库配置
            self.logger.info(f"当前知识库配置: {self.knowledge_bases}")
            
            # 如果没有配置知识库，直接返回默认值
            if not self.knowledge_bases or len(self.knowledge_bases) == 0:
                self.logger.info("没有配置知识库，使用默认值: test")
                return "test"
            
            # 如果只有一个知识库，直接使用
            if len(self.knowledge_bases) == 1:
                return self.knowledge_bases[0].get('name', 'test')
            
            # 构建知识库描述
            kb_list = []
            for kb in self.knowledge_bases:
                kb_name = kb.get('name', '未知')
                kb_desc = kb.get('description', '无描述')
                kb_list.append(f'"{kb_name}": {kb_desc}')
            
            kb_descriptions = "\n".join(kb_list)
            
            # 构建选择提示
            selection_prompt = f"""
            根据用户的查询问题，选择最合适的知识库进行检索。
            
            用户查询：{query}
            
            可用的知识库：
            {kb_descriptions}
            
            请分析用户查询的内容和意图，选择最相关的知识库。
            
            返回JSON格式：
            {{
                "collection_name": "选择的知识库名称",
                "reason": "选择这个知识库的原因（简短说明）"
            }}
            
            注意：collection_name必须是上述知识库列表中的某个名称。
            """
            
            # 调用LLM选择知识库
            result = await self.llm_service.generate_json_response(
                selection_prompt,
                temperature=0.1  # 使用较低的温度以获得更确定的选择
            )
            
            if result and isinstance(result, dict):
                selected_name = result.get("collection_name")
                reason = result.get("reason", "")
                
                # 验证选择的知识库是否存在
                valid_names = [kb.get('name') for kb in self.knowledge_bases]
                if selected_name in valid_names:
                    self.logger.info(f"智能选择知识库: {selected_name}, 原因: {reason}")
                    # 向前端发送选择结果
                    await self.emit_content(f"\n🎯 **知识库选择**: {selected_name}")
                    if reason:
                        await self.emit_content(f"   选择原因: {reason}")
                    return selected_name
                else:
                    self.logger.warning(f"LLM选择了无效的知识库: {selected_name}")
                    return None
            else:
                self.logger.warning("LLM未能返回有效的知识库选择")
                return None
                
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
            error_msg = f"LightRAG搜索失败: {str(e)}"
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
