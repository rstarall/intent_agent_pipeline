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
        try:
            # 准备请求数据
            request_data = {
                "query": query,
                "mode": mode,
                "only_need_context": only_need_context
            }
            
            # 准备请求头
            headers = {
                "Content-Type": "application/json"
            }
            
            if self.settings.lightrag_api_key:
                headers["Authorization"] = f"Bearer {self.settings.lightrag_api_key}"
            
            # 发送请求
            session = await self._get_session()
            url = f"{self.settings.lightrag_api_url.rstrip('/')}/query"
            
            async with session.post(
                url,
                headers=headers,
                json=request_data
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"LightRAG API错误 {response.status}: {error_text}")
                
                result = await response.json()
                
                # 解析响应数据
                search_results = []
                
                # LightRAG可能返回不同格式的数据
                if "answer" in result:
                    # 如果有直接答案
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
                
                if "contexts" in result:
                    # 如果有上下文信息
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
                
                if "entities" in result:
                    # 如果有实体信息
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
                
                self.logger.info(
                    "LightRAG检索完成",
                    query=query,
                    mode=mode,
                    result_count=len(search_results)
                )
                
                return search_results
                
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "query": query,
                    "mode": mode,
                    "api_url": self.settings.lightrag_api_url
                }
            )
            raise
    
    async def get_entity_info(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        获取实体详细信息
        
        Args:
            entity_id: 实体ID
            
        Returns:
            Optional[Dict[str, Any]]: 实体信息
        """
        try:
            # 准备请求头
            headers = {}
            if self.settings.lightrag_api_key:
                headers["Authorization"] = f"Bearer {self.settings.lightrag_api_key}"
            
            # 发送请求
            session = await self._get_session()
            url = f"{self.settings.lightrag_api_url.rstrip('/')}/entity/{entity_id}"
            
            async with session.get(url, headers=headers) as response:
                
                if response.status == 404:
                    return None
                
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"LightRAG API错误 {response.status}: {error_text}")
                
                result = await response.json()
                
                self.logger.info(
                    "获取实体信息成功",
                    entity_id=entity_id
                )
                
                return result
                
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "entity_id": entity_id,
                    "api_url": self.settings.lightrag_api_url
                }
            )
            raise
    
    async def get_relation_info(self, relation_id: str) -> Optional[Dict[str, Any]]:
        """
        获取关系详细信息
        
        Args:
            relation_id: 关系ID
            
        Returns:
            Optional[Dict[str, Any]]: 关系信息
        """
        try:
            # 准备请求头
            headers = {}
            if self.settings.lightrag_api_key:
                headers["Authorization"] = f"Bearer {self.settings.lightrag_api_key}"
            
            # 发送请求
            session = await self._get_session()
            url = f"{self.settings.lightrag_api_url.rstrip('/')}/relation/{relation_id}"
            
            async with session.get(url, headers=headers) as response:
                
                if response.status == 404:
                    return None
                
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"LightRAG API错误 {response.status}: {error_text}")
                
                result = await response.json()
                
                self.logger.info(
                    "获取关系信息成功",
                    relation_id=relation_id
                )
                
                return result
                
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "relation_id": relation_id,
                    "api_url": self.settings.lightrag_api_url
                }
            )
            raise
    
    async def get_graph_stats(self) -> Dict[str, Any]:
        """
        获取知识图谱统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        try:
            # 准备请求头
            headers = {}
            if self.settings.lightrag_api_key:
                headers["Authorization"] = f"Bearer {self.settings.lightrag_api_key}"
            
            # 发送请求
            session = await self._get_session()
            url = f"{self.settings.lightrag_api_url.rstrip('/')}/stats"
            
            async with session.get(url, headers=headers) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"LightRAG API错误 {response.status}: {error_text}")
                
                result = await response.json()
                
                self.logger.info("获取图谱统计信息成功")
                
                return result
                
        except Exception as e:
            self.logger.error_with_context(e, {})
            raise
    
    async def health_check(self) -> bool:
        """
        检查LightRAG服务健康状态
        
        Returns:
            bool: 服务是否健康
        """
        try:
            session = await self._get_session()
            url = f"{self.settings.lightrag_api_url.rstrip('/')}/health"
            
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                return response.status == 200
                
        except Exception:
            return False
