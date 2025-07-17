"""
内存检查点存储模块

提供基于内存的LangGraph检查点存储实现。
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import json
import threading
from collections import defaultdict

from ...config import get_logger


class MemoryCheckpointStore:
    """内存检查点存储器"""
    
    def __init__(self):
        """初始化内存存储器"""
        self.logger = get_logger("MemoryCheckpointStore")
        
        # 存储结构：{thread_id: {checkpoint_id: checkpoint_data}}
        self._checkpoints: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
        
        # 存储元数据：{thread_id: metadata}
        self._metadata: Dict[str, Dict[str, Any]] = {}
        
        # 线程锁
        self._lock = threading.RLock()
        
        # 统计信息
        self._stats = {
            "total_checkpoints": 0,
            "total_threads": 0,
            "created_at": datetime.now().isoformat()
        }
    
    def save_checkpoint(
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
            with self._lock:
                # 创建检查点数据
                checkpoint_data = {
                    "state": state,
                    "metadata": metadata or {},
                    "created_at": datetime.now().isoformat(),
                    "thread_id": thread_id,
                    "checkpoint_id": checkpoint_id
                }
                
                # 保存检查点
                if thread_id not in self._checkpoints:
                    self._stats["total_threads"] += 1
                
                self._checkpoints[thread_id][checkpoint_id] = checkpoint_data
                self._stats["total_checkpoints"] += 1
                
                # 更新线程元数据
                if thread_id not in self._metadata:
                    self._metadata[thread_id] = {
                        "created_at": datetime.now().isoformat(),
                        "checkpoint_count": 0
                    }
                
                self._metadata[thread_id]["checkpoint_count"] += 1
                self._metadata[thread_id]["last_updated"] = datetime.now().isoformat()
                
                self.logger.debug(
                    "保存检查点成功",
                    thread_id=thread_id,
                    checkpoint_id=checkpoint_id,
                    state_keys=list(state.keys()) if state else []
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
    
    def load_checkpoint(
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
            with self._lock:
                if thread_id in self._checkpoints:
                    checkpoint_data = self._checkpoints[thread_id].get(checkpoint_id)
                    
                    if checkpoint_data:
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
    
    def list_checkpoints(self, thread_id: str) -> List[str]:
        """
        列出线程的所有检查点ID
        
        Args:
            thread_id: 线程ID
            
        Returns:
            List[str]: 检查点ID列表
        """
        try:
            with self._lock:
                if thread_id in self._checkpoints:
                    checkpoint_ids = list(self._checkpoints[thread_id].keys())
                    
                    self.logger.debug(
                        "列出检查点",
                        thread_id=thread_id,
                        checkpoint_count=len(checkpoint_ids)
                    )
                    
                    return checkpoint_ids
                
                return []
                
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "thread_id": thread_id,
                    "operation": "list_checkpoints"
                }
            )
            return []
    
    def delete_checkpoint(self, thread_id: str, checkpoint_id: str) -> bool:
        """
        删除检查点
        
        Args:
            thread_id: 线程ID
            checkpoint_id: 检查点ID
            
        Returns:
            bool: 是否删除成功
        """
        try:
            with self._lock:
                if thread_id in self._checkpoints:
                    if checkpoint_id in self._checkpoints[thread_id]:
                        del self._checkpoints[thread_id][checkpoint_id]
                        self._stats["total_checkpoints"] -= 1
                        
                        # 更新元数据
                        if thread_id in self._metadata:
                            self._metadata[thread_id]["checkpoint_count"] -= 1
                            self._metadata[thread_id]["last_updated"] = datetime.now().isoformat()
                        
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
    
    def delete_thread(self, thread_id: str) -> bool:
        """
        删除整个线程的所有检查点
        
        Args:
            thread_id: 线程ID
            
        Returns:
            bool: 是否删除成功
        """
        try:
            with self._lock:
                if thread_id in self._checkpoints:
                    checkpoint_count = len(self._checkpoints[thread_id])
                    del self._checkpoints[thread_id]
                    
                    self._stats["total_checkpoints"] -= checkpoint_count
                    self._stats["total_threads"] -= 1
                    
                    # 删除元数据
                    if thread_id in self._metadata:
                        del self._metadata[thread_id]
                    
                    self.logger.info(
                        "删除线程成功",
                        thread_id=thread_id,
                        deleted_checkpoints=checkpoint_count
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
    
    def get_latest_checkpoint(self, thread_id: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        获取线程的最新检查点
        
        Args:
            thread_id: 线程ID
            
        Returns:
            Optional[Tuple[str, Dict[str, Any]]]: (检查点ID, 检查点数据)
        """
        try:
            with self._lock:
                if thread_id in self._checkpoints:
                    checkpoints = self._checkpoints[thread_id]
                    
                    if checkpoints:
                        # 按创建时间排序，获取最新的
                        latest_id = max(
                            checkpoints.keys(),
                            key=lambda cid: checkpoints[cid]["created_at"]
                        )
                        
                        return latest_id, checkpoints[latest_id]
                
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
    
    def get_thread_metadata(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """
        获取线程元数据
        
        Args:
            thread_id: 线程ID
            
        Returns:
            Optional[Dict[str, Any]]: 线程元数据
        """
        try:
            with self._lock:
                return self._metadata.get(thread_id)
                
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "thread_id": thread_id,
                    "operation": "get_thread_metadata"
                }
            )
            return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取存储统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        try:
            with self._lock:
                return {
                    **self._stats,
                    "current_time": datetime.now().isoformat(),
                    "memory_usage": {
                        "threads": len(self._checkpoints),
                        "total_checkpoints": sum(
                            len(checkpoints) for checkpoints in self._checkpoints.values()
                        )
                    }
                }
                
        except Exception as e:
            self.logger.error_with_context(e, {"operation": "get_statistics"})
            return {}
    
    def clear_all(self) -> bool:
        """
        清空所有数据
        
        Returns:
            bool: 是否清空成功
        """
        try:
            with self._lock:
                self._checkpoints.clear()
                self._metadata.clear()
                
                self._stats = {
                    "total_checkpoints": 0,
                    "total_threads": 0,
                    "created_at": datetime.now().isoformat()
                }
                
                self.logger.info("清空所有检查点数据")
                return True
                
        except Exception as e:
            self.logger.error_with_context(e, {"operation": "clear_all"})
            return False
