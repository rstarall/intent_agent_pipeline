"""
日志配置模块

配置结构化日志系统，支持JSON格式输出和文件轮转。
"""

import os
import sys
import logging
import logging.handlers
from typing import Dict, Any
from datetime import datetime

try:
    import structlog
    from structlog.stdlib import LoggerFactory
    STRUCTLOG_AVAILABLE = True
except ImportError:
    STRUCTLOG_AVAILABLE = False
    structlog = None
    LoggerFactory = None

from .settings import get_settings


def setup_logging() -> None:
    """设置日志系统"""
    settings = get_settings()

    # 创建日志目录
    log_dir = os.path.dirname(settings.log_file_path)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    # 配置标准库日志
    if STRUCTLOG_AVAILABLE:
        logging.basicConfig(
            format="%(message)s",
            stream=sys.stdout,
            level=getattr(logging, settings.log_level.upper())
        )

        # 配置structlog
        if settings.log_format.lower() == "json":
            processors = [
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                add_custom_fields,
                structlog.processors.JSONRenderer()
            ]
        else:
            processors = [
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                add_custom_fields,
                structlog.dev.ConsoleRenderer()
            ]

        structlog.configure(
            processors=processors,
            context_class=dict,
            logger_factory=LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
    else:
        # 使用标准库日志作为后备
        logging.basicConfig(
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            stream=sys.stdout,
            level=getattr(logging, settings.log_level.upper())
        )

    # 配置文件处理器
    if settings.log_file_path:
        setup_file_handler(settings)


def setup_file_handler(settings) -> None:
    """设置文件日志处理器"""
    # 解析文件大小
    max_bytes = parse_size(settings.log_max_size)
    
    # 创建轮转文件处理器
    file_handler = logging.handlers.RotatingFileHandler(
        filename=settings.log_file_path,
        maxBytes=max_bytes,
        backupCount=settings.log_backup_count,
        encoding='utf-8'
    )
    
    # 设置格式器
    if settings.log_format.lower() == "json":
        formatter = logging.Formatter('%(message)s')
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    file_handler.setFormatter(formatter)
    file_handler.setLevel(getattr(logging, settings.log_level.upper()))
    
    # 添加到根日志器
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)


def parse_size(size_str: str) -> int:
    """解析文件大小字符串"""
    size_str = size_str.upper()
    
    if size_str.endswith('KB'):
        return int(size_str[:-2]) * 1024
    elif size_str.endswith('MB'):
        return int(size_str[:-2]) * 1024 * 1024
    elif size_str.endswith('GB'):
        return int(size_str[:-2]) * 1024 * 1024 * 1024
    else:
        return int(size_str)


def add_custom_fields(logger, method_name, event_dict):
    """添加自定义字段到日志记录"""
    event_dict['service'] = 'intent-agent-pipeline'
    event_dict['version'] = '1.0.0'
    
    # 添加请求ID（如果存在）
    import contextvars
    try:
        request_id = contextvars.copy_context().get('request_id', None)
        if request_id:
            event_dict['request_id'] = request_id
    except:
        pass
    
    return event_dict


class StructuredLogger:
    """结构化日志器包装类"""

    def __init__(self, name: str):
        if STRUCTLOG_AVAILABLE:
            self.logger = structlog.get_logger(name)
            self.use_structlog = True
        else:
            self.logger = logging.getLogger(name)
            self.use_structlog = False
    
    def debug(self, message: str, **kwargs):
        """调试日志"""
        if self.use_structlog:
            self.logger.debug(message, **kwargs)
        else:
            extra_info = " | ".join([f"{k}={v}" for k, v in kwargs.items()]) if kwargs else ""
            full_message = f"{message} {extra_info}".strip()
            self.logger.debug(full_message)

    def info(self, message: str, **kwargs):
        """信息日志"""
        if self.use_structlog:
            self.logger.info(message, **kwargs)
        else:
            extra_info = " | ".join([f"{k}={v}" for k, v in kwargs.items()]) if kwargs else ""
            full_message = f"{message} {extra_info}".strip()
            self.logger.info(full_message)

    def warning(self, message: str, **kwargs):
        """警告日志"""
        if self.use_structlog:
            self.logger.warning(message, **kwargs)
        else:
            extra_info = " | ".join([f"{k}={v}" for k, v in kwargs.items()]) if kwargs else ""
            full_message = f"{message} {extra_info}".strip()
            self.logger.warning(full_message)

    def error(self, message: str, **kwargs):
        """错误日志"""
        if self.use_structlog:
            self.logger.error(message, **kwargs)
        else:
            extra_info = " | ".join([f"{k}={v}" for k, v in kwargs.items()]) if kwargs else ""
            full_message = f"{message} {extra_info}".strip()
            self.logger.error(full_message)

    def critical(self, message: str, **kwargs):
        """严重错误日志"""
        if self.use_structlog:
            self.logger.critical(message, **kwargs)
        else:
            extra_info = " | ".join([f"{k}={v}" for k, v in kwargs.items()]) if kwargs else ""
            full_message = f"{message} {extra_info}".strip()
            self.logger.critical(full_message)
    
    def log_request(self, method: str, path: str, status_code: int,
                   duration: float, **kwargs):
        """记录HTTP请求日志"""
        self.info(
            "HTTP请求",
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=round(duration * 1000, 2),
            **kwargs
        )

    def log_agent_action(self, agent_type: str, action: str,
                        conversation_id: str, **kwargs):
        """记录Agent动作日志"""
        self.info(
            "Agent动作",
            agent_type=agent_type,
            action=action,
            conversation_id=conversation_id,
            **kwargs
        )

    def log_error_with_context(self, error: Exception, context: Dict[str, Any]):
        """记录带上下文的错误日志"""
        self.error(
            "系统错误",
            error_type=type(error).__name__,
            error_message=str(error),
            **context
        )

    def error_with_context(self, error: Exception, context: Dict[str, Any]):
        """兼容性方法：记录带上下文的错误日志"""
        self.log_error_with_context(error, context)


def get_logger(name: str) -> StructuredLogger:
    """获取结构化日志器"""
    return StructuredLogger(name)
