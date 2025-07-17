"""
Pipeline配置修复模块

修复与intent_pipeline.py的兼容性问题，确保后端配置与pipeline期望匹配
"""

import os
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from .settings import get_settings


class PipelineCompatibilityConfig(BaseModel):
    """Pipeline兼容性配置"""
    
    # 后端URL配置（与intent_pipeline.py中的BACKEND_BASE_URL匹配）
    backend_base_url: str = Field(
        default="http://117.50.252.245:8000",  # 修复为正确的端口
        description="后端服务基础URL"
    )
    
    # API端点配置
    create_conversation_endpoint: str = Field(
        default="/api/v1/conversations",
        description="创建对话端点"
    )
    
    stream_chat_endpoint: str = Field(
        default="/api/v1/conversations/{conversation_id}/stream",
        description="流式聊天端点"
    )
    
    # 超时配置（与intent_pipeline.py中的REQUEST_TIMEOUT匹配）
    request_timeout: int = Field(
        default=300,
        description="请求超时时间（秒）"
    )
    
    # 流式响应配置（与intent_pipeline.py中的STREAM_CHUNK_SIZE匹配）
    stream_chunk_size: int = Field(
        default=1024,
        description="流式响应块大小"
    )
    
    # 默认配置（与intent_pipeline.py中的默认值匹配）
    default_mode: str = Field(
        default="workflow",
        description="默认执行模式"
    )
    
    default_user_id: str = Field(
        default="default_user",
        description="默认用户ID"
    )
    
    # 调试模式
    debug_mode: bool = Field(
        default=True,
        description="是否启用调试模式"
    )
    
    def get_full_create_conversation_url(self) -> str:
        """获取完整的创建对话URL"""
        return f"{self.backend_base_url}{self.create_conversation_endpoint}"
    
    def get_full_stream_chat_url(self, conversation_id: str) -> str:
        """获取完整的流式聊天URL"""
        endpoint = self.stream_chat_endpoint.format(conversation_id=conversation_id)
        return f"{self.backend_base_url}{endpoint}"
    
    def get_template_stream_chat_url(self) -> str:
        """获取模板流式聊天URL（用于字符串格式化）"""
        return f"{self.backend_base_url}/api/v1/conversations/{{}}/stream"
    
    def validate_configuration(self) -> Dict[str, Any]:
        """验证配置是否正确"""
        validation_results = {
            "backend_url_valid": self.backend_base_url.startswith("http"),
            "timeout_reasonable": 30 <= self.request_timeout <= 600,
            "chunk_size_valid": 512 <= self.stream_chunk_size <= 8192,
            "mode_valid": self.default_mode in ["workflow", "agent"],
            "endpoints_valid": all([
                self.create_conversation_endpoint.startswith("/api/v1/"),
                self.stream_chat_endpoint.startswith("/api/v1/"),
                "{conversation_id}" in self.stream_chat_endpoint
            ])
        }
        
        validation_results["all_valid"] = all(validation_results.values())
        return validation_results


def get_pipeline_config() -> PipelineCompatibilityConfig:
    """获取Pipeline兼容性配置"""
    app_settings = get_settings()
    
    # 使用应用设置中的配置构建Pipeline配置
    config = PipelineCompatibilityConfig(
        backend_base_url=f"http://117.50.252.245:{app_settings.api_port}",
        request_timeout=300,  # 与intent_pipeline.py匹配
        stream_chunk_size=1024,  # 与intent_pipeline.py匹配
        debug_mode=app_settings.debug
    )
    
    return config


def validate_pipeline_compatibility() -> Dict[str, Any]:
    """验证Pipeline兼容性"""
    config = get_pipeline_config()
    app_settings = get_settings()
    
    compatibility_check = {
        "config_validation": config.validate_configuration(),
        "url_consistency": {
            "backend_url": config.backend_base_url,
            "expected_by_pipeline": f"http://117.50.252.245:{app_settings.api_port}",
            "matches": config.backend_base_url.endswith(f":{app_settings.api_port}")
        },
        "timeout_consistency": {
            "pipeline_config": config.request_timeout,
            "app_settings": app_settings.request_timeout,
            "intent_pipeline_expected": 300,
            "matches": config.request_timeout == 300
        },
        "chunk_size_consistency": {
            "pipeline_config": config.stream_chunk_size,
            "app_settings": app_settings.stream_chunk_size,
            "intent_pipeline_expected": 1024,
            "matches": config.stream_chunk_size == 1024
        }
    }
    
    return compatibility_check


def generate_env_fix_suggestions() -> Dict[str, str]:
    """生成环境配置修复建议"""
    app_settings = get_settings()
    
    suggestions = {
        "# 修复后端URL配置": f"BACKEND_BASE_URL=http://117.50.252.245:{app_settings.api_port}",
        "# 确保超时配置匹配": "REQUEST_TIMEOUT=300",
        "# 确保流式块大小匹配": "STREAM_CHUNK_SIZE=1024",
        "# 启用调试模式": "DEBUG_MODE=true",
        "# 默认执行模式": "DEFAULT_MODE=workflow",
        "# 默认用户ID": "DEFAULT_USER_ID=default_user"
    }
    
    return suggestions


def print_configuration_report():
    """打印配置报告"""
    config = get_pipeline_config()
    validation = validate_pipeline_compatibility()
    suggestions = generate_env_fix_suggestions()
    
    print("Pipeline兼容性配置报告")
    print("=" * 60)
    
    print("\n当前配置:")
    print(f"  后端URL: {config.backend_base_url}")
    print(f"  请求超时: {config.request_timeout}秒")
    print(f"  流式块大小: {config.stream_chunk_size}字节")
    print(f"  默认模式: {config.default_mode}")
    print(f"  调试模式: {config.debug_mode}")
    
    print("\n兼容性检查:")
    config_valid = validation["config_validation"]
    print(f"  配置有效性: {'✓' if config_valid['all_valid'] else '✗'}")
    print(f"  URL一致性: {'✓' if validation['url_consistency']['matches'] else '✗'}")
    print(f"  超时一致性: {'✓' if validation['timeout_consistency']['matches'] else '✗'}")
    print(f"  块大小一致性: {'✓' if validation['chunk_size_consistency']['matches'] else '✗'}")
    
    print("\n环境配置修复建议:")
    for comment, suggestion in suggestions.items():
        print(f"  {comment}")
        print(f"  {suggestion}")
    
    print("\nAPI端点:")
    print(f"  创建对话: {config.get_full_create_conversation_url()}")
    print(f"  流式聊天: {config.get_template_stream_chat_url()}")
    
    return validation


if __name__ == "__main__":
    print_configuration_report() 