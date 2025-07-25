"""
健康检查API模块

提供系统健康状态检查接口。
"""

from fastapi import APIRouter, Depends
from datetime import datetime
from typing import Dict, Any

from ...models import HealthCheckResponse, APIResponse
from ...services import KnowledgeService, LightRagService, SearchService
from ...config import get_settings, get_logger


router = APIRouter()
logger = get_logger("health_api")


async def get_knowledge_service() -> KnowledgeService:
    """获取知识库服务实例"""
    return KnowledgeService()


async def get_lightrag_service() -> LightRagService:
    """获取LightRAG服务实例"""
    return LightRagService()


async def get_search_service() -> SearchService:
    """获取搜索服务实例"""
    return SearchService()


@router.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """
    基础健康检查
    
    Returns:
        HealthCheckResponse: 健康状态响应
    """
    try:
        settings = get_settings()
        
        response = HealthCheckResponse(
            status="healthy",
            version="1.0.0",
            timestamp=datetime.now(),
            services={}
        )
        
        # 删除健康检查的INFO日志，避免冗余
        
        return response
        
    except Exception as e:
        logger.error(f"健康检查失败: {str(e)}")
        
        return HealthCheckResponse(
            status="unhealthy",
            version="1.0.0",
            timestamp=datetime.now(),
            services={"error": str(e)}
        )


@router.get("/health/detailed", response_model=APIResponse)
async def detailed_health_check(
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
    lightrag_service: LightRagService = Depends(get_lightrag_service),
    search_service: SearchService = Depends(get_search_service)
):
    """
    详细健康检查，包括外部服务状态
    
    Returns:
        APIResponse: 详细健康状态
    """
    try:
        # 删除详细健康检查的INFO日志
        
        # 检查各个服务的健康状态
        services_status = {}
        overall_healthy = True
        
        # 检查知识库服务
        try:
            knowledge_healthy = await knowledge_service.health_check()
            services_status["knowledge_service"] = {
                "status": "healthy" if knowledge_healthy else "unhealthy",
                "checked_at": datetime.now().isoformat()
            }
            if not knowledge_healthy:
                overall_healthy = False
        except Exception as e:
            services_status["knowledge_service"] = {
                "status": "error",
                "error": str(e),
                "checked_at": datetime.now().isoformat()
            }
            overall_healthy = False
        
        # 检查LightRAG服务
        try:
            lightrag_healthy = await lightrag_service.health_check()
            services_status["lightrag_service"] = {
                "status": "healthy" if lightrag_healthy else "unhealthy",
                "checked_at": datetime.now().isoformat()
            }
            if not lightrag_healthy:
                overall_healthy = False
        except Exception as e:
            services_status["lightrag_service"] = {
                "status": "error",
                "error": str(e),
                "checked_at": datetime.now().isoformat()
            }
            overall_healthy = False
        
        # 检查搜索服务
        try:
            search_healthy = await search_service.health_check()
            services_status["search_service"] = {
                "status": "healthy" if search_healthy else "unhealthy",
                "checked_at": datetime.now().isoformat()
            }
            if not search_healthy:
                overall_healthy = False
        except Exception as e:
            services_status["search_service"] = {
                "status": "error",
                "error": str(e),
                "checked_at": datetime.now().isoformat()
            }
            overall_healthy = False
        
        # 构建响应
        health_data = {
            "overall_status": "healthy" if overall_healthy else "degraded",
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "services": services_status,
            "system_info": {
                "environment": get_settings().environment,
                "debug_mode": get_settings().debug
            }
        }
        
        # 关闭服务连接
        await knowledge_service.close()
        await lightrag_service.close()
        await search_service.close()
        
        if overall_healthy:
            return APIResponse.success_response(
                message="所有服务运行正常",
                data=health_data
            )
        else:
            return APIResponse.error_response(
                message="部分服务不可用",
                error_code="SERVICES_DEGRADED",
                data=health_data
            )
        
    except Exception as e:
        logger.error_with_context(e, {"operation": "detailed_health_check"})
        
        return APIResponse.error_response(
            message=f"健康检查失败: {str(e)}",
            error_code="HEALTH_CHECK_ERROR"
        )


@router.get("/health/services/{service_name}", response_model=APIResponse)
async def service_health_check(service_name: str):
    """
    单个服务健康检查
    
    Args:
        service_name: 服务名称 (knowledge, lightrag, search)
        
    Returns:
        APIResponse: 服务健康状态
    """
    try:
        # 删除服务健康检查的INFO日志
        
        service_healthy = False
        service_info = {}
        
        if service_name == "knowledge":
            service = KnowledgeService()
            try:
                service_healthy = await service.health_check()
                service_info = {"service": "knowledge_service"}
            finally:
                await service.close()
                
        elif service_name == "lightrag":
            service = LightRagService()
            try:
                service_healthy = await service.health_check()
                service_info = {"service": "lightrag_service"}
            finally:
                await service.close()
                
        elif service_name == "search":
            service = SearchService()
            try:
                service_healthy = await service.health_check()
                service_info = {"service": "search_service"}
            finally:
                await service.close()
                
        else:
            return APIResponse.error_response(
                message=f"未知的服务名称: {service_name}",
                error_code="UNKNOWN_SERVICE"
            )
        
        service_info.update({
            "status": "healthy" if service_healthy else "unhealthy",
            "checked_at": datetime.now().isoformat()
        })
        
        if service_healthy:
            return APIResponse.success_response(
                message=f"服务 {service_name} 运行正常",
                data=service_info
            )
        else:
            return APIResponse.error_response(
                message=f"服务 {service_name} 不可用",
                error_code="SERVICE_UNHEALTHY",
                data=service_info
            )
        
    except Exception as e:
        logger.error_with_context(
            e,
            {
                "operation": "service_health_check",
                "service_name": service_name
            }
        )
        
        return APIResponse.error_response(
            message=f"检查服务 {service_name} 健康状态失败: {str(e)}",
            error_code="HEALTH_CHECK_ERROR"
        )


@router.get("/health/stats", response_model=APIResponse)
async def health_stats():
    """
    获取系统统计信息
    
    Returns:
        APIResponse: 系统统计信息
    """
    try:
        # 删除系统统计信息的INFO日志
        
        settings = get_settings()
        
        stats = {
            "application": {
                "name": "化妆品知识库问答机器人Pipeline",
                "version": "1.0.0",
                "environment": settings.environment,
                "debug_mode": settings.debug
            },
            "configuration": {
                "api_host": settings.api_host,
                "api_port": settings.api_port,
                "log_level": settings.log_level,
                "max_workers": settings.max_workers,
                "request_timeout": settings.request_timeout
            },
            "timestamp": datetime.now().isoformat()
        }
        
        return APIResponse.success_response(
            message="系统统计信息获取成功",
            data=stats
        )
        
    except Exception as e:
        logger.error_with_context(e, {"operation": "health_stats"})
        
        return APIResponse.error_response(
            message=f"获取系统统计信息失败: {str(e)}",
            error_code="STATS_ERROR"
        )
