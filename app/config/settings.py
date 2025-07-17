"""
配置管理模块

使用Pydantic Settings管理应用配置，支持环境变量和配置文件。
"""

import os
from typing import Optional, List
from pydantic import BaseSettings, Field, validator


class Settings(BaseSettings):
    """应用配置类"""
    
    # 应用基础配置
    environment: str = Field(default="development", description="运行环境")
    debug: bool = Field(default=True, description="调试模式")
    log_level: str = Field(default="info", description="日志级别")
    api_host: str = Field(default="0.0.0.0", description="API主机")
    api_port: int = Field(default=8000, description="API端口")
    
    # OpenAI配置
    openai_api_key: str = Field(..., description="OpenAI API密钥")
    openai_base_url: str = Field(default="https://api.openai.com/v1", description="OpenAI API基础URL")
    openai_model: str = Field(default="gpt-4", description="OpenAI模型")
    openai_temperature: float = Field(default=0.7, description="OpenAI温度参数")
    openai_max_tokens: int = Field(default=2000, description="OpenAI最大令牌数")
    
    # 知识库配置
    knowledge_api_url: str = Field(default="http://localhost:8000/api/knowledge_search", description="知识库API URL")
    knowledge_api_key: Optional[str] = Field(None, description="知识库API密钥")
    knowledge_timeout: int = Field(default=30, description="知识库请求超时时间")
    
    # Open WebUI配置
    openwebui_base_url: str = Field(default="http://localhost:8080", description="Open WebUI基础URL")
    
    # LightRAG配置
    lightrag_api_url: str = Field(default="http://localhost:8001/api/lightrag", description="LightRAG API URL")
    lightrag_api_key: Optional[str] = Field(None, description="LightRAG API密钥")
    lightrag_timeout: int = Field(default=30, description="LightRAG请求超时时间")
    lightrag_default_mode: str = Field(default="mix", description="LightRAG默认模式")
    
    # 搜索引擎配置
    search_engine_api_key: Optional[str] = Field(None, description="搜索引擎API密钥")
    search_engine_url: str = Field(default="https://api.search.com", description="搜索引擎URL")
    search_timeout: int = Field(default=30, description="搜索请求超时时间")
    search_max_results: int = Field(default=5, description="搜索最大结果数")
    
    # Redis配置
    redis_host: str = Field(default="localhost", description="Redis主机")
    redis_port: int = Field(default=6379, description="Redis端口")
    redis_db: int = Field(default=0, description="Redis数据库")
    redis_password: Optional[str] = Field(None, description="Redis密码")
    redis_timeout: int = Field(default=5, description="Redis连接超时时间")
    

    
    # 日志配置
    log_format: str = Field(default="json", description="日志格式")
    log_file_path: str = Field(default="logs/app.log", description="日志文件路径")
    log_max_size: str = Field(default="100MB", description="日志文件最大大小")
    log_backup_count: int = Field(default=5, description="日志文件备份数量")
    
    # 性能配置
    max_workers: int = Field(default=10, description="最大工作线程数")
    request_timeout: int = Field(default=30, description="请求超时时间")
    stream_chunk_size: int = Field(default=1024, description="流式响应块大小")
    max_concurrent_tasks: int = Field(default=3, description="最大并发任务数")
    
    # CORS配置
    cors_origins: List[str] = Field(default=["*"], description="CORS允许的源")
    cors_methods: List[str] = Field(default=["*"], description="CORS允许的方法")
    cors_headers: List[str] = Field(default=["*"], description="CORS允许的头部")
    
    @validator("log_level")
    def validate_log_level(cls, v):
        """验证日志级别"""
        valid_levels = ["debug", "info", "warning", "error", "critical"]
        if v.lower() not in valid_levels:
            raise ValueError(f"日志级别必须是以下之一: {valid_levels}")
        return v.lower()
    
    @validator("environment")
    def validate_environment(cls, v):
        """验证运行环境"""
        valid_envs = ["development", "testing", "staging", "production"]
        if v.lower() not in valid_envs:
            raise ValueError(f"运行环境必须是以下之一: {valid_envs}")
        return v.lower()
    
    @validator("openai_temperature")
    def validate_temperature(cls, v):
        """验证OpenAI温度参数"""
        if not 0.0 <= v <= 2.0:
            raise ValueError("OpenAI温度参数必须在0.0到2.0之间")
        return v
    
    def is_development(self) -> bool:
        """判断是否为开发环境"""
        return self.environment == "development"
    
    def is_production(self) -> bool:
        """判断是否为生产环境"""
        return self.environment == "production"
    
    def get_redis_url(self) -> str:
        """获取Redis连接URL"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
    
    class Config:
        """Pydantic配置"""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# 创建全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取配置实例"""
    return settings
