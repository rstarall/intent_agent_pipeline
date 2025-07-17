"""
Redis检查点存储模块

提供基于Redis的LangGraph检查点存储实现。
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
import json
import asyncio

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from ...config import get_settings, get_logger


class RedisCheckpointStore:
    """Redis检查点存储器"""
    
    def __init__(self, redis_url: Optional[str] = None, ttl: int = 3600):
        """
        初始化Redis存储器
        
        Args:
            redis_url: Redis连接URL
            ttl: 检查点过期时间（秒）
        """
        if not REDIS_AVAILABLE:
            raise ImportError("Redis库未安装，请运行: pip install redis")
        
        self.settings = get_settings()
        self.logger = get_logger("RedisCheckpointStore")
        
        self.redis_url = redis_url or self.settings.get_redis_url()
        self.ttl = ttl
        self.redis_client: Optional[redis.Redis] = None
        
        # 键前缀
        self.checkpoint_prefix = "langgraph:checkpoint:"
        self.metadata_prefix = "langgraph:metadata:"
        self.stats_key = "langgraph:stats"
    
    async def _get_client(self) -> redis.Redis:
        """获取Redis客户端"""
        if self.redis_client is None:
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_timeout=self.settings.redis_timeout,
                socket_connect_timeout=self.settings.redis_timeout
            )
        return self.redis_client
    
    async def close(self):
        """关闭Redis连接"""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
    
    def _get_checkpoint_key(self, thread_id: str, checkpoint_id: str) -> str:
        """获取检查点键名"""
        return f"{self.checkpoint_prefix}{thread_id}:{checkpoint_id}"
    
    def _get_metadata_key(self, thread_id: str) -> str:
        """获取元数据键名"""
        return f"{self.metadata_prefix}{thread_id}"
    
    def _get_thread_pattern(self, thread_id: str) -> str:
        """获取线程模式"""
        return f"{self.checkpoint_prefix}{thread_id}:*"
    
    async def save_checkpoint(
        self,
        thread_id: str,
        checkpoint_id: str,
        state: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        保存检查点
        
        Args:
            thread_id: 线程ID
            checkpoint_id: 检查点ID
            state: 状态数据
            metadata: 元数据
            
        Returns:
            bool: 是否保存成功
        """
        try:
            client = await self._get_client()
            
            # 创建检查点数据
            checkpoint_data = {
                "state": state,
                "metadata": metadata or {},
                "created_at": datetime.now().isoformat(),
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id
            }
            
            # 序列化数据
            serialized_data = json.dumps(checkpoint_data, ensure_ascii=False)
            
            # 保存到Redis
            checkpoint_key = self._get_checkpoint_key(thread_id, checkpoint_id)
            await client.setex(checkpoint_key, self.ttl, serialized_data)
            
            # 更新线程元数据
            await self._update_thread_metadata(thread_id)
            
            # 更新统计信息
            await self._update_stats("checkpoint_saved")
            
            self.logger.debug(
                "保存检查点成功",
                thread_id=thread_id,
                checkpoint_id=checkpoint_id,
                key=checkpoint_key
            )
            
            return True
            
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "thread_id": thread_id,
                    "checkpoint_id": checkpoint_id,
                    "operation": "save_checkpoint"
                }
            )
            return False
    
    async def load_checkpoint(
        self,
        thread_id: str,
        checkpoint_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        加载检查点
        
        Args:
            thread_id: 线程ID
            checkpoint_id: 检查点ID
            
        Returns:
            Optional[Dict[str, Any]]: 检查点数据
        """
        try:
            client = await self._get_client()
            
            checkpoint_key = self._get_checkpoint_key(thread_id, checkpoint_id)
            serialized_data = await client.get(checkpoint_key)
            
            if serialized_data:
                checkpoint_data = json.loads(serialized_data)
                
                self.logger.debug(
                    "加载检查点成功",
                    thread_id=thread_id,
                    checkpoint_id=checkpoint_id
                )
                
                return checkpoint_data
            
            self.logger.debug(
                "检查点不存在",
                thread_id=thread_id,
                checkpoint_id=checkpoint_id
            )
            return None
            
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "thread_id": thread_id,
                    "checkpoint_id": checkpoint_id,
                    "operation": "load_checkpoint"
                }
            )
            return None
    
    async def list_checkpoints(self, thread_id: str) -> List[str]:
        """
        列出线程的所有检查点ID
        
        Args:
            thread_id: 线程ID
            
        Returns:
            List[str]: 检查点ID列表
        """
        try:
            client = await self._get_client()
            
            pattern = self._get_thread_pattern(thread_id)
            keys = await client.keys(pattern)
            
            # 提取检查点ID
            checkpoint_ids = []
            prefix_len = len(f"{self.checkpoint_prefix}{thread_id}:")
            
            for key in keys:
                checkpoint_id = key[prefix_len:]
                checkpoint_ids.append(checkpoint_id)
            
            self.logger.debug(
                "列出检查点",
                thread_id=thread_id,
                checkpoint_count=len(checkpoint_ids)
            )
            
            return checkpoint_ids
            
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "thread_id": thread_id,
                    "operation": "list_checkpoints"
                }
            )
            return []
    
    async def delete_checkpoint(self, thread_id: str, checkpoint_id: str) -> bool:
        """
        删除检查点
        
        Args:
            thread_id: 线程ID
            checkpoint_id: 检查点ID
            
        Returns:
            bool: 是否删除成功
        """
        try:
            client = await self._get_client()
            
            checkpoint_key = self._get_checkpoint_key(thread_id, checkpoint_id)
            deleted_count = await client.delete(checkpoint_key)
            
            if deleted_count > 0:
                # 更新线程元数据
                await self._update_thread_metadata(thread_id)
                
                # 更新统计信息
                await self._update_stats("checkpoint_deleted")
                
                self.logger.debug(
                    "删除检查点成功",
                    thread_id=thread_id,
                    checkpoint_id=checkpoint_id
                )
                
                return True
            
            return False
            
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "thread_id": thread_id,
                    "checkpoint_id": checkpoint_id,
                    "operation": "delete_checkpoint"
                }
            )
            return False
    
    async def delete_thread(self, thread_id: str) -> bool:
        """
        删除整个线程的所有检查点
        
        Args:
            thread_id: 线程ID
            
        Returns:
            bool: 是否删除成功
        """
        try:
            client = await self._get_client()
            
            # 获取所有检查点键
            pattern = self._get_thread_pattern(thread_id)
            keys = await client.keys(pattern)
            
            if keys:
                # 删除所有检查点
                deleted_count = await client.delete(*keys)
                
                # 删除元数据
                metadata_key = self._get_metadata_key(thread_id)
                await client.delete(metadata_key)
                
                # 更新统计信息
                await self._update_stats("thread_deleted", deleted_count)
                
                self.logger.info(
                    "删除线程成功",
                    thread_id=thread_id,
                    deleted_checkpoints=deleted_count
                )
                
                return True
            
            return False
            
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "thread_id": thread_id,
                    "operation": "delete_thread"
                }
            )
            return False
    
    async def get_latest_checkpoint(self, thread_id: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        获取线程的最新检查点
        
        Args:
            thread_id: 线程ID
            
        Returns:
            Optional[Tuple[str, Dict[str, Any]]]: (检查点ID, 检查点数据)
        """
        try:
            client = await self._get_client()
            
            # 获取所有检查点
            pattern = self._get_thread_pattern(thread_id)
            keys = await client.keys(pattern)
            
            if not keys:
                return None
            
            # 获取所有检查点数据
            checkpoints = []
            for key in keys:
                serialized_data = await client.get(key)
                if serialized_data:
                    checkpoint_data = json.loads(serialized_data)
                    checkpoints.append((key, checkpoint_data))
            
            if checkpoints:
                # 按创建时间排序，获取最新的
                latest_key, latest_data = max(
                    checkpoints,
                    key=lambda x: x[1]["created_at"]
                )
                
                # 提取检查点ID
                prefix_len = len(f"{self.checkpoint_prefix}{thread_id}:")
                checkpoint_id = latest_key[prefix_len:]
                
                return checkpoint_id, latest_data
            
            return None
            
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "thread_id": thread_id,
                    "operation": "get_latest_checkpoint"
                }
            )
            return None
    
    async def _update_thread_metadata(self, thread_id: str):
        """更新线程元数据"""
        try:
            client = await self._get_client()
            
            # 获取检查点数量
            pattern = self._get_thread_pattern(thread_id)
            keys = await client.keys(pattern)
            checkpoint_count = len(keys)
            
            # 更新元数据
            metadata = {
                "checkpoint_count": checkpoint_count,
                "last_updated": datetime.now().isoformat()
            }
            
            metadata_key = self._get_metadata_key(thread_id)
            serialized_metadata = json.dumps(metadata, ensure_ascii=False)
            await client.setex(metadata_key, self.ttl, serialized_metadata)
            
        except Exception as e:
            self.logger.error(f"更新线程元数据失败: {str(e)}")
    
    async def _update_stats(self, operation: str, count: int = 1):
        """更新统计信息"""
        try:
            client = await self._get_client()
            
            # 使用Redis哈希存储统计信息
            await client.hincrby(self.stats_key, operation, count)
            await client.hset(self.stats_key, "last_updated", datetime.now().isoformat())
            
            # 设置过期时间
            await client.expire(self.stats_key, self.ttl * 24)  # 24小时过期
            
        except Exception as e:
            self.logger.error(f"更新统计信息失败: {str(e)}")
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        获取存储统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        try:
            client = await self._get_client()
            
            stats = await client.hgetall(self.stats_key)
            
            return {
                "checkpoint_saved": int(stats.get("checkpoint_saved", 0)),
                "checkpoint_deleted": int(stats.get("checkpoint_deleted", 0)),
                "thread_deleted": int(stats.get("thread_deleted", 0)),
                "last_updated": stats.get("last_updated"),
                "current_time": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error_with_context(e, {"operation": "get_statistics"})
            return {}
    
    async def health_check(self) -> bool:
        """
        检查Redis连接健康状态
        
        Returns:
            bool: 是否健康
        """
        try:
            client = await self._get_client()
            await client.ping()
            return True
        except Exception:
            return False
