"""
数据验证工具模块

提供数据验证相关的工具函数。
"""

import re
import uuid
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from pydantic import ValidationError

from ..models import ExecutionModeType, MessageRoleType


class ValidationError(Exception):
    """验证错误异常"""
    
    def __init__(self, message: str, field: Optional[str] = None, value: Any = None):
        """
        初始化验证错误
        
        Args:
            message: 错误消息
            field: 字段名
            value: 字段值
        """
        self.message = message
        self.field = field
        self.value = value
        super().__init__(message)


class Validator:
    """数据验证器"""
    
    @staticmethod
    def validate_user_id(user_id: str) -> bool:
        """
        验证用户ID
        
        Args:
            user_id: 用户ID
            
        Returns:
            bool: 是否有效
            
        Raises:
            ValidationError: 验证失败
        """
        if not user_id or not isinstance(user_id, str):
            raise ValidationError("用户ID不能为空", "user_id", user_id)
        
        if len(user_id) < 1 or len(user_id) > 100:
            raise ValidationError("用户ID长度必须在1-100字符之间", "user_id", user_id)
        
        # 检查是否包含有效字符
        if not re.match(r'^[a-zA-Z0-9_-]+$', user_id):
            raise ValidationError("用户ID只能包含字母、数字、下划线和连字符", "user_id", user_id)
        
        return True
    
    @staticmethod
    def validate_conversation_id(conversation_id: str) -> bool:
        """
        验证对话ID
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            bool: 是否有效
            
        Raises:
            ValidationError: 验证失败
        """
        if not conversation_id or not isinstance(conversation_id, str):
            raise ValidationError("对话ID不能为空", "conversation_id", conversation_id)
        
        # 检查是否为有效的UUID格式
        try:
            uuid.UUID(conversation_id)
        except ValueError:
            raise ValidationError("对话ID必须是有效的UUID格式", "conversation_id", conversation_id)
        
        return True
    
    @staticmethod
    def validate_execution_mode(mode: str) -> bool:
        """
        验证执行模式
        
        Args:
            mode: 执行模式
            
        Returns:
            bool: 是否有效
            
        Raises:
            ValidationError: 验证失败
        """
        valid_modes = ["workflow", "agent"]
        
        if mode not in valid_modes:
            raise ValidationError(
                f"执行模式必须是以下之一: {valid_modes}",
                "mode",
                mode
            )
        
        return True
    
    @staticmethod
    def validate_message_content(content: str) -> bool:
        """
        验证消息内容
        
        Args:
            content: 消息内容
            
        Returns:
            bool: 是否有效
            
        Raises:
            ValidationError: 验证失败
        """
        if not content or not isinstance(content, str):
            raise ValidationError("消息内容不能为空", "content", content)
        
        if len(content.strip()) == 0:
            raise ValidationError("消息内容不能只包含空白字符", "content", content)
        
        if len(content) > 10000:
            raise ValidationError("消息内容长度不能超过10000字符", "content", len(content))
        
        return True
    
    @staticmethod
    def validate_message_role(role: str) -> bool:
        """
        验证消息角色
        
        Args:
            role: 消息角色
            
        Returns:
            bool: 是否有效
            
        Raises:
            ValidationError: 验证失败
        """
        valid_roles = ["user", "assistant", "system"]
        
        if role not in valid_roles:
            raise ValidationError(
                f"消息角色必须是以下之一: {valid_roles}",
                "role",
                role
            )
        
        return True
    
    @staticmethod
    def validate_metadata(metadata: Dict[str, Any]) -> bool:
        """
        验证元数据
        
        Args:
            metadata: 元数据字典
            
        Returns:
            bool: 是否有效
            
        Raises:
            ValidationError: 验证失败
        """
        if not isinstance(metadata, dict):
            raise ValidationError("元数据必须是字典类型", "metadata", type(metadata))
        
        # 检查键的有效性
        for key in metadata.keys():
            if not isinstance(key, str):
                raise ValidationError("元数据的键必须是字符串", "metadata.key", key)
            
            if len(key) > 100:
                raise ValidationError("元数据的键长度不能超过100字符", "metadata.key", key)
        
        # 检查值的大小（简单检查）
        try:
            import json
            serialized = json.dumps(metadata)
            if len(serialized) > 10000:
                raise ValidationError("元数据序列化后大小不能超过10KB", "metadata", len(serialized))
        except (TypeError, ValueError) as e:
            raise ValidationError(f"元数据无法序列化: {str(e)}", "metadata", metadata)
        
        return True
    
    @staticmethod
    def validate_query_string(query: str) -> bool:
        """
        验证查询字符串
        
        Args:
            query: 查询字符串
            
        Returns:
            bool: 是否有效
            
        Raises:
            ValidationError: 验证失败
        """
        if not query or not isinstance(query, str):
            raise ValidationError("查询字符串不能为空", "query", query)
        
        if len(query.strip()) == 0:
            raise ValidationError("查询字符串不能只包含空白字符", "query", query)
        
        if len(query) > 1000:
            raise ValidationError("查询字符串长度不能超过1000字符", "query", len(query))
        
        return True
    
    @staticmethod
    def validate_pagination(page: int, size: int) -> bool:
        """
        验证分页参数
        
        Args:
            page: 页码
            size: 页大小
            
        Returns:
            bool: 是否有效
            
        Raises:
            ValidationError: 验证失败
        """
        if not isinstance(page, int) or page < 1:
            raise ValidationError("页码必须是大于0的整数", "page", page)
        
        if not isinstance(size, int) or size < 1 or size > 100:
            raise ValidationError("页大小必须是1-100之间的整数", "size", size)
        
        return True


class RequestValidator:
    """请求验证器"""
    
    @staticmethod
    def validate_chat_request(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证聊天请求
        
        Args:
            data: 请求数据
            
        Returns:
            Dict[str, Any]: 验证后的数据
            
        Raises:
            ValidationError: 验证失败
        """
        # 必需字段
        required_fields = ["conversation_id", "message"]
        for field in required_fields:
            if field not in data:
                raise ValidationError(f"缺少必需字段: {field}", field, None)
        
        # 验证各个字段
        Validator.validate_conversation_id(data["conversation_id"])
        Validator.validate_message_content(data["message"])
        
        # 可选字段验证
        if "user_id" in data and data["user_id"]:
            Validator.validate_user_id(data["user_id"])
        
        if "mode" in data:
            Validator.validate_execution_mode(data["mode"])
        
        if "metadata" in data:
            Validator.validate_metadata(data["metadata"])
        
        return data
    
    @staticmethod
    def validate_create_conversation_request(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证创建对话请求
        
        Args:
            data: 请求数据
            
        Returns:
            Dict[str, Any]: 验证后的数据
            
        Raises:
            ValidationError: 验证失败
        """
        # 必需字段
        if "user_id" not in data:
            raise ValidationError("缺少必需字段: user_id", "user_id", None)
        
        # 验证字段
        Validator.validate_user_id(data["user_id"])
        
        if "mode" in data:
            Validator.validate_execution_mode(data["mode"])
        else:
            data["mode"] = "workflow"  # 默认模式
        
        return data


class ResponseValidator:
    """响应验证器"""
    
    @staticmethod
    def validate_stream_response(data: Dict[str, Any]) -> bool:
        """
        验证流式响应数据
        
        Args:
            data: 响应数据
            
        Returns:
            bool: 是否有效
            
        Raises:
            ValidationError: 验证失败
        """
        # 必需字段
        required_fields = ["conversation_id", "response_type", "timestamp"]
        for field in required_fields:
            if field not in data:
                raise ValidationError(f"流式响应缺少必需字段: {field}", field, None)
        
        # 验证响应类型
        valid_response_types = ["status", "content", "progress", "error"]
        if data["response_type"] not in valid_response_types:
            raise ValidationError(
                f"响应类型必须是以下之一: {valid_response_types}",
                "response_type",
                data["response_type"]
            )
        
        # 验证时间戳
        try:
            datetime.fromisoformat(data["timestamp"].replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            raise ValidationError("时间戳格式无效", "timestamp", data["timestamp"])
        
        return True


def sanitize_input(text: str) -> str:
    """
    清理输入文本
    
    Args:
        text: 输入文本
        
    Returns:
        str: 清理后的文本
    """
    if not isinstance(text, str):
        return str(text)
    
    # 移除控制字符
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    
    # 限制长度
    if len(text) > 10000:
        text = text[:10000]
    
    # 去除首尾空白
    text = text.strip()
    
    return text


def validate_json_schema(data: Any, schema: Dict[str, Any]) -> bool:
    """
    验证JSON模式
    
    Args:
        data: 要验证的数据
        schema: JSON模式
        
    Returns:
        bool: 是否有效
        
    Raises:
        ValidationError: 验证失败
    """
    try:
        import jsonschema
        jsonschema.validate(data, schema)
        return True
    except ImportError:
        # 如果没有安装jsonschema，进行简单验证
        return isinstance(data, dict)
    except jsonschema.ValidationError as e:
        raise ValidationError(f"JSON模式验证失败: {e.message}", e.path, e.instance)
