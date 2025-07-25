"""
日志中间件模块

记录HTTP请求和响应信息。
"""

import time
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ...config import get_logger


class LoggingMiddleware(BaseHTTPMiddleware):
    """HTTP请求日志中间件"""
    
    def __init__(self, app):
        """初始化中间件"""
        super().__init__(app)
        self.logger = get_logger("http_middleware")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        处理HTTP请求
        
        Args:
            request: HTTP请求
            call_next: 下一个处理器
            
        Returns:
            Response: HTTP响应
        """
        # 生成请求ID
        request_id = str(uuid.uuid4())
        
        # 记录请求开始时间
        start_time = time.time()
        
        # 提取请求信息
        method = request.method
        url = str(request.url)
        path = request.url.path
        query_params = dict(request.query_params)
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        # 仅在非健康检查路径上记录请求开始
        is_health_check = path.startswith("/api/v1/health")
        if not is_health_check:
            self.logger.info(
                "HTTP请求开始",
                request_id=request_id,
                method=method,
                path=path,
                query_params=query_params,
                client_ip=client_ip,
                user_agent=user_agent
            )
        
        try:
            # 处理请求
            response = await call_next(request)
            
            # 计算处理时间
            process_time = time.time() - start_time
            
            # 仅在非健康检查路径上记录请求完成
            if not is_health_check:
                self.logger.log_request(
                    method=method,
                    path=path,
                    status_code=response.status_code,
                    duration=process_time,
                    request_id=request_id,
                    client_ip=client_ip
                )
            
            # 添加响应头
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.4f}"
            
            return response
            
        except Exception as e:
            # 计算处理时间
            process_time = time.time() - start_time
            
            # 记录请求错误
            self.logger.error(
                "HTTP请求处理失败",
                request_id=request_id,
                method=method,
                path=path,
                error=str(e),
                duration=process_time,
                client_ip=client_ip
            )
            
            # 重新抛出异常
            raise
