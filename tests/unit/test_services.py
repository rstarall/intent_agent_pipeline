"""
服务层单元测试

测试各种外部服务的功能。
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import aiohttp
import json

from app.services import LLMService, KnowledgeService, LightRagService, SearchService
from app.models import SearchResult, Message


class TestLLMService:
    """LLM服务测试"""
    
    @pytest.fixture
    def llm_service(self):
        """LLM服务实例"""
        return LLMService()
    
    @pytest.mark.asyncio
    async def test_generate_response(self, llm_service):
        """测试生成响应"""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "choices": [{"message": {"content": "测试响应"}}]
        })
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await llm_service.generate_response("测试提示")
            
            assert result == "测试响应"
            mock_post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_json_response(self, llm_service):
        """测试生成JSON响应"""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "choices": [{"message": {"content": '{"result": "success"}'}}]
        })
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await llm_service.generate_json_response("测试提示")
            
            assert result == {"result": "success"}
    
    @pytest.mark.asyncio
    async def test_generate_stream_response(self, llm_service):
        """测试生成流式响应"""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.content = AsyncMock()
        
        # 模拟流式数据
        stream_data = [
            'data: {"choices": [{"delta": {"content": "测试"}}]}\n\n'.encode('utf-8'),
            'data: {"choices": [{"delta": {"content": "流式"}}]}\n\n'.encode('utf-8'),
            'data: {"choices": [{"delta": {"content": "响应"}}]}\n\n'.encode('utf-8'),
            b'data: [DONE]\n\n'
        ]
        
        mock_response.content.__aiter__.return_value = stream_data
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = []
            async for chunk in llm_service.generate_stream_response("测试提示"):
                result.append(chunk)
            
            assert "测试" in result
            assert "流式" in result
            assert "响应" in result
    
    @pytest.mark.asyncio
    async def test_api_error(self, llm_service):
        """测试API错误处理"""
        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal Server Error")
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.return_value.__aenter__.return_value = mock_response
            
            with pytest.raises(Exception) as exc_info:
                await llm_service.generate_response("测试提示")
            
            assert "OpenAI API错误 500" in str(exc_info.value)


class TestKnowledgeService:
    """知识库服务测试"""
    
    @pytest.fixture
    def knowledge_service(self):
        """知识库服务实例"""
        return KnowledgeService()
    
    @pytest.mark.asyncio
    async def test_search_cosmetics_knowledge(self, knowledge_service):
        """测试搜索化妆品知识"""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "results": [
                {
                    "title": "透明质酸介绍",
                    "content": "透明质酸是一种保湿成分...",
                    "score": 0.9,
                    "category": "成分",
                    "id": "knowledge_1"
                }
            ]
        })
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.return_value.__aenter__.return_value = mock_response
            
            results = await knowledge_service.search_cosmetics_knowledge("透明质酸")
            
            assert len(results) == 1
            assert isinstance(results[0], SearchResult)
            assert results[0].title == "透明质酸介绍"
            assert results[0].source == "knowledge_base"
    
    @pytest.mark.asyncio
    async def test_get_knowledge_by_id(self, knowledge_service):
        """测试根据ID获取知识"""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "id": "knowledge_1",
            "title": "透明质酸",
            "content": "详细内容...",
            "category": "成分"
        })
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_response
            
            result = await knowledge_service.get_knowledge_by_id("knowledge_1")
            
            assert result["id"] == "knowledge_1"
            assert result["title"] == "透明质酸"
    
    @pytest.mark.asyncio
    async def test_knowledge_not_found(self, knowledge_service):
        """测试知识不存在"""
        mock_response = MagicMock()
        mock_response.status = 404
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_response
            
            result = await knowledge_service.get_knowledge_by_id("nonexistent")
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_health_check(self, knowledge_service):
        """测试健康检查"""
        mock_response = MagicMock()
        mock_response.status = 200
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_response
            
            result = await knowledge_service.health_check()
            
            assert result is True


class TestLightRagService:
    """LightRAG服务测试"""
    
    @pytest.fixture
    def lightrag_service(self):
        """LightRAG服务实例"""
        return LightRagService()
    
    @pytest.mark.asyncio
    async def test_search_lightrag(self, lightrag_service):
        """测试LightRAG搜索"""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "answer": "透明质酸是一种天然保湿成分...",
            "contexts": [
                {
                    "content": "透明质酸的分子结构...",
                    "score": 0.8,
                    "entity_type": "成分"
                }
            ],
            "entities": [
                {
                    "name": "透明质酸",
                    "type": "化学成分",
                    "description": "保湿成分",
                    "relevance": 0.9
                }
            ]
        })
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.return_value.__aenter__.return_value = mock_response
            
            results = await lightrag_service.search_lightrag("透明质酸", mode="mix")
            
            assert len(results) >= 1
            assert any(result.title == "LightRAG回答" for result in results)
            assert any(result.source == "lightrag" for result in results)
    
    @pytest.mark.asyncio
    async def test_get_entity_info(self, lightrag_service):
        """测试获取实体信息"""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "id": "entity_1",
            "name": "透明质酸",
            "type": "化学成分",
            "properties": {"分子量": "高"}
        })
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_response
            
            result = await lightrag_service.get_entity_info("entity_1")
            
            assert result["name"] == "透明质酸"
            assert result["type"] == "化学成分"


class TestSearchService:
    """搜索服务测试"""
    
    @pytest.fixture
    def search_service(self):
        """搜索服务实例"""
        return SearchService()
    
    @pytest.mark.asyncio
    async def test_search_online(self, search_service):
        """测试在线搜索"""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "items": [
                {
                    "title": "透明质酸的作用",
                    "snippet": "透明质酸具有强大的保湿能力...",
                    "link": "https://example.com/hyaluronic-acid",
                    "displayLink": "example.com"
                }
            ]
        })
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_response
            
            results = await search_service.search_online("透明质酸")
            
            assert len(results) == 1
            assert isinstance(results[0], SearchResult)
            assert results[0].title == "透明质酸的作用"
            assert results[0].source == "online_search"
    
    @pytest.mark.asyncio
    async def test_search_news(self, search_service):
        """测试新闻搜索"""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "items": [
                {
                    "title": "化妆品行业最新动态",
                    "snippet": "最新的化妆品技术发展...",
                    "link": "https://news.example.com/cosmetics",
                    "displayLink": "news.example.com"
                }
            ]
        })
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_response
            
            results = await search_service.search_news("化妆品", time_range="d")
            
            assert len(results) == 1
            assert results[0].source == "news_search"
    
    @pytest.mark.asyncio
    async def test_mock_search_results(self, search_service):
        """测试模拟搜索结果"""
        # 当没有API密钥时，应该返回模拟结果
        search_service.settings.search_engine_api_key = None
        
        results = await search_service.search_online("测试查询")
        
        assert len(results) > 0
        assert all(result.source == "mock_search" for result in results)
        assert all(result.metadata.get("is_mock") is True for result in results)
    
    @pytest.mark.asyncio
    async def test_health_check_with_api_key(self, search_service):
        """测试有API密钥时的健康检查"""
        search_service.settings.search_engine_api_key = "test_key"
        
        mock_response = MagicMock()
        mock_response.status = 200
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_response
            
            result = await search_service.health_check()
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_health_check_without_api_key(self, search_service):
        """测试没有API密钥时的健康检查"""
        search_service.settings.search_engine_api_key = None
        
        result = await search_service.health_check()
        
        assert result is True  # 模拟模式总是健康的
