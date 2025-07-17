"""
异步工具函数模块

提供异步编程相关的工具函数。
"""

import asyncio
from typing import Any, Awaitable, List, Optional, TypeVar, Callable
from functools import wraps
import time

T = TypeVar('T')


async def run_with_timeout(
    coro: Awaitable[T],
    timeout: float,
    default: Optional[T] = None
) -> T:
    """
    运行协程并设置超时
    
    Args:
        coro: 协程对象
        timeout: 超时时间（秒）
        default: 超时时返回的默认值
        
    Returns:
        T: 协程结果或默认值
        
    Raises:
        asyncio.TimeoutError: 如果超时且没有默认值
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        if default is not None:
            return default
        raise


async def gather_with_concurrency(
    *awaitables: Awaitable[T],
    limit: int = 10,
    return_exceptions: bool = False
) -> List[T]:
    """
    并发执行协程，限制并发数量
    
    Args:
        *awaitables: 协程对象列表
        limit: 最大并发数
        return_exceptions: 是否返回异常
        
    Returns:
        List[T]: 结果列表
    """
    semaphore = asyncio.Semaphore(limit)
    
    async def _run_with_semaphore(awaitable: Awaitable[T]) -> T:
        async with semaphore:
            return await awaitable
    
    tasks = [_run_with_semaphore(awaitable) for awaitable in awaitables]
    return await asyncio.gather(*tasks, return_exceptions=return_exceptions)


def async_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    异步重试装饰器
    
    Args:
        max_attempts: 最大重试次数
        delay: 初始延迟时间
        backoff: 退避倍数
        exceptions: 需要重试的异常类型
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts - 1:
                        raise
                    
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
            
            # 这行代码实际上不会执行，但为了类型检查
            raise RuntimeError("重试失败")
        
        return wrapper
    return decorator


class AsyncContextManager:
    """异步上下文管理器基类"""
    
    async def __aenter__(self):
        """进入上下文"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出上下文"""
        pass


class AsyncTimer(AsyncContextManager):
    """异步计时器上下文管理器"""
    
    def __init__(self, name: str = "Timer"):
        """
        初始化计时器
        
        Args:
            name: 计时器名称
        """
        self.name = name
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
    
    async def __aenter__(self):
        """开始计时"""
        self.start_time = time.time()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """结束计时"""
        self.end_time = time.time()
    
    @property
    def elapsed(self) -> float:
        """获取经过的时间"""
        if self.start_time is None:
            return 0.0
        
        end_time = self.end_time or time.time()
        return end_time - self.start_time


class AsyncBatch:
    """异步批处理器"""
    
    def __init__(self, batch_size: int = 10, max_wait: float = 1.0):
        """
        初始化批处理器
        
        Args:
            batch_size: 批处理大小
            max_wait: 最大等待时间
        """
        self.batch_size = batch_size
        self.max_wait = max_wait
        self.items: List[Any] = []
        self.futures: List[asyncio.Future] = []
        self.last_batch_time = time.time()
        self._lock = asyncio.Lock()
        self._batch_task: Optional[asyncio.Task] = None
    
    async def add_item(self, item: Any) -> Any:
        """
        添加项目到批处理
        
        Args:
            item: 要处理的项目
            
        Returns:
            Any: 处理结果
        """
        async with self._lock:
            future = asyncio.Future()
            self.items.append(item)
            self.futures.append(future)
            
            # 如果达到批处理大小或者是第一个项目，立即处理
            if len(self.items) >= self.batch_size or len(self.items) == 1:
                if self._batch_task is None or self._batch_task.done():
                    self._batch_task = asyncio.create_task(self._process_batch())
            
            return await future
    
    async def _process_batch(self):
        """处理批次"""
        await asyncio.sleep(0.01)  # 短暂等待，允许更多项目加入
        
        async with self._lock:
            if not self.items:
                return
            
            current_items = self.items.copy()
            current_futures = self.futures.copy()
            self.items.clear()
            self.futures.clear()
            self.last_batch_time = time.time()
        
        try:
            # 这里应该实现实际的批处理逻辑
            results = await self._batch_process(current_items)
            
            # 设置结果
            for future, result in zip(current_futures, results):
                if not future.done():
                    future.set_result(result)
                    
        except Exception as e:
            # 设置异常
            for future in current_futures:
                if not future.done():
                    future.set_exception(e)
    
    async def _batch_process(self, items: List[Any]) -> List[Any]:
        """
        实际的批处理逻辑（需要子类实现）
        
        Args:
            items: 要处理的项目列表
            
        Returns:
            List[Any]: 处理结果列表
        """
        # 默认实现：直接返回项目
        return items


async def async_map(
    func: Callable[[T], Awaitable[Any]],
    items: List[T],
    concurrency: int = 10
) -> List[Any]:
    """
    异步映射函数
    
    Args:
        func: 异步处理函数
        items: 要处理的项目列表
        concurrency: 并发数
        
    Returns:
        List[Any]: 处理结果列表
    """
    semaphore = asyncio.Semaphore(concurrency)
    
    async def _process_item(item: T) -> Any:
        async with semaphore:
            return await func(item)
    
    tasks = [_process_item(item) for item in items]
    return await asyncio.gather(*tasks)


async def async_filter(
    func: Callable[[T], Awaitable[bool]],
    items: List[T],
    concurrency: int = 10
) -> List[T]:
    """
    异步过滤函数
    
    Args:
        func: 异步判断函数
        items: 要过滤的项目列表
        concurrency: 并发数
        
    Returns:
        List[T]: 过滤后的项目列表
    """
    semaphore = asyncio.Semaphore(concurrency)
    
    async def _check_item(item: T) -> tuple[T, bool]:
        async with semaphore:
            result = await func(item)
            return item, result
    
    tasks = [_check_item(item) for item in items]
    results = await asyncio.gather(*tasks)
    
    return [item for item, passed in results if passed]
