"""
错误处理增强模块

提供鲁棒性和错误隔离功能，确保并行任务不会相互影响
"""

import asyncio
import traceback
import uuid
from typing import Dict, Any, Optional, List, Callable, Union
from datetime import datetime
from functools import wraps
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
import threading

from ..config import get_logger
from ..models import StreamResponse, APIResponse


class ConversationTaskManager:
    """对话任务管理器 - 防止任务间相互影响"""
    
    def __init__(self, max_concurrent_tasks: int = 3):
        self.max_concurrent_tasks = max_concurrent_tasks
        self.active_tasks: Dict[str, Dict[str, Any]] = {}
        self.task_locks: Dict[str, threading.Lock] = {}
        self.global_lock = threading.Lock()
        self.logger = get_logger("ConversationTaskManager")
    
    def create_task_context(self, conversation_id: str, user_id: str) -> Dict[str, Any]:
        """创建任务上下文"""
        with self.global_lock:
            if conversation_id not in self.active_tasks:
                self.active_tasks[conversation_id] = {
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "status": "pending",
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                    "error_count": 0,
                    "last_error": None,
                    "is_streaming": False,
                    "stream_active": False
                }
                self.task_locks[conversation_id] = threading.Lock()
            
            return self.active_tasks[conversation_id].copy()
    
    def update_task_status(self, conversation_id: str, status: str, error: Optional[str] = None):
        """更新任务状态"""
        with self.global_lock:
            if conversation_id in self.active_tasks:
                self.active_tasks[conversation_id]["status"] = status
                self.active_tasks[conversation_id]["updated_at"] = datetime.now()
                
                if error:
                    self.active_tasks[conversation_id]["error_count"] += 1
                    self.active_tasks[conversation_id]["last_error"] = error
    
    def get_task_lock(self, conversation_id: str) -> threading.Lock:
        """获取任务锁"""
        with self.global_lock:
            if conversation_id not in self.task_locks:
                self.task_locks[conversation_id] = threading.Lock()
            return self.task_locks[conversation_id]
    
    def cleanup_task(self, conversation_id: str):
        """清理任务"""
        with self.global_lock:
            if conversation_id in self.active_tasks:
                del self.active_tasks[conversation_id]
            if conversation_id in self.task_locks:
                del self.task_locks[conversation_id]
    
    def get_task_statistics(self) -> Dict[str, Any]:
        """获取任务统计"""
        with self.global_lock:
            stats = {
                "total_tasks": len(self.active_tasks),
                "pending_tasks": sum(1 for task in self.active_tasks.values() if task["status"] == "pending"),
                "running_tasks": sum(1 for task in self.active_tasks.values() if task["status"] == "running"),
                "completed_tasks": sum(1 for task in self.active_tasks.values() if task["status"] == "completed"),
                "error_tasks": sum(1 for task in self.active_tasks.values() if task["status"] == "error"),
                "streaming_tasks": sum(1 for task in self.active_tasks.values() if task["is_streaming"]),
                "total_errors": sum(task["error_count"] for task in self.active_tasks.values()),
                "timestamp": datetime.now().isoformat()
            }
            return stats


# 全局任务管理器实例
task_manager = ConversationTaskManager()


class ErrorHandler:
    """错误处理器"""
    
    def __init__(self, conversation_id: str):
        self.conversation_id = conversation_id
        self.logger = get_logger(f"ErrorHandler-{conversation_id}")
    
    def handle_error(self, error: Exception, context: Dict[str, Any] = None) -> StreamResponse:
        """处理错误并返回标准化响应"""
        error_id = str(uuid.uuid4())
        error_msg = str(error)
        
        # 记录错误
        self.logger.error_with_context(
            error,
            {
                "error_id": error_id,
                "conversation_id": self.conversation_id,
                "context": context or {},
                "traceback": traceback.format_exc()
            }
        )
        
        # 更新任务状态
        task_manager.update_task_status(self.conversation_id, "error", error_msg)
        
        # 确定错误类型和代码
        error_code = self._determine_error_code(error)
        
        # 返回错误响应
        return StreamResponse.create_error_response(
            conversation_id=self.conversation_id,
            error_code=error_code,
            error_message=error_msg,
            metadata={"error_id": error_id}
        )
    
    def _determine_error_code(self, error: Exception) -> str:
        """确定错误代码"""
        error_type = type(error).__name__
        
        error_code_mapping = {
            "ValueError": "VALIDATION_ERROR",
            "TimeoutError": "TIMEOUT_ERROR",
            "ConnectionError": "CONNECTION_ERROR",
            "HTTPException": "HTTP_ERROR",
            "KeyError": "MISSING_KEY_ERROR",
            "TypeError": "TYPE_ERROR",
            "RuntimeError": "RUNTIME_ERROR",
            "FileNotFoundError": "FILE_NOT_FOUND_ERROR",
            "PermissionError": "PERMISSION_ERROR"
        }
        
        return error_code_mapping.get(error_type, "UNKNOWN_ERROR")


def robust_async_wrapper(func: Callable) -> Callable:
    """异步函数鲁棒性包装器"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        conversation_id = kwargs.get("conversation_id") or "unknown"
        error_handler = ErrorHandler(conversation_id)
        
        try:
            # 创建任务上下文
            task_manager.create_task_context(conversation_id, kwargs.get("user_id", "unknown"))
            
            # 获取任务锁
            task_lock = task_manager.get_task_lock(conversation_id)
            
            # 在锁保护下执行
            with task_lock:
                task_manager.update_task_status(conversation_id, "running")
                result = await func(*args, **kwargs)
                task_manager.update_task_status(conversation_id, "completed")
                return result
        
        except Exception as e:
            error_response = error_handler.handle_error(e, {
                "function": func.__name__,
                "args": str(args),
                "kwargs": str(kwargs)
            })
            
            # 对于生成器函数，返回错误响应
            if hasattr(func, "__name__") and "stream" in func.__name__:
                async def error_generator():
                    yield error_response
                return error_generator()
            else:
                raise
    
    return wrapper


def robust_sync_wrapper(func: Callable) -> Callable:
    """同步函数鲁棒性包装器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        conversation_id = kwargs.get("conversation_id") or "unknown"
        error_handler = ErrorHandler(conversation_id)
        
        try:
            # 创建任务上下文
            task_manager.create_task_context(conversation_id, kwargs.get("user_id", "unknown"))
            
            # 获取任务锁
            task_lock = task_manager.get_task_lock(conversation_id)
            
            # 在锁保护下执行
            with task_lock:
                task_manager.update_task_status(conversation_id, "running")
                result = func(*args, **kwargs)
                task_manager.update_task_status(conversation_id, "completed")
                return result
        
        except Exception as e:
            error_response = error_handler.handle_error(e, {
                "function": func.__name__,
                "args": str(args),
                "kwargs": str(kwargs)
            })
            
            # 对于API响应，返回错误响应
            if hasattr(func, "__name__") and "api" in func.__name__.lower():
                return APIResponse.error_response(
                    message=error_response.error_message,
                    error_code=error_response.error_code
                )
            else:
                raise
    
    return wrapper


@asynccontextmanager
async def conversation_context(conversation_id: str, user_id: str):
    """对话上下文管理器"""
    error_handler = ErrorHandler(conversation_id)
    
    try:
        # 创建任务上下文
        task_context = task_manager.create_task_context(conversation_id, user_id)
        
        # 获取任务锁
        task_lock = task_manager.get_task_lock(conversation_id)
        
        with task_lock:
            task_manager.update_task_status(conversation_id, "running")
            yield task_context
            task_manager.update_task_status(conversation_id, "completed")
    
    except Exception as e:
        error_handler.handle_error(e, {"operation": "conversation_context"})
        raise
    
    finally:
        # 如果任务已完成，清理资源
        if conversation_id in task_manager.active_tasks:
            task_status = task_manager.active_tasks[conversation_id]["status"]
            if task_status in ["completed", "error", "cancelled"]:
                task_manager.cleanup_task(conversation_id)


class CircuitBreaker:
    """熔断器 - 防止错误传播"""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
        self.lock = threading.Lock()
    
    def call(self, func: Callable, *args, **kwargs):
        """调用受保护的函数"""
        with self.lock:
            if self.state == "open":
                if self._should_attempt_reset():
                    self.state = "half-open"
                else:
                    raise Exception("Circuit breaker is open")
            
            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            except Exception as e:
                self._on_failure()
                raise
    
    def _should_attempt_reset(self) -> bool:
        """判断是否应该尝试重置"""
        if self.last_failure_time is None:
            return True
        
        return (datetime.now() - self.last_failure_time).seconds > self.timeout
    
    def _on_success(self):
        """成功时的处理"""
        self.failure_count = 0
        self.state = "closed"
    
    def _on_failure(self):
        """失败时的处理"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"


class RateLimiter:
    """速率限制器 - 防止过度请求"""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[datetime]] = {}
        self.lock = threading.Lock()
    
    def is_allowed(self, identifier: str) -> bool:
        """检查是否允许请求"""
        with self.lock:
            now = datetime.now()
            
            # 初始化或清理过期请求
            if identifier not in self.requests:
                self.requests[identifier] = []
            
            # 移除过期请求
            self.requests[identifier] = [
                req_time for req_time in self.requests[identifier]
                if (now - req_time).seconds < self.window_seconds
            ]
            
            # 检查是否超过限制
            if len(self.requests[identifier]) >= self.max_requests:
                return False
            
            # 记录新请求
            self.requests[identifier].append(now)
            return True
    
    def get_remaining_requests(self, identifier: str) -> int:
        """获取剩余请求数"""
        with self.lock:
            if identifier not in self.requests:
                return self.max_requests
            
            return max(0, self.max_requests - len(self.requests[identifier]))


# 全局熔断器和速率限制器
circuit_breaker = CircuitBreaker()
rate_limiter = RateLimiter()


def get_error_handling_statistics() -> Dict[str, Any]:
    """获取错误处理统计"""
    task_stats = task_manager.get_task_statistics()
    
    circuit_stats = {
        "circuit_breaker_state": circuit_breaker.state,
        "circuit_failure_count": circuit_breaker.failure_count,
        "circuit_last_failure": circuit_breaker.last_failure_time.isoformat() if circuit_breaker.last_failure_time else None
    }
    
    rate_limit_stats = {
        "active_rate_limit_entries": len(rate_limiter.requests)
    }
    
    return {
        "task_statistics": task_stats,
        "circuit_breaker": circuit_stats,
        "rate_limiting": rate_limit_stats,
        "timestamp": datetime.now().isoformat()
    }


# 装饰器导出
__all__ = [
    "robust_async_wrapper",
    "robust_sync_wrapper",
    "conversation_context",
    "ErrorHandler",
    "ConversationTaskManager",
    "CircuitBreaker",
    "RateLimiter",
    "task_manager",
    "circuit_breaker",
    "rate_limiter",
    "get_error_handling_statistics"
] 