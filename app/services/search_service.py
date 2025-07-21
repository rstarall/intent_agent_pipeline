"""
搜索服务模块

提供在线搜索引擎服务。
"""

from typing import Dict, List, Optional, Any
import aiohttp
import json
from urllib.parse import quote

from ..config import get_settings, get_logger
from ..models import SearchResult


class SearchService:
    """在线搜索服务"""
    
    def __init__(self):
        """初始化搜索服务"""
        self.settings = get_settings()
        self.logger = get_logger("SearchService")
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取HTTP会话"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.settings.search_timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def close(self):
        """关闭HTTP会话"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def search_online(
        self,
        query: str,
        num_results: Optional[int] = None,
        language: str = "zh-CN",
        safe_search: str = "moderate"
    ) -> List[SearchResult]:
        """
        执行在线搜索
        
        Args:
            query: 搜索查询
            num_results: 结果数量
            language: 搜索语言
            safe_search: 安全搜索级别
            
        Returns:
            List[SearchResult]: 搜索结果列表
        """
        try:
            # 优先使用 SearXNG
            if self.settings.searxng_url:
                return await self._search_with_searxng(query, num_results, language)
            
            if not self.settings.search_engine_api_key:
                # 如果没有配置API密钥，返回模拟结果
                return await self._mock_search_results(query)
            
            num_results = num_results or self.settings.search_max_results
            
            # 准备请求参数
            params = {
                "q": query,
                "num": min(num_results, 10),  # 限制最大结果数
                "hl": language,
                "safe": safe_search,
                "key": self.settings.search_engine_api_key
            }
            
            # 发送请求
            session = await self._get_session()
            
            async with session.get(
                self.settings.search_engine_url,
                params=params
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"搜索引擎API错误 {response.status}: {error_text}")
                
                result = await response.json()
                
                # 解析搜索结果
                search_results = []
                
                if "items" in result:
                    for item in result["items"]:
                        search_result = SearchResult(
                            title=item.get("title", ""),
                            content=item.get("snippet", ""),
                            url=item.get("link", ""),
                            source="online_search",
                            score=1.0,  # 在线搜索结果默认分数
                            metadata={
                                "display_link": item.get("displayLink", ""),
                                "formatted_url": item.get("formattedUrl", ""),
                                "cache_id": item.get("cacheId"),
                                "page_map": item.get("pagemap", {}),
                                "search_engine": "google"
                            }
                        )
                        search_results.append(search_result)
                
                self.logger.info(
                    "在线搜索完成",
                    query=query,
                    result_count=len(search_results),
                    num_results=num_results
                )
                
                return search_results
                
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "query": query,
                    "num_results": num_results,
                    "search_url": self.settings.search_engine_url
                }
            )
            
            # 如果搜索失败，返回模拟结果
            return await self._mock_search_results(query)
    
    async def _mock_search_results(self, query: str) -> List[SearchResult]:
        """
        生成模拟搜索结果（用于测试或API不可用时）
        
        Args:
            query: 搜索查询
            
        Returns:
            List[SearchResult]: 模拟搜索结果
        """
        mock_results = [
            SearchResult(
                title=f"关于'{query}'的搜索结果1",
                content=f"这是关于{query}的详细信息。由于搜索API不可用，这是一个模拟结果。",
                url="",  # 不提供虚假URL
                source="mock_search",
                score=0.9,
                metadata={
                    "is_mock": True,
                    "query": query,
                    "note": "模拟数据，无真实URL"
                }
            ),
            SearchResult(
                title=f"'{query}'相关信息2",
                content=f"更多关于{query}的信息。这个结果展示了相关的背景知识和应用场景。",
                url="",  # 不提供虚假URL
                source="mock_search",
                score=0.8,
                metadata={
                    "is_mock": True,
                    "query": query,
                    "note": "模拟数据，无真实URL"
                }
            ),
            SearchResult(
                title=f"{query}的专业解析",
                content=f"专业角度分析{query}的特点、用途和注意事项。包含详细的技术说明。",
                url="",  # 不提供虚假URL
                source="mock_search",
                score=0.7,
                metadata={
                    "is_mock": True,
                    "query": query,
                    "note": "模拟数据，无真实URL"
                }
            )
        ]
        
        self.logger.warning(
            "使用模拟搜索结果",
            query=query,
            reason="搜索API不可用或未配置"
        )
        
        return mock_results
    
    async def search_news(
        self,
        query: str,
        num_results: Optional[int] = None,
        time_range: str = "d"  # d=day, w=week, m=month, y=year
    ) -> List[SearchResult]:
        """
        搜索新闻内容
        
        Args:
            query: 搜索查询
            num_results: 结果数量
            time_range: 时间范围
            
        Returns:
            List[SearchResult]: 新闻搜索结果
        """
        try:
            if not self.settings.search_engine_api_key:
                return await self._mock_news_results(query)
            
            num_results = num_results or self.settings.search_max_results
            
            # 准备新闻搜索参数
            params = {
                "q": query,
                "num": min(num_results, 10),
                "tbm": "nws",  # 新闻搜索
                "tbs": f"qdr:{time_range}",  # 时间范围
                "key": self.settings.search_engine_api_key
            }
            
            # 发送请求
            session = await self._get_session()
            
            async with session.get(
                self.settings.search_engine_url,
                params=params
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"新闻搜索API错误 {response.status}: {error_text}")
                
                result = await response.json()
                
                # 解析新闻结果
                search_results = []
                
                if "items" in result:
                    for item in result["items"]:
                        search_result = SearchResult(
                            title=item.get("title", ""),
                            content=item.get("snippet", ""),
                            url=item.get("link", ""),
                            source="news_search",
                            score=1.0,
                            metadata={
                                "display_link": item.get("displayLink", ""),
                                "formatted_url": item.get("formattedUrl", ""),
                                "page_map": item.get("pagemap", {}),
                                "news_source": item.get("displayLink", ""),
                                "time_range": time_range
                            }
                        )
                        search_results.append(search_result)
                
                self.logger.info(
                    "新闻搜索完成",
                    query=query,
                    result_count=len(search_results),
                    time_range=time_range
                )
                
                return search_results
                
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "query": query,
                    "num_results": num_results,
                    "time_range": time_range
                }
            )
            
            return await self._mock_news_results(query)
    
    async def _mock_news_results(self, query: str) -> List[SearchResult]:
        """生成模拟新闻结果"""
        mock_results = [
            SearchResult(
                title=f"最新：{query}行业动态",
                content=f"最新报道显示，{query}领域出现了新的发展趋势。专家分析认为这将对行业产生重要影响。",
                url="",  # 不提供虚假URL
                source="mock_news",
                score=0.9,
                metadata={
                    "is_mock": True,
                    "news_type": "industry",
                    "query": query,
                    "note": "模拟数据，无真实URL"
                }
            ),
            SearchResult(
                title=f"{query}市场分析报告",
                content=f"根据最新市场调研，{query}市场呈现出稳定增长的态势。消费者需求持续上升。",
                url="",  # 不提供虚假URL
                source="mock_news",
                score=0.8,
                metadata={
                    "is_mock": True,
                    "news_type": "market",
                    "query": query,
                    "note": "模拟数据，无真实URL"
                }
            )
        ]
        
        return mock_results
    
    async def _search_with_searxng(
        self,
        query: str,
        num_results: Optional[int] = None,
        language: Optional[str] = None
    ) -> List[SearchResult]:
        """
        使用 SearXNG 进行搜索
        
        Args:
            query: 搜索查询
            num_results: 结果数量
            language: 搜索语言
            
        Returns:
            List[SearchResult]: 搜索结果列表
        """
        try:
            num_results = num_results or self.settings.search_max_results
            language = language or self.settings.searxng_language
            
            # 构建 SearXNG 请求参数
            params = {
                'q': query.strip(),
                'format': 'json',
                'language': language,
                'safesearch': self.settings.searxng_safesearch,
                'categories': self.settings.searxng_categories
            }
            
            # 添加时间范围（如果配置了）
            if self.settings.searxng_time_range:
                params['time_range'] = self.settings.searxng_time_range
            
            # 发送请求
            session = await self._get_session()
            url = f"{self.settings.searxng_url}/search"
            
            self.logger.info(
                "开始 SearXNG 搜索",
                query=query,
                url=url,
                params=params
            )
            
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    error_text = await response.text()
                    self.logger.error(f"SearXNG API 错误 {response.status}: {error_text}")
                    # 如果 SearXNG 失败，回退到模拟结果
                    return await self._mock_search_results(query)
                
                result = await response.json()
                
                # 解析 SearXNG 响应
                search_results = []
                results = result.get("results", [])
                
                # 限制结果数量
                for i, item in enumerate(results[:num_results]):
                    # 处理内容，清理多余空白
                    content = item.get("content", "").strip()
                    if content:
                        content = ' '.join(content.split())
                        # 限制内容长度
                        if len(content) > 300:
                            content = content[:300] + "..."
                    
                    search_result = SearchResult(
                        title=item.get("title", "无标题").strip(),
                        content=content or "无描述内容",
                        url=item.get("url", ""),
                        source="searxng",
                        score=1.0 - (i * 0.1),  # 根据排序位置计算分数
                        metadata={
                            "engine": item.get("engine", "unknown"),
                            "category": item.get("category", self.settings.searxng_categories),
                            "publishedDate": item.get("publishedDate"),
                            "search_query": query,
                            "position": i + 1
                        }
                    )
                    search_results.append(search_result)
                
                self.logger.info(
                    "SearXNG 搜索完成",
                    query=query,
                    result_count=len(search_results),
                    total_results=result.get("number_of_results", 0)
                )
                
                # 如果没有结果，返回提示信息
                if not search_results:
                    return [SearchResult(
                        title="未找到相关搜索结果",
                        content=f"抱歉，没有找到与 '{query}' 相关的搜索结果。请尝试其他关键词。",
                        url="",
                        source="searxng",
                        score=0.0,
                        metadata={"is_empty": True}
                    )]
                
                return search_results
                
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "query": query,
                    "searxng_url": self.settings.searxng_url,
                    "num_results": num_results
                }
            )
            # 如果出错，返回模拟结果
            return await self._mock_search_results(query)
    
    async def health_check(self) -> bool:
        """
        检查搜索服务健康状态
        
        Returns:
            bool: 服务是否健康
        """
        try:
            if not self.settings.search_engine_api_key:
                return True  # 模拟模式总是健康的
            
            session = await self._get_session()
            
            # 执行简单的测试搜索
            params = {
                "q": "test",
                "num": 1,
                "key": self.settings.search_engine_api_key
            }
            
            async with session.get(
                self.settings.search_engine_url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                return response.status == 200
                
        except Exception:
            return False
