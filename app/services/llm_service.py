"""
LLM服务模块

提供OpenAI API调用服务，支持流式和非流式响应。
"""

import asyncio
from typing import Dict, List, Optional, AsyncIterator, Any
import aiohttp
import json

from ..config import get_settings, get_logger
from ..models import Message


class LLMService:
    """LLM调用服务"""
    
    def __init__(self):
        """初始化LLM服务"""
        self.settings = get_settings()
        self.logger = get_logger("LLMService")
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取HTTP会话"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.settings.request_timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def close(self):
        """关闭HTTP会话"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def generate_response(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_message: Optional[str] = None,
        conversation_history: Optional[List[Message]] = None
    ) -> str:
        """
        生成LLM响应
        
        Args:
            prompt: 用户提示
            temperature: 温度参数
            max_tokens: 最大令牌数
            system_message: 系统消息
            conversation_history: 对话历史
            
        Returns:
            str: LLM响应内容
        """
        try:
            # 检查配置
            if not self.settings.openai_api_key:
                # 尝试从环境变量获取
                import os
                # 如果使用OpenRouter，优先尝试OPENROUTER_API_KEY
                if "openrouter.ai" in self.settings.openai_base_url:
                    api_key = os.getenv('OPENROUTER_API_KEY') or os.getenv('OPENAI_API_KEY')
                else:
                    api_key = os.getenv('OPENAI_API_KEY')
                if not api_key:
                    raise ValueError("未配置OpenAI API密钥")
                self.settings.openai_api_key = api_key
            
            if not self.settings.openai_base_url:
                raise ValueError("未配置OpenAI Base URL")
            
            # 调试信息：显示 API key 和 base URL
            self.logger.info(
                "OpenAI API 配置信息",
                api_key_prefix=self.settings.openai_api_key[:12] + "..." if self.settings.openai_api_key else "None",
                base_url=self.settings.openai_base_url,
                model=self.settings.openai_model
            )
            
            # 构建消息列表
            messages = []
            
            # 添加系统消息
            if system_message:
                messages.append({"role": "system", "content": system_message})
            
            # 添加对话历史
            if conversation_history:
                for msg in conversation_history[-5:]:  # 只保留最近5条消息
                    messages.append({"role": msg.role, "content": msg.content})
            
            # 添加当前提示
            messages.append({"role": "user", "content": prompt})
            
            # 准备请求数据
            request_data = {
                "model": self.settings.openai_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens or self.settings.openai_max_tokens
            }
            
            # 发送请求
            session = await self._get_session()
            headers = {
                "Authorization": f"Bearer {self.settings.openai_api_key}",
                "Content-Type": "application/json"
            }
            
            self.logger.info(
                "发送LLM请求",
                url=f"{self.settings.openai_base_url}/chat/completions",
                model=self.settings.openai_model,
                prompt_length=len(prompt),
                request_headers={"Authorization": f"Bearer {self.settings.openai_api_key[:12]}...", "Content-Type": "application/json"}
            )
            
            async with session.post(
                f"{self.settings.openai_base_url}/chat/completions",
                headers=headers,
                json=request_data
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    self.logger.error(
                        f"OpenAI API错误 {response.status}: {error_text}",
                        extra={
                            "status_code": response.status,
                            "response_text": error_text,
                            "url": f"{self.settings.openai_base_url}/chat/completions",
                            "api_key_prefix": self.settings.openai_api_key[:12] + "..." if self.settings.openai_api_key else "None",
                            "request_data": {k: v for k, v in request_data.items() if k != "messages"}
                        }
                    )
                    raise Exception(f"OpenAI API错误 {response.status}: {error_text}")
                
                result = await response.json()
                
                # 检查响应格式
                if "choices" not in result or not result["choices"]:
                    raise Exception(f"无效的OpenAI响应格式: {result}")
                
                content = result["choices"][0]["message"]["content"]
                
                # 检查内容
                if not content:
                    self.logger.warning("收到空的LLM响应")
                    return "抱歉，我目前无法为您提供回答。请稍后再试。"
                
                self.logger.info(
                    "LLM响应生成成功",
                    prompt_length=len(prompt),
                    response_length=len(content),
                    model=self.settings.openai_model,
                    temperature=temperature
                )
                
                return content
                
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "prompt_length": len(prompt),
                    "temperature": temperature,
                    "model": self.settings.openai_model,
                    "openai_base_url": self.settings.openai_base_url
                }
            )
            # 返回错误消息而不是抛出异常
            return f"抱歉，在生成响应时遇到了问题：{str(e)}"
    
    async def generate_stream_response(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_message: Optional[str] = None,
        conversation_history: Optional[List[Message]] = None
    ) -> AsyncIterator[str]:
        """
        生成流式LLM响应
        
        Args:
            prompt: 用户提示
            temperature: 温度参数
            max_tokens: 最大令牌数
            system_message: 系统消息
            conversation_history: 对话历史
            
        Yields:
            str: 流式响应内容片段
        """
        try:
            # 构建消息列表
            messages = []
            
            if system_message:
                messages.append({"role": "system", "content": system_message})
            
            if conversation_history:
                for msg in conversation_history[-5:]:
                    messages.append({"role": msg.role, "content": msg.content})
            
            messages.append({"role": "user", "content": prompt})
            
            # 准备请求数据
            request_data = {
                "model": self.settings.openai_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens or self.settings.openai_max_tokens,
                "stream": True
            }
            
            # 发送流式请求
            session = await self._get_session()
            headers = {
                "Authorization": f"Bearer {self.settings.openai_api_key}",
                "Content-Type": "application/json"
            }
            
            async with session.post(
                f"{self.settings.openai_base_url}/chat/completions",
                headers=headers,
                json=request_data
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"OpenAI API错误 {response.status}: {error_text}")
                
                # 处理流式响应
                async for line in response.content:
                    line = line.decode('utf-8', errors='ignore').strip()
                    
                    if line.startswith('data: '):
                        data = line[6:]  # 移除 'data: ' 前缀
                        
                        if data == '[DONE]':
                            break
                        
                        try:
                            chunk = json.loads(data)
                            delta = chunk.get('choices', [{}])[0].get('delta', {})
                            content = delta.get('content', '')
                            
                            if content:
                                yield content
                                
                        except json.JSONDecodeError:
                            continue
                
                self.logger.info(
                    "流式LLM响应生成完成",
                    prompt_length=len(prompt),
                    model=self.settings.openai_model
                )
                
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "prompt_length": len(prompt),
                    "temperature": temperature,
                    "model": self.settings.openai_model
                }
            )
            raise
    
    async def generate_json_response(
        self,
        prompt: str,
        schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        生成JSON格式的LLM响应
        
        Args:
            prompt: 用户提示
            schema: JSON模式（可选）
            temperature: 温度参数
            max_tokens: 最大令牌数
            
        Returns:
            Dict[str, Any]: 解析后的JSON响应
        """
        try:
            # 添加JSON格式要求到提示
            json_prompt = f"{prompt}\n\n请以有效的JSON格式返回响应。"
            
            if schema:
                json_prompt += f"\n\nJSON模式: {json.dumps(schema, ensure_ascii=False)}"
            
            # 生成响应
            response = await self.generate_response(
                json_prompt,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # 尝试解析JSON
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                # 如果解析失败，尝试提取JSON部分
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                else:
                    raise ValueError(f"无法解析JSON响应: {response}")
                    
        except Exception as e:
            self.logger.error_with_context(
                e,
                {
                    "prompt_length": len(prompt),
                    "schema": schema is not None
                }
            )
            raise
    
    def __del__(self):
        """析构函数，确保会话关闭"""
        if hasattr(self, 'session') and self.session and not self.session.closed:
            # 在事件循环中关闭会话
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.session.close())
                else:
                    loop.run_until_complete(self.session.close())
            except:
                pass
