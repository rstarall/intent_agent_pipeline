"""
CORS中间件模块

配置跨域资源共享设置。
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ...config import Settings


def setup_cors(app: FastAPI, settings: Settings) -> None:
    """
    设置CORS中间件
    
    Args:
        app: FastAPI应用实例
        settings: 应用配置
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=settings.cors_methods,
        allow_headers=settings.cors_headers,
        expose_headers=[
            "Content-Type",
            "Cache-Control",
            "Connection",
            "Access-Control-Allow-Origin",
            "Access-Control-Allow-Headers"
        ]
    )
