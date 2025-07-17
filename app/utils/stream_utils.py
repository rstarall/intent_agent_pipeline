"""
流式处理工具模块

提供流式数据处理相关的工具函数。
"""

import asyncio
import json
from typing import AsyncIterator, Any, Dict, Optional, Callable, TypeVar
from datetime import datetime

T = TypeVar('T')


class StreamBuffer:
    """流式缓冲器"""
    
    def __init__(self, max_size: int = 1024):
        """
        初始化缓冲器
        
        Args:
            max_size: 最大缓冲区大小
        """
        self.max_size = max_size
        self.buffer = ""
        self.overflow = False
    
    def add(self, data: str) -> str:
        """
        添加数据到缓冲区
        
        Args:
            data: 要添加的数据
            
        Returns:
            str: 可以输出的完整数据
        """
        self.buffer += data
        
        # 检查是否超出最大大小
        if len(self.buffer) > self.max_size:
            self.overflow = True
            # 保留最后的数据
            self.buffer = self.buffer[-self.max_size:]
        
        # 查找完整的行或句子
        output = ""
        lines = self.buffer.split('\n')
        
        if len(lines) > 1:
            # 有完整的行
            output = '\n'.join(lines[:-1]) + '\n'
            self.buffer = lines[-1]
        
        return output
    
    def flush(self) -> str:
        """
        刷新缓冲区，返回所有剩余数据
        
        Returns:
            str: 剩余的所有数据
        """
        output = self.buffer
        self.buffer = ""
        self.overflow = False
        return output
    
    def is_empty(self) -> bool:
        """检查缓冲区是否为空"""
        return len(self.buffer) == 0


class StreamChunker:
    """流式分块器"""
    
    def __init__(self, chunk_size: int = 1024):
        """
        初始化分块器
        
        Args:
            chunk_size: 块大小
        """
        self.chunk_size = chunk_size
    
    async def chunk_stream(self, stream: AsyncIterator[str]) -> AsyncIterator[str]:
        """
        将流分块
        
        Args:
            stream: 输入流
            
        Yields:
            str: 分块后的数据
        """
        buffer = ""
        
        async for data in stream:
            buffer += data
            
            while len(buffer) >= self.chunk_size:
                chunk = buffer[:self.chunk_size]
                buffer = buffer[self.chunk_size:]
                yield chunk
        
        # 输出剩余数据
        if buffer:
            yield buffer


class StreamFormatter:
    """流式格式化器"""
    
    @staticmethod
    def format_sse(data: Dict[str, Any], event: Optional[str] = None) -> str:
        """
        格式化为Server-Sent Events格式
        
        Args:
            data: 要发送的数据
            event: 事件类型
            
        Returns:
            str: SSE格式的字符串
        """
        lines = []
        
        if event:
            lines.append(f"event: {event}")
        
        json_data = json.dumps(data, ensure_ascii=False)
        lines.append(f"data: {json_data}")
        lines.append("")  # 空行表示消息结束
        
        return "\n".join(lines) + "\n"
    
    @staticmethod
    def format_json_stream(data: Dict[str, Any]) -> str:
        """
        格式化为JSON流格式
        
        Args:
            data: 要发送的数据
            
        Returns:
            str: JSON格式的字符串
        """
        return json.dumps(data, ensure_ascii=False) + "\n"
    
    @staticmethod
    def format_text_stream(text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        格式化为文本流格式
        
        Args:
            text: 文本内容
            metadata: 元数据
            
        Returns:
            str: 格式化后的文本
        """
        if metadata:
            header = json.dumps(metadata, ensure_ascii=False)
            return f"[META]{header}[/META]{text}"
        return text


class StreamProcessor:
    """流式处理器"""
    
    def __init__(self, buffer_size: int = 1024):
        """
        初始化处理器
        
        Args:
            buffer_size: 缓冲区大小
        """
        self.buffer_size = buffer_size
        self.processors: list[Callable[[str], str]] = []
    
    def add_processor(self, processor: Callable[[str], str]):
        """
        添加处理函数
        
        Args:
            processor: 处理函数
        """
        self.processors.append(processor)
    
    async def process_stream(self, stream: AsyncIterator[str]) -> AsyncIterator[str]:
        """
        处理流数据
        
        Args:
            stream: 输入流
            
        Yields:
            str: 处理后的数据
        """
        async for data in stream:
            processed_data = data
            
            # 应用所有处理器
            for processor in self.processors:
                processed_data = processor(processed_data)
            
            if processed_data:  # 只输出非空数据
                yield processed_data


class StreamMerger:
    """流式合并器"""
    
    def __init__(self):
        """初始化合并器"""
        self.streams: list[AsyncIterator[T]] = []
    
    def add_stream(self, stream: AsyncIterator[T]):
        """
        添加流
        
        Args:
            stream: 要添加的流
        """
        self.streams.append(stream)
    
    async def merge(self) -> AsyncIterator[T]:
        """
        合并所有流
        
        Yields:
            T: 合并后的数据
        """
        if not self.streams:
            return
        
        # 创建任务
        tasks = []
        for i, stream in enumerate(self.streams):
            task = asyncio.create_task(self._stream_to_queue(stream, i))
            tasks.append(task)
        
        # 创建结果队列
        result_queue = asyncio.Queue()
        
        # 启动合并任务
        merge_task = asyncio.create_task(
            self._merge_streams(tasks, result_queue)
        )
        
        try:
            # 输出合并结果
            while True:
                try:
                    item = await asyncio.wait_for(result_queue.get(), timeout=0.1)
                    if item is None:  # 结束标记
                        break
                    yield item
                except asyncio.TimeoutError:
                    if merge_task.done():
                        break
                    continue
        finally:
            # 清理任务
            merge_task.cancel()
            for task in tasks:
                task.cancel()
    
    async def _stream_to_queue(self, stream: AsyncIterator[T], stream_id: int):
        """将流数据放入队列"""
        try:
            async for item in stream:
                yield (stream_id, item)
        except Exception as e:
            yield (stream_id, e)
    
    async def _merge_streams(self, tasks: list, result_queue: asyncio.Queue):
        """合并流任务"""
        try:
            async for stream_id, item in asyncio.as_completed(tasks):
                if isinstance(item, Exception):
                    continue  # 忽略异常
                await result_queue.put(item)
        finally:
            await result_queue.put(None)  # 结束标记


class StreamRateLimiter:
    """流式速率限制器"""
    
    def __init__(self, rate: float, burst: int = 1):
        """
        初始化速率限制器
        
        Args:
            rate: 每秒允许的请求数
            burst: 突发请求数
        """
        self.rate = rate
        self.burst = burst
        self.tokens = burst
        self.last_update = asyncio.get_event_loop().time()
    
    async def acquire(self) -> bool:
        """
        获取令牌
        
        Returns:
            bool: 是否获取成功
        """
        now = asyncio.get_event_loop().time()
        
        # 添加令牌
        elapsed = now - self.last_update
        self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
        self.last_update = now
        
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        
        return False
    
    async def wait(self):
        """等待直到可以获取令牌"""
        while not await self.acquire():
            await asyncio.sleep(0.01)


async def stream_with_timeout(
    stream: AsyncIterator[T],
    timeout: float,
    default: Optional[T] = None
) -> AsyncIterator[T]:
    """
    为流添加超时控制
    
    Args:
        stream: 输入流
        timeout: 超时时间
        default: 超时时的默认值
        
    Yields:
        T: 流数据或默认值
    """
    async for item in stream:
        try:
            yield await asyncio.wait_for(
                asyncio.coroutine(lambda: item)(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            if default is not None:
                yield default
            break


async def stream_with_retry(
    stream_factory: Callable[[], AsyncIterator[T]],
    max_retries: int = 3,
    delay: float = 1.0
) -> AsyncIterator[T]:
    """
    为流添加重试机制
    
    Args:
        stream_factory: 创建流的工厂函数
        max_retries: 最大重试次数
        delay: 重试延迟
        
    Yields:
        T: 流数据
    """
    for attempt in range(max_retries + 1):
        try:
            stream = stream_factory()
            async for item in stream:
                yield item
            break  # 成功完成
        except Exception as e:
            if attempt == max_retries:
                raise
            await asyncio.sleep(delay * (2 ** attempt))  # 指数退避
