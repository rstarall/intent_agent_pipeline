"""
Token认证中间件

提供token验证功能，支持从请求头和请求体中获取token。
"""

from typing import Optional
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ...config import get_logger


logger = get_logger("auth_middleware")
security = HTTPBearer(auto_error=False)


def get_token_from_request(request: Request) -> Optional[str]:
    """
    从请求中获取token
    
    支持以下方式：
    1. Authorization头部: Bearer token
    2. 请求体中的user.token字段
    
    Args:
        request: FastAPI请求对象
        
    Returns:
        Optional[str]: token字符串，如果没有找到则返回None
    """
    # 1. 首先尝试从Authorization头部获取
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]  # 去掉 "Bearer " 前缀
    
    # 2. 尝试从请求体获取（仅适用于POST请求）
    if hasattr(request, "_body") and request._body:
        try:
            import json
            body = json.loads(request._body.decode())
            if isinstance(body, dict) and "user" in body:
                user_info = body["user"]
                if isinstance(user_info, dict) and "token" in user_info:
                    return user_info["token"]
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
    
    return None


def validate_token(token: str) -> bool:
    """
    验证token是否有效
    
    Args:
        token: 要验证的token
        
    Returns:
        bool: token是否有效
    """
    # 这里可以实现实际的token验证逻辑
    # 例如：JWT验证、数据库查询等
    # 目前返回True，表示所有token都有效
    
    if not token or len(token.strip()) == 0:
        return False
    
    # 简单验证：token长度应该大于10
    if len(token) < 10:
        return False
    
    return True


def get_current_user_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[str]:
    """
    获取当前用户的token
    
    Args:
        request: FastAPI请求对象
        credentials: HTTP认证凭据
        
    Returns:
        Optional[str]: 用户token
    """
    token = None
    
    # 1. 从HTTP Bearer认证获取
    if credentials:
        token = credentials.credentials
    
    # 2. 从请求中获取
    if not token:
        token = get_token_from_request(request)
    
    return token


def require_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> str:
    """
    要求提供有效的token
    
    Args:
        request: FastAPI请求对象
        credentials: HTTP认证凭据
        
    Returns:
        str: 有效的token
        
    Raises:
        HTTPException: 如果token无效或缺失
    """
    token = get_current_user_token(request, credentials)
    
    if not token:
        raise HTTPException(
            status_code=401,
            detail="缺少认证token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not validate_token(token):
        raise HTTPException(
            status_code=401,
            detail="无效的认证token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return token


def optional_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[str]:
    """
    可选的token验证
    
    Args:
        request: FastAPI请求对象
        credentials: HTTP认证凭据
        
    Returns:
        Optional[str]: 有效的token，如果没有或无效则返回None
    """
    token = get_current_user_token(request, credentials)
    
    if token and validate_token(token):
        return token
    
    return None 