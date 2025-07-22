"""
LangGraph节点定义模块

定义工作流中各个Agent节点的执行逻辑。
"""

import asyncio
from typing import Dict, Any, List
import json

from .state_manager import AgentState, StateManager
from ..services import LLMService, KnowledgeService, LightRagService, SearchService
from ..config import get_logger


class NodeDefinitions:
    """节点定义类"""
    
    def __init__(self):
        """初始化节点定义"""
        self.logger = get_logger("NodeDefinitions")
        
        # 初始化服务
        self.llm_service = LLMService()
        self.knowledge_service = KnowledgeService()
        self.lightrag_service = LightRagService()
        self.search_service = SearchService()
    
    async def master_agent_node(self, state: AgentState) -> AgentState:
        """
        总控制者Agent节点
        
        Args:
            state: 当前状态
            
        Returns:
            AgentState: 更新后的状态
        """
        try:
            self.logger.info("执行总控制者Agent", conversation_id=state["metadata"].get("conversation_id"))
            
            # 更新阶段
            state = StateManager.update_stage(state, "master_agent")
            
            # 构建分析提示
            all_summaries = StateManager.get_all_summaries(state)
            has_info = any(summary for summary in all_summaries.values())
            
            if has_info:
                # 如果已有信息，判断是否足够
                analysis_prompt = f"""
                用户问题：{state['user_question']}
                
                当前已有信息摘要：
                在线搜索：{all_summaries['online'] or '无'}
                知识库：{all_summaries['knowledge'] or '无'}
                LightRAG：{all_summaries['lightrag'] or '无'}
                
                请判断当前信息是否足够回答用户问题。
                
                返回JSON格式：
                {{
                    "decision": "continue" 或 "finish",
                    "reasoning": "决策理由",
                    "confidence": 0.0-1.0
                }}
                """
            else:
                # 如果没有信息，需要收集
                analysis_prompt = f"""
                用户问题：{state['user_question']}
                
                这是一个新的问题，需要收集信息来回答。
                
                返回JSON格式：
                {{
                    "decision": "continue",
                    "reasoning": "需要收集信息来回答用户问题",
                    "confidence": 1.0
                }}
                """
            
            # 调用LLM进行决策
            response = await self.llm_service.generate_json_response(
                analysis_prompt,
                temperature=0.3
            )
            
            decision = response.get("decision", "continue")
            reasoning = response.get("reasoning", "")
            
            # 更新状态
            need_more_info = decision == "continue"
            state = StateManager.set_master_decision(state, decision, need_more_info)
            
            # 记录输出
            output = {
                "decision": decision,
                "reasoning": reasoning,
                "confidence": response.get("confidence", 0.5)
            }
            state = StateManager.record_agent_output(state, "master_agent", output)
            
            self.logger.info(
                "总控制者决策完成",
                decision=decision,
                reasoning=reasoning
            )
            
            return state
            
        except Exception as e:
            self.logger.error(f"总控制者Agent执行失败: {str(e)}")
            # 默认继续收集信息
            state = StateManager.set_master_decision(state, "continue", True)
            return state
    
    async def query_optimizer_node(self, state: AgentState) -> AgentState:
        """
        问题优化Agent节点
        
        Args:
            state: 当前状态
            
        Returns:
            AgentState: 更新后的状态
        """
        try:
            self.logger.info("执行问题优化Agent")
            
            # 更新阶段
            state = StateManager.update_stage(state, "query_optimizer")
            
            # 构建优化提示
            optimization_prompt = f"""
            原始用户问题：{state['user_question']}
            
            请为以下三种检索系统优化查询问题：
            1. online_search - 在线搜索引擎，适合获取最新信息和广泛内容
            2. knowledge_search - 化妆品专业知识库，适合专业技术问题
            3. lightrag_search - 知识图谱检索，适合关联性和推理性问题
            
            为每种检索系统生成最适合的查询问题。
            
            返回JSON格式：
            {{
                "online_search": "优化后的在线搜索问题",
                "knowledge_search": "优化后的知识库搜索问题", 
                "lightrag_search": "优化后的LightRAG搜索问题"
            }}
            """
            
            # 调用LLM优化问题
            response = await self.llm_service.generate_json_response(
                optimization_prompt,
                temperature=0.2
            )
            
            # 更新状态
            optimized_queries = {
                "online_search": response.get("online_search", state['user_question']),
                "knowledge_search": response.get("knowledge_search", state['user_question']),
                "lightrag_search": response.get("lightrag_search", state['user_question'])
            }
            
            state = StateManager.set_optimized_queries(state, optimized_queries)
            
            # 记录输出
            output = {"optimized_queries": optimized_queries}
            state = StateManager.record_agent_output(state, "query_optimizer", output)
            
            self.logger.info("问题优化完成", queries=optimized_queries)
            
            return state
            
        except Exception as e:
            self.logger.error(f"问题优化Agent执行失败: {str(e)}")
            # 使用原始问题作为备选
            default_queries = {
                "online_search": state['user_question'],
                "knowledge_search": state['user_question'],
                "lightrag_search": state['user_question']
            }
            state = StateManager.set_optimized_queries(state, default_queries)
            return state
    
    async def parallel_search_node(self, state: AgentState) -> AgentState:
        """
        并行搜索节点
        
        Args:
            state: 当前状态
            
        Returns:
            AgentState: 更新后的状态
        """
        try:
            self.logger.info("执行并行搜索")
            
            # 更新阶段
            state = StateManager.update_stage(state, "parallel_search")
            
            # 获取优化后的查询
            queries = state["optimized_queries"]
            
            # 创建并行任务
            tasks = []
            
            if "online_search" in queries:
                tasks.append(("online", self._execute_online_search(queries["online_search"])))
            
            if "knowledge_search" in queries:
                tasks.append(("knowledge", self._execute_knowledge_search(queries["knowledge_search"])))
            
            if "lightrag_search" in queries:
                tasks.append(("lightrag", self._execute_lightrag_search(queries["lightrag_search"])))
            
            # 并行执行搜索
            results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
            
            # 处理结果
            search_results = {}
            for i, (search_type, _) in enumerate(tasks):
                result = results[i]
                if isinstance(result, Exception):
                    self.logger.error(f"{search_type}搜索失败: {str(result)}")
                    search_results[search_type] = []
                else:
                    search_results[search_type] = result
                    # 添加到状态
                    state = StateManager.add_search_results(state, search_type, result)
            
            # 记录输出
            output = {"search_results": search_results}
            state = StateManager.record_agent_output(state, "parallel_search", output)
            
            self.logger.info("并行搜索完成", result_counts={k: len(v) for k, v in search_results.items()})
            
            return state
            
        except Exception as e:
            self.logger.error(f"并行搜索执行失败: {str(e)}")
            return state
    
    async def summary_agent_node(self, state: AgentState) -> AgentState:
        """
        摘要Agent节点
        
        Args:
            state: 当前状态
            
        Returns:
            AgentState: 更新后的状态
        """
        try:
            self.logger.info("执行摘要Agent")
            
            # 更新阶段
            state = StateManager.update_stage(state, "summary_agent")
            
            # 获取所有搜索结果
            all_results = StateManager.get_all_search_results(state)
            
            # 为每种类型生成摘要
            summaries = {}
            
            for result_type, results in all_results.items():
                if results:
                    summary = await self._generate_summary(result_type, results, state['user_question'])
                    summaries[result_type] = summary
                else:
                    summaries[result_type] = ""
            
            # 更新状态
            state = StateManager.update_summaries(
                state,
                online_summary=summaries.get("online", ""),
                knowledge_summary=summaries.get("knowledge", ""),
                lightrag_summary=summaries.get("lightrag", "")
            )
            
            # 记录输出
            output = {"summaries": summaries}
            state = StateManager.record_agent_output(state, "summary_agent", output)
            
            self.logger.info("摘要生成完成", summary_lengths={k: len(v) for k, v in summaries.items()})
            
            return state
            
        except Exception as e:
            self.logger.error(f"摘要Agent执行失败: {str(e)}")
            return state
    
    async def final_output_node(self, state: AgentState) -> AgentState:
        """
        最终输出Agent节点
        
        Args:
            state: 当前状态
            
        Returns:
            AgentState: 更新后的状态
        """
        try:
            self.logger.info("执行最终输出Agent")
            
            # 更新阶段
            state = StateManager.update_stage(state, "final_output")
            
            # 构建最终回答提示
            all_summaries = StateManager.get_all_summaries(state)
            
            final_prompt = f"""
            用户问题：{state['user_question']}
            
            基于以下信息源，生成全面准确的回答：
            
            在线搜索信息：{all_summaries['online'] or '无相关信息'}
            
            专业知识库信息：{all_summaries['knowledge'] or '无相关信息'}
            
            知识图谱信息：{all_summaries['lightrag'] or '无相关信息'}
            
            要求：
            1. 直接回答用户问题
            2. 整合多源信息，提供全面回答
            3. 保持专业性和准确性
            4. 如果信息不足，请明确说明
            5. 使用友好的语调
            """
            
            # 生成最终回答
            final_answer = await self.llm_service.generate_response(
                final_prompt,
                temperature=0.7
            )
            
            # 更新状态
            state = StateManager.set_final_answer(state, final_answer)
            
            # 记录输出
            output = {"final_answer": final_answer}
            state = StateManager.record_agent_output(state, "final_output", output)
            
            self.logger.info("最终回答生成完成", answer_length=len(final_answer))
            
            return state
            
        except Exception as e:
            self.logger.error(f"最终输出Agent执行失败: {str(e)}")
            # 设置错误回答
            error_answer = f"抱歉，在处理您的问题时遇到了技术问题。错误信息：{str(e)}"
            state = StateManager.set_final_answer(state, error_answer)
            return state
    
    async def _execute_online_search(self, query: str) -> List[Dict[str, Any]]:
        """执行在线搜索"""
        try:
            results = await self.search_service.search_online(query, num_results=5)
            return [result.to_dict() for result in results]
        except Exception as e:
            self.logger.error(f"在线搜索失败: {str(e)}")
            return []
    
    async def _execute_knowledge_search(self, query: str) -> List[Dict[str, Any]]:
        """执行知识库搜索"""
        try:
            results = await self.knowledge_service.search_cosmetics_knowledge(query, limit=5)
            return [result.to_dict() for result in results]
        except Exception as e:
            self.logger.error(f"知识库搜索失败: {str(e)}")
            return []
    
    async def _execute_lightrag_search(self, query: str) -> List[Dict[str, Any]]:
        """执行LightRAG搜索"""
        try:
            results = await self.lightrag_service.search_lightrag(query, mode="mix")
            return [result.to_dict() for result in results]
        except Exception as e:
            # 更安全的异常消息提取
            try:
                error_detail = str(e)
            except Exception:
                error_detail = f"{type(e).__name__}异常"
            self.logger.error(f"LightRAG搜索失败: {error_detail}")
            return []
    
    async def _generate_summary(self, result_type: str, results: List[Dict[str, Any]], user_question: str) -> str:
        """生成搜索结果摘要"""
        try:
            # 构建摘要提示
            results_text = "\n".join([
                f"标题: {result.get('title', '')}\n内容: {result.get('content', '')}"
                for result in results[:3]  # 只使用前3个结果
            ])
            
            summary_prompt = f"""
            用户问题：{user_question}
            
            {result_type}搜索结果：
            {results_text}
            
            请基于以上搜索结果，生成一个简洁的摘要，重点关注与用户问题相关的信息。
            摘要应该：
            1. 突出关键信息
            2. 保持简洁明了
            3. 与用户问题相关
            """
            
            summary = await self.llm_service.generate_response(
                summary_prompt,
                temperature=0.3,
                max_tokens=500
            )
            
            return summary
            
        except Exception as e:
            self.logger.error(f"生成{result_type}摘要失败: {str(e)}")
            return f"无法生成{result_type}摘要"
