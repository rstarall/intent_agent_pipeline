"""
LightRAG服务模块

提供LightRAG知识图谱检索和推理服务。
"""

from typing import Dict, List, Optional, Any
import aiohttp
import json

from ..config import get_settings, get_logger
from ..models import SearchResult, LightRagModeType


class LightRagService:
    """LightRAG检索服务"""
    
    def __init__(self):
        """初始化LightRAG服务"""
        self.settings = get_settings()
        self.logger = get_logger("LightRagService")
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取HTTP会话"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.settings.lightrag_timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def close(self):
        """关闭HTTP会话"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def search_lightrag(
        self,
        query: str,
        mode: LightRagModeType = "mix",
        only_need_context: bool = False
    ) -> List[SearchResult]:
        """
        执行LightRAG检索
        
        Args:
            query: 检索查询
            mode: 检索模式 (naive, local, global, hybrid, mix)
            only_need_context: 是否只需要上下文
            
        Returns:
            List[SearchResult]: 检索结果列表
        """
        # 检查配置
        if not self.settings.lightrag_api_url:
            raise Exception("LightRAG API URL未配置")
        
        try:
            # 准备请求数据
            request_data = {
                "query": query,
                "mode": mode,
                "only_need_context": only_need_context
            }
            
            # 准备请求头（无需认证）
            headers = {"Content-Type": "application/json"}
            
            # 发送请求
            session = await self._get_session()
            url = f"{self.settings.lightrag_api_url.rstrip('/')}/query"
            
            self.logger.info(f"请求LightRAG API: {url}")
            
            async with session.post(url, headers=headers, json=request_data) as response:
                response_text = await response.text()
                
                if response.status != 200:
                    self.logger.error(f"LightRAG API错误 {response.status}: {response_text}")
                    raise Exception(f"LightRAG API错误 {response.status}: {response_text}")
                
                # 解析响应
                result = json.loads(response_text) if response_text else {}
                
                return self._parse_search_results(result, mode, query)
                
        except aiohttp.ClientError as e:
            error_msg = f"LightRAG API连接失败: {str(e)}"
            self.logger.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            # 如果是我们已经抛出的异常，直接重新抛出
            if "LightRAG API" in str(e):
                raise
            # 其他未知异常
            error_msg = f"LightRAG检索失败: {str(e)}"
            self.logger.error(error_msg)
            raise Exception(error_msg)
    
    def _parse_search_results(self, result: Dict, mode: str, query: str) -> List[SearchResult]:
        """解析搜索结果"""
        search_results = []
        
        # 处理新格式响应
        if "response" in result:
            content = result["response"]
            references = self._extract_references(content)
            
            search_result = SearchResult(
                title="LightRAG知识图谱回答",
                content=content,
                source="lightrag",
                score=1.0,
                metadata={
                    "mode": mode,
                    "references": references,
                    "query": query
                }
            )
            search_results.append(search_result)
        
        # 处理旧格式响应
        elif "answer" in result:
            search_result = SearchResult(
                title="LightRAG回答",
                content=result["answer"],
                source="lightrag",
                score=1.0,
                metadata={
                    "mode": mode,
                    "context_used": result.get("context_used", False),
                    "reasoning_path": result.get("reasoning_path", [])
                }
            )
            search_results.append(search_result)
        
        # 处理上下文信息
        if "contexts" in result:
            for i, context in enumerate(result["contexts"]):
                search_result = SearchResult(
                    title=f"上下文 {i+1}",
                    content=context.get("content", ""),
                    source="lightrag_context",
                    score=context.get("score", 0.0),
                    metadata={
                        "mode": mode,
                        "entity_type": context.get("entity_type"),
                        "relation_type": context.get("relation_type"),
                        "context_id": context.get("id")
                    }
                )
                search_results.append(search_result)
        
        # 处理实体信息
        if "entities" in result:
            for entity in result["entities"]:
                search_result = SearchResult(
                    title=f"实体: {entity.get('name', '')}",
                    content=entity.get("description", ""),
                    source="lightrag_entity",
                    score=entity.get("relevance", 0.0),
                    metadata={
                        "mode": mode,
                        "entity_type": entity.get("type"),
                        "entity_id": entity.get("id"),
                        "properties": entity.get("properties", {})
                    }
                )
                search_results.append(search_result)
        
        # 检查是否有有效数据
        if not search_results:
            self.logger.warning(f"LightRAG API响应中没有找到有效数据: {result}")
        
        self.logger.info(f"LightRAG检索完成: {len(search_results)}个结果")
        return search_results
    
    def _extract_references(self, content: str) -> List[str]:
        """提取引用信息"""
        references = []
        if "References" in content:
            ref_start = content.find("References")
            if ref_start > 0:
                references_text = content[ref_start:]
                import re
                ref_pattern = r'\* \[DC\] (.+?)(?:\n|$)'
                matches = re.findall(ref_pattern, references_text)
                references = matches
        return references
    
    async def get_entity_info(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """获取实体详细信息"""
        try:
            session = await self._get_session()
            url = f"{self.settings.lightrag_api_url.rstrip('/')}/entity/{entity_id}"
            
            async with session.get(url) as response:
                if response.status == 404:
                    return None
                
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"LightRAG API错误 {response.status}: {error_text}")
                
                result = await response.json()
                self.logger.info(f"获取实体信息成功: {entity_id}")
                return result
                
        except Exception as e:
            self.logger.error(f"获取实体信息失败: {str(e)}")
            raise
    
    async def get_relation_info(self, relation_id: str) -> Optional[Dict[str, Any]]:
        """获取关系详细信息"""
        try:
            session = await self._get_session()
            url = f"{self.settings.lightrag_api_url.rstrip('/')}/relation/{relation_id}"
            
            async with session.get(url) as response:
                if response.status == 404:
                    return None
                
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"LightRAG API错误 {response.status}: {error_text}")
                
                result = await response.json()
                self.logger.info(f"获取关系信息成功: {relation_id}")
                return result
                
        except Exception as e:
            self.logger.error(f"获取关系信息失败: {str(e)}")
            raise
    
    async def get_graph_stats(self) -> Dict[str, Any]:
        """获取知识图谱统计信息"""
        try:
            session = await self._get_session()
            url = f"{self.settings.lightrag_api_url.rstrip('/')}/stats"
            
            async with session.get(url) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"LightRAG API错误 {response.status}: {error_text}")
                
                result = await response.json()
                self.logger.info("获取图谱统计信息成功")
                return result
                
        except Exception as e:
            self.logger.error(f"获取图谱统计信息失败: {str(e)}")
            raise
    
    async def health_check(self) -> bool:
        """检查LightRAG服务健康状态"""
        try:
            session = await self._get_session()
            url = f"{self.settings.lightrag_api_url.rstrip('/')}/health"
            
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                return response.status == 200
                
        except Exception:
            return False
