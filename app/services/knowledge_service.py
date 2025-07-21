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
        threshold: float = 0.5,
        api_url: Optional[str] = None
    ) -> List[SearchResult]:
        """
        搜索化妆品知识库
        
        Args:
            query: 搜索查询
            limit: 结果数量限制
            threshold: 相关性阈值
            api_url: 可选的API URL，如果不提供则使用配置中的URL
            
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
            
            # 使用传入的API URL或默认配置
            url = api_url or self.settings.knowledge_api_url
            
            # 检查URL是否配置
            if not url:
                raise Exception("知识库API URL未配置")
            
            self.logger.info(f"准备请求知识库API: {url}")
            
            # 发送请求
            session = await self._get_session()
            
            async with session.post(
                url,
                headers=headers,
                json=request_data
            ) as response:
                
                response_text = await response.text()
                
                if response.status != 200:
                    self.logger.error(f"知识库API返回错误状态码: {response.status}, 响应: {response_text}")
                    raise Exception(f"知识库API错误 {response.status}: {response_text}")
                
                # 尝试解析JSON
                try:
                    result = json.loads(response_text) if response_text else {}
                except json.JSONDecodeError:
                    self.logger.error(f"知识库API返回无效的JSON: {response_text}")
                    raise Exception(f"知识库API返回无效的JSON响应")
                
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
                else:
                    # 如果没有results字段，记录警告
                    self.logger.warning(
                        f"知识库API响应中没有results字段",
                        response=result,
                        query=query
                    )
                
                self.logger.info(
                    "知识库搜索完成",
                    query=query,
                    result_count=len(search_results),
                    limit=limit,
                    has_results_field="results" in result
                )
                
                # 如果没有找到任何结果且响应中没有明确的空结果标识，可能是API问题
                if len(search_results) == 0 and "results" not in result:
                    self.logger.warning("知识库API可能未正常工作，返回了空响应")
                
                return search_results
                
        except aiohttp.ClientError as e:
            error_msg = f"知识库API连接失败: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error_with_context(
                e,
                {
                    "query": query,
                    "limit": limit,
                    "api_url": url,
                    "error_type": "connection_error"
                }
            )
            raise Exception(error_msg)
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "query": query,
                    "limit": limit,
                    "api_url": url
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
    
    async def get_knowledge_bases(
        self,
        token: str,
        api_url: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取知识库列表
        
        Args:
            token: 用户认证token
            api_url: 可选的API基础URL，如果不提供则使用配置中的URL
            
        Returns:
            List[Dict[str, Any]]: 知识库列表
        """
        try:
            # 准备请求头
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            # 使用传入的API URL或默认配置
            base_url = api_url or self.settings.openwebui_base_url
            
            # 检查URL是否配置
            if not base_url:
                raise Exception("知识库API URL未配置")
            
            # 发送请求
            session = await self._get_session()
            url = f"{base_url.rstrip('/')}/api/v1/knowledge/"
            
            self.logger.info(f"准备请求知识库列表API: {url}")
            
            async with session.get(url, headers=headers) as response:
                
                response_text = await response.text()
                
                if response.status != 200:
                    self.logger.error(f"知识库列表API返回错误状态码: {response.status}, 响应: {response_text}")
                    raise Exception(f"知识库列表API错误 {response.status}: {response_text}")
                
                # 尝试解析JSON
                try:
                    result = json.loads(response_text) if response_text else []
                except json.JSONDecodeError:
                    self.logger.error(f"知识库列表API返回无效的JSON: {response_text}")
                    raise Exception(f"知识库列表API返回无效的JSON响应")
                
                self.logger.info(
                    "获取知识库列表成功",
                    knowledge_base_count=len(result)
                )
                
                return result
                
        except aiohttp.ClientError as e:
            error_msg = f"知识库列表API连接失败: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error_with_context(
                e,
                {
                    "api_url": url if 'url' in locals() else 'URL未构建',
                    "error_type": "connection_error"
                }
            )
            raise Exception(error_msg)
        except Exception as e:
            self.logger.error_with_context(e, {})
            raise
    
    async def get_knowledge_base_id_by_name(
        self,
        token: str,
        knowledge_base_name: str,
        api_url: Optional[str] = None
    ) -> Optional[str]:
        """
        根据名称获取知识库ID
        
        Args:
            token: 用户认证token
            knowledge_base_name: 知识库名称
            api_url: 可选的API基础URL
            
        Returns:
            Optional[str]: 知识库ID，如果未找到返回None
        """
        try:
            knowledge_bases = await self.get_knowledge_bases(token, api_url)
            
            for kb in knowledge_bases:
                if kb.get('name') == knowledge_base_name:
                    kb_id = kb.get('id')
                    self.logger.info(f"找到知识库'{knowledge_base_name}'的ID: {kb_id}")
                    return kb_id
            
            self.logger.warning(f"未找到名称为'{knowledge_base_name}'的知识库")
            return None
            
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "knowledge_base_name": knowledge_base_name
                }
            )
            raise
    
    async def query_doc(
        self,
        token: str,
        collection_name: str,
        query: str,
        k: int = 5,
        k_reranker: Optional[int] = None,
        r: Optional[float] = None,
        hybrid: Optional[bool] = None,
        api_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        查询文档集合，符合examples/knowledge_search.py的接口格式
        
        注意：collection_name参数实际上应该是collection_id（知识库ID），
        但为了保持向后兼容性，参数名仍为collection_name。
        
        Args:
            token: 用户认证token
            collection_name: 文档集合ID（知识库ID，不是名称）
            query: 查询内容
            k: 返回结果数量
            k_reranker: 重排序结果数量
            r: 相关性阈值
            hybrid: 是否使用混合搜索
            api_url: 可选的API基础URL，如果不提供则使用配置中的URL
            
        Returns:
            Dict[str, Any]: 查询结果
        """
        try:
            # 准备请求数据
            request_data = {
                "collection_name": collection_name,
                "query": query,
                "k": k
            }
            
            # 不传递 hybrid, k_reranker, r 等参数，因为API不支持
            # if k_reranker is not None:
            #     request_data["k_reranker"] = k_reranker
            # if r is not None:
            #     request_data["r"] = r
            # if hybrid is not None:
            #     request_data["hybrid"] = hybrid
            
            # 准备请求头
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            # 使用传入的API URL或默认配置
            base_url = api_url or self.settings.openwebui_base_url
            
            # 检查URL是否配置
            if not base_url:
                raise Exception("知识库查询API URL未配置")
            
            # 发送请求
            session = await self._get_session()
            url = f"{base_url.rstrip('/')}/api/v1/retrieval/query/doc"
            
            self.logger.info(f"准备请求文档查询API: {url}")
            
            async with session.post(
                url,
                headers=headers,
                json=request_data
            ) as response:
                
                response_text = await response.text()
                
                if response.status != 200:
                    self.logger.error(f"知识库查询API返回错误状态码: {response.status}, 响应: {response_text}")
                    raise Exception(f"知识库查询API错误 {response.status}: {response_text}")
                
                # 尝试解析JSON
                try:
                    result = json.loads(response_text) if response_text else {}
                except json.JSONDecodeError:
                    self.logger.error(f"知识库查询API返回无效的JSON: {response_text}")
                    raise Exception(f"知识库查询API返回无效的JSON响应")
                
                # 计算结果数量
                result_count = 0
                if result.get("documents"):
                    docs = result.get("documents", [])
                    if docs and isinstance(docs[0], list):
                        result_count = len(docs[0])
                
                self.logger.info(
                    "文档查询完成",
                    collection_name=collection_name,
                    query=query,
                    result_count=result_count,
                    has_documents="documents" in result
                )
                
                # 如果没有文档字段，记录警告
                if "documents" not in result:
                    self.logger.warning(
                        "知识库查询API响应中没有documents字段",
                        response=result,
                        collection_name=collection_name,
                        query=query
                    )
                
                return result
                
        except aiohttp.ClientError as e:
            error_msg = f"知识库查询API连接失败: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error_with_context(
                e,
                {
                    "collection_name": collection_name,
                    "query": query,
                    "k": k,
                    "api_url": url if 'url' in locals() else 'URL未构建',
                    "error_type": "connection_error"
                }
            )
            raise Exception(error_msg)
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "collection_name": collection_name,
                    "query": query,
                    "k": k
                }
            )
            raise
    
    async def query_doc_by_name(
        self,
        token: str,
        knowledge_base_name: str,
        query: str,
        k: int = 5,
        k_reranker: Optional[int] = None,
        r: Optional[float] = None,
        hybrid: Optional[bool] = None,
        api_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        根据知识库名称查询文档（会先获取ID）
        
        Args:
            token: 用户认证token
            knowledge_base_name: 知识库名称
            query: 查询内容
            k: 返回结果数量
            k_reranker: 重排序结果数量
            r: 相关性阈值
            hybrid: 是否使用混合搜索
            api_url: 可选的API基础URL
            
        Returns:
            Dict[str, Any]: 查询结果
        """
        try:
            # 先根据名称获取知识库ID
            kb_id = await self.get_knowledge_base_id_by_name(token, knowledge_base_name, api_url)
            
            if not kb_id:
                raise Exception(f"未找到名称为'{knowledge_base_name}'的知识库")
            
            # 使用ID进行查询
            return await self.query_doc(
                token=token,
                collection_name=kb_id,  # 这里使用ID
                query=query,
                k=k,
                k_reranker=k_reranker,
                r=r,
                hybrid=hybrid,
                api_url=api_url
            )
            
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "knowledge_base_name": knowledge_base_name,
                    "query": query
                }
            )
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
