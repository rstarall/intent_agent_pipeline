"""
知识库服务模块

提供化妆品专业知识库检索服务。
"""

from typing import Dict, List, Optional, Any
import aiohttp
import json

from ..config import get_settings, get_logger
from ..models import SearchResult


class KnowledgeService:
    """化妆品知识库服务"""
    
    def __init__(self):
        """初始化知识库服务"""
        self.settings = get_settings()
        self.logger = get_logger("KnowledgeService")
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取HTTP会话"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.settings.knowledge_timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def close(self):
        """关闭HTTP会话"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def search_cosmetics_knowledge(
        self,
        query: str,
        limit: int = 10,
        threshold: float = 0.5
    ) -> List[SearchResult]:
        """
        搜索化妆品知识库
        
        Args:
            query: 搜索查询
            limit: 结果数量限制
            threshold: 相关性阈值
            
        Returns:
            List[SearchResult]: 搜索结果列表
        """
        try:
            # 准备请求数据
            request_data = {
                "query": query,
                "limit": limit,
                "threshold": threshold
            }
            
            # 准备请求头
            headers = {
                "Content-Type": "application/json"
            }
            
            if self.settings.knowledge_api_key:
                headers["Authorization"] = f"Bearer {self.settings.knowledge_api_key}"
            
            # 发送请求
            session = await self._get_session()
            
            async with session.post(
                self.settings.knowledge_api_url,
                headers=headers,
                json=request_data
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"知识库API错误 {response.status}: {error_text}")
                
                result = await response.json()
                
                # 解析响应数据
                search_results = []
                
                if "results" in result:
                    for item in result["results"]:
                        search_result = SearchResult(
                            title=item.get("title", ""),
                            content=item.get("content", ""),
                            url=item.get("url"),
                            score=item.get("score", 0.0),
                            source="knowledge_base",
                            metadata={
                                "category": item.get("category"),
                                "tags": item.get("tags", []),
                                "confidence": item.get("confidence", 0.0),
                                "knowledge_id": item.get("id")
                            }
                        )
                        search_results.append(search_result)
                
                self.logger.info(
                    "知识库搜索完成",
                    query=query,
                    result_count=len(search_results),
                    limit=limit
                )
                
                return search_results
                
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "query": query,
                    "limit": limit,
                    "api_url": self.settings.knowledge_api_url
                }
            )
            raise
    
    async def get_knowledge_by_id(self, knowledge_id: str) -> Optional[Dict[str, Any]]:
        """
        根据ID获取知识条目
        
        Args:
            knowledge_id: 知识条目ID
            
        Returns:
            Optional[Dict[str, Any]]: 知识条目详情
        """
        try:
            # 准备请求头
            headers = {}
            if self.settings.knowledge_api_key:
                headers["Authorization"] = f"Bearer {self.settings.knowledge_api_key}"
            
            # 发送请求
            session = await self._get_session()
            url = f"{self.settings.knowledge_api_url.rstrip('/')}/{knowledge_id}"
            
            async with session.get(url, headers=headers) as response:
                
                if response.status == 404:
                    return None
                
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"知识库API错误 {response.status}: {error_text}")
                
                result = await response.json()
                
                self.logger.info(
                    "获取知识条目成功",
                    knowledge_id=knowledge_id
                )
                
                return result
                
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "knowledge_id": knowledge_id,
                    "api_url": self.settings.knowledge_api_url
                }
            )
            raise
    
    async def search_by_category(
        self,
        category: str,
        query: Optional[str] = None,
        limit: int = 10
    ) -> List[SearchResult]:
        """
        按分类搜索知识库
        
        Args:
            category: 知识分类
            query: 可选的搜索查询
            limit: 结果数量限制
            
        Returns:
            List[SearchResult]: 搜索结果列表
        """
        try:
            # 准备请求数据
            request_data = {
                "category": category,
                "limit": limit
            }
            
            if query:
                request_data["query"] = query
            
            # 准备请求头
            headers = {
                "Content-Type": "application/json"
            }
            
            if self.settings.knowledge_api_key:
                headers["Authorization"] = f"Bearer {self.settings.knowledge_api_key}"
            
            # 发送请求
            session = await self._get_session()
            url = f"{self.settings.knowledge_api_url.rstrip('/')}/category"
            
            async with session.post(
                url,
                headers=headers,
                json=request_data
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"知识库API错误 {response.status}: {error_text}")
                
                result = await response.json()
                
                # 解析响应数据
                search_results = []
                
                if "results" in result:
                    for item in result["results"]:
                        search_result = SearchResult(
                            title=item.get("title", ""),
                            content=item.get("content", ""),
                            url=item.get("url"),
                            score=item.get("score", 0.0),
                            source="knowledge_base",
                            metadata={
                                "category": item.get("category"),
                                "tags": item.get("tags", []),
                                "confidence": item.get("confidence", 0.0),
                                "knowledge_id": item.get("id")
                            }
                        )
                        search_results.append(search_result)
                
                self.logger.info(
                    "分类搜索完成",
                    category=category,
                    query=query,
                    result_count=len(search_results)
                )
                
                return search_results
                
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "category": category,
                    "query": query,
                    "limit": limit
                }
            )
            raise
    
    async def get_categories(self) -> List[str]:
        """
        获取可用的知识分类
        
        Returns:
            List[str]: 分类列表
        """
        try:
            # 准备请求头
            headers = {}
            if self.settings.knowledge_api_key:
                headers["Authorization"] = f"Bearer {self.settings.knowledge_api_key}"
            
            # 发送请求
            session = await self._get_session()
            url = f"{self.settings.knowledge_api_url.rstrip('/')}/categories"
            
            async with session.get(url, headers=headers) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"知识库API错误 {response.status}: {error_text}")
                
                result = await response.json()
                categories = result.get("categories", [])
                
                self.logger.info(
                    "获取分类列表成功",
                    category_count=len(categories)
                )
                
                return categories
                
        except Exception as e:
            self.logger.error_with_context(e, {})
            raise
    
    async def health_check(self) -> bool:
        """
        检查知识库服务健康状态
        
        Returns:
            bool: 服务是否健康
        """
        try:
            session = await self._get_session()
            url = f"{self.settings.knowledge_api_url.rstrip('/')}/health"
            
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                return response.status == 200
                
        except Exception:
            return False
