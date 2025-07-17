"""
FastAPI应用主入口

化妆品知识库问答机器人Pipeline项目的主应用。
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from .config import setup_logging, get_settings, get_logger
from .core import PipelineInterface
from .api.v1 import pipeline_router, health_router
from .api.middleware.cors import setup_cors
from .api.middleware.logging import LoggingMiddleware


# 全局变量
pipeline_interface: PipelineInterface = None
logger = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global pipeline_interface, logger
    
    # 启动时初始化
    try:
        # 设置日志
        setup_logging()
        logger = get_logger("main")
        
        logger.info("启动化妆品知识库问答机器人Pipeline")
        
        # 初始化Pipeline接口
        pipeline_interface = PipelineInterface()
        
        # 将Pipeline接口添加到应用状态
        app.state.pipeline = pipeline_interface
        
        logger.info("应用初始化完成")
        
        yield
        
    except Exception as e:
        if logger:
            logger.error(f"应用启动失败: {str(e)}")
        else:
            print(f"应用启动失败: {str(e)}")
        raise
    
    # 关闭时清理
    try:
        if logger:
            logger.info("开始关闭应用")
        
        # 这里可以添加清理逻辑
        # 例如关闭数据库连接、清理缓存等
        
        if logger:
            logger.info("应用关闭完成")
            
    except Exception as e:
        if logger:
            logger.error(f"应用关闭时出错: {str(e)}")


def create_app() -> FastAPI:
    """创建FastAPI应用"""
    settings = get_settings()
    
    # 创建应用实例
    app = FastAPI(
        title="化妆品知识库问答机器人Pipeline",
        description="支持Workflow和Agent两种模式的智能问答系统",
        version="1.0.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan
    )
    
    # 设置CORS
    setup_cors(app, settings)
    
    # 添加中间件
    app.add_middleware(LoggingMiddleware)
    
    # 注册路由
    app.include_router(health_router, prefix="/api/v1", tags=["健康检查"])
    app.include_router(pipeline_router, prefix="/api/v1", tags=["Pipeline"])
    
    # 全局异常处理器
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """全局异常处理"""
        logger = get_logger("exception_handler")
        
        logger.error_with_context(
            exc,
            {
                "method": request.method,
                "url": str(request.url),
                "client": request.client.host if request.client else "unknown"
            }
        )
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "内部服务器错误",
                "error_code": "INTERNAL_SERVER_ERROR",
                "timestamp": "2024-01-01T00:00:00Z"  # 实际应用中应该使用真实时间
            }
        )
    
    # 404处理器
    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc):
        """404错误处理"""
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "message": "请求的资源不存在",
                "error_code": "NOT_FOUND",
                "timestamp": "2024-01-01T00:00:00Z"
            }
        )
    
    return app


# 创建应用实例
app = create_app()


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "化妆品知识库问答机器人Pipeline API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health"
    }


def main():
    """主函数，用于直接运行应用"""
    settings = get_settings()
    
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        access_log=True
    )


if __name__ == "__main__":
    main()
