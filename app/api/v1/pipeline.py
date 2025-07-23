"""
Pipeline API路由模块

提供对话创建、消息发送和流式响应接口。
"""

import json
import asyncio
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import List, Optional
from datetime import datetime

from ...models import (
    ChatRequest, ChatResponse, APIResponse, Message,
    ExecutionModeType, StreamResponse, CreateConversationRequest
)
from ...core import PipelineInterface
from ...config import get_logger
from ...api.middleware import optional_token


router = APIRouter()
logger = get_logger("pipeline_api")


def get_pipeline_interface(request: Request) -> PipelineInterface:
    """获取Pipeline接口实例"""
    return request.app.state.pipeline


@router.post("/conversations", response_model=APIResponse)
async def create_conversation(
    request: CreateConversationRequest,
    pipeline: PipelineInterface = Depends(get_pipeline_interface),
    token: Optional[str] = Depends(optional_token)
):
    """
    创建新对话会话
    
    Args:
        request: 创建对话请求
        pipeline: Pipeline接口实例
        token: 用户认证token
        
    Returns:
        APIResponse: 包含对话ID的响应
    """
    try:
        # 从请求中获取token（优先级：依赖注入 > 请求体）
        user_token = token or request.get_user_token()
        
        # 记录请求信息
        log_info = f"创建新对话会话: user_id={request.user_id}, mode={request.mode}"
        if request.conversation_id:
            log_info += f", conversation_id={request.conversation_id}"
        logger.info(log_info)
        
        # DEBUG: 打印完整的请求参数
        print("\n" + "="*80)
        print("[DEBUG] 创建对话API接收到的参数:")
        print(f"  user_id: {request.user_id}")
        print(f"  mode: {request.mode}")
        print(f"  conversation_id: {request.conversation_id}")
        print(f"  knowledge_bases: {request.knowledge_bases}")
        print(f"  knowledge_api_url: {request.knowledge_api_url}")
        print("="*80 + "\n")
        
        # 创建对话 - 传递可选的conversation_id和知识库配置
        conversation_id = pipeline.create_conversation(
            user_id=request.user_id,
            mode=request.mode,
            conversation_id=request.conversation_id,
            knowledge_bases=request.knowledge_bases,
            knowledge_api_url=request.knowledge_api_url
        )
        
        response_data = {
            "conversation_id": conversation_id,
            "user_id": request.user_id,
            "mode": request.mode,
            "created_at": datetime.now().isoformat(),
            "is_custom_id": request.conversation_id is not None
        }
        
        logger.info(f"对话创建成功: {conversation_id}")
        
        return APIResponse.success_response(
            message="对话创建成功",
            data=response_data
        )
        
    except Exception as e:
        logger.error_with_context(
            e,
            {
                "operation": "create_conversation",
                "user_id": request.user_id,
                "mode": request.mode,
                "conversation_id": request.conversation_id
            }
        )
        
        return APIResponse.error_response(
            message=f"创建对话失败: {str(e)}",
            error_code="CREATE_CONVERSATION_ERROR"
        )


@router.post("/conversations/{conversation_id}/messages", response_model=APIResponse)
async def send_message(
    conversation_id: str,
    request: ChatRequest,
    pipeline: PipelineInterface = Depends(get_pipeline_interface)
):
    """
    发送消息（非流式）
    
    Args:
        conversation_id: 对话ID
        request: 聊天请求
        pipeline: Pipeline接口实例
        
    Returns:
        APIResponse: 响应结果
    """
    try:
        logger.info(f"发送消息: conversation_id={conversation_id}")
        
        # 验证对话ID匹配
        if request.conversation_id != conversation_id:
            raise HTTPException(
                status_code=400,
                detail="请求中的对话ID与URL中的对话ID不匹配"
            )
        
        # 检查对话是否存在
        if conversation_id not in pipeline.active_conversations:
            raise HTTPException(
                status_code=404,
                detail=f"对话不存在: {conversation_id}"
            )
        
        # 收集所有流式响应
        responses = []
        final_content = ""
        
        async for stream_response in pipeline.send_message(
            conversation_id,
            request.message,
            request.user_id
        ):
            responses.append(stream_response.to_dict())
            
            # 收集内容响应
            if stream_response.response_type == "content" and stream_response.content:
                final_content += stream_response.content
        
        # 构建响应
        response_data = {
            "conversation_id": conversation_id,
            "message": final_content,
            "responses": responses,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"消息处理完成: {conversation_id}")
        
        return APIResponse.success_response(
            message="消息发送成功",
            data=response_data
        )
        
    except Exception as e:
        logger.error_with_context(
            e,
            {
                "operation": "send_message",
                "conversation_id": conversation_id,
                "message_length": len(request.message) if request.message else 0
            }
        )
        
        return APIResponse.error_response(
            message=f"发送消息失败: {str(e)}",
            error_code="SEND_MESSAGE_ERROR"
        )


@router.post("/conversations/{conversation_id}/stream")
async def stream_chat(
    conversation_id: str,
    request: ChatRequest,
    pipeline: PipelineInterface = Depends(get_pipeline_interface),
    token: Optional[str] = Depends(optional_token)
):
    """
    流式聊天接口
    
    Args:
        conversation_id: 对话ID
        request: 聊天请求
        pipeline: Pipeline接口实例
        token: 用户认证token
        
    Returns:
        StreamingResponse: 流式响应
    """
    try:
        # 从请求中获取token（优先级：依赖注入 > 请求体）
        user_token = token or request.get_user_token()
        
        logger.info(f"开始流式聊天: conversation_id={conversation_id}")
        
        # DEBUG: 打印流式聊天请求参数
        print("\n" + "="*80)
        print("[DEBUG] 流式聊天API接收到的参数:")
        print(f"  conversation_id: {conversation_id}")
        print(f"  message: {request.message[:100]}..." if len(request.message) > 100 else f"  message: {request.message}")
        print(f"  user_id: {request.user_id}")
        print(f"  knowledge_bases: {request.knowledge_bases}")
        print(f"  knowledge_api_url: {request.knowledge_api_url}")
        print("="*80 + "\n")
        
        # 验证对话ID匹配
        if request.conversation_id != conversation_id:
            raise HTTPException(
                status_code=400,
                detail="请求中的对话ID与URL中的对话ID不匹配"
            )
        
        # 检查对话是否存在
        if conversation_id not in pipeline.active_conversations:
            raise HTTPException(
                status_code=404,
                detail=f"对话不存在: {conversation_id}"
            )
        
        async def generate_stream():
            """生成流式响应"""
            try:
                
                # 直接处理流式响应，不再使用复杂的双重监听机制
                response_count = 0
                content_received = False
                
                async for stream_response in pipeline.send_message(
                    conversation_id,
                    request.message,
                    request.user_id,
                    user_token,
                    request.messages,
                    request.knowledge_bases,
                    request.knowledge_api_url
                ):
                    response_count += 1
                    
                    # 使用新的to_dict方法格式化响应
                    response_data = stream_response.to_dict()
                    json_str = json.dumps(response_data, ensure_ascii=False, indent=None, separators=(',', ':'))
                    
                    
                    yield f"data: {json_str}\n\n"
                    
                    # 检查是否收到内容
                    if response_data.get('type') == 'content' and response_data.get('content'):
                        content_received = True
                
                # 检查是否收到了任何内容
                if not content_received:
                    no_content_data = {
                        'type': 'content',
                        'content': '⚠️ 后端处理完成，但没有返回具体内容。可能是：\n1. 后端配置问题\n2. 模型未正确加载\n3. 任务类型不支持\n\n请检查后端日志或联系管理员。',
                        'conversation_id': conversation_id,
                        'timestamp': datetime.now().isoformat()
                    }
                    yield f"data: {json.dumps(no_content_data, ensure_ascii=False)}\n\n"
                
                # 发送完成状态
                completion_data = {
                    'type': 'status',
                    'stage': 'completed',
                    'status': 'completed',
                    'description': '所有任务已完成',
                    'metadata': {
                        'total_responses': response_count,
                        'content_received': content_received
                    },
                    'timestamp': datetime.now().isoformat()
                }
                yield f"data: {json.dumps(completion_data, ensure_ascii=False)}\n\n"
                
                # 发送结束标记
                yield "data: [DONE]\n\n"
                
                logger.info(f"流式聊天完成: {conversation_id}, 响应数量: {response_count}, 内容接收: {content_received}")
                
            except Exception as e:
                logger.error_with_context(
                    e,
                    {
                        "operation": "generate_stream",
                        "conversation_id": conversation_id
                    }
                )
                
                # 发送错误响应
                error_data = {
                    'type': 'error',
                    'error': f"流式处理错误: {str(e)}",
                    'code': 'STREAM_ERROR',
                    'timestamp': datetime.now().isoformat()
                }
                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                
                # 发送结束标记
                yield "data: [DONE]\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream; charset=utf-8",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream; charset=utf-8",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*"
            }
        )
        
    except Exception as e:
        logger.error_with_context(
            e,
            {
                "operation": "stream_chat",
                "conversation_id": conversation_id,
                "message_length": len(request.message) if request.message else 0
            }
        )
        
        raise HTTPException(
            status_code=500,
            detail=f"流式聊天失败: {str(e)}"
        )


@router.get("/conversations/{conversation_id}/history", response_model=APIResponse)
async def get_conversation_history(
    conversation_id: str,
    pipeline: PipelineInterface = Depends(get_pipeline_interface)
):
    """
    获取对话历史
    
    Args:
        conversation_id: 对话ID
        pipeline: Pipeline接口实例
        
    Returns:
        APIResponse: 对话历史
    """
    try:
        logger.info(f"获取对话历史: {conversation_id}")
        
        # 检查对话是否存在
        if conversation_id not in pipeline.active_conversations:
            raise HTTPException(
                status_code=404,
                detail=f"对话不存在: {conversation_id}"
            )
        
        # 获取对话历史
        messages = pipeline.get_conversation_history(conversation_id)
        
        # 转换为字典格式
        history_data = {
            "conversation_id": conversation_id,
            "messages": [msg.to_dict() for msg in messages],
            "message_count": len(messages),
            "retrieved_at": datetime.now().isoformat()
        }
        
        return APIResponse.success_response(
            message="对话历史获取成功",
            data=history_data
        )
        
    except Exception as e:
        logger.error_with_context(
            e,
            {
                "operation": "get_conversation_history",
                "conversation_id": conversation_id
            }
        )
        
        return APIResponse.error_response(
            message=f"获取对话历史失败: {str(e)}",
            error_code="GET_HISTORY_ERROR"
        )


@router.get("/conversations/{conversation_id}/summary", response_model=APIResponse)
async def get_conversation_summary(
    conversation_id: str,
    pipeline: PipelineInterface = Depends(get_pipeline_interface)
):
    """
    获取对话摘要
    
    Args:
        conversation_id: 对话ID
        pipeline: Pipeline接口实例
        
    Returns:
        APIResponse: 对话摘要
    """
    try:
        logger.info(f"获取对话摘要: {conversation_id}")
        
        # 检查对话是否存在
        if conversation_id not in pipeline.active_conversations:
            raise HTTPException(
                status_code=404,
                detail=f"对话不存在: {conversation_id}"
            )
        
        # 获取对话摘要
        summary = pipeline.get_conversation_summary(conversation_id)
        
        return APIResponse.success_response(
            message="对话摘要获取成功",
            data=summary
        )
        
    except Exception as e:
        logger.error_with_context(
            e,
            {
                "operation": "get_conversation_summary",
                "conversation_id": conversation_id
            }
        )
        
        return APIResponse.error_response(
            message=f"获取对话摘要失败: {str(e)}",
            error_code="GET_SUMMARY_ERROR"
        )


@router.get("/conversations", response_model=APIResponse)
async def list_conversations(
    user_id: Optional[str] = None,
    pipeline: PipelineInterface = Depends(get_pipeline_interface)
):
    """
    列出活跃对话
    
    Args:
        user_id: 用户ID（可选，用于过滤）
        pipeline: Pipeline接口实例
        
    Returns:
        APIResponse: 对话列表
    """
    try:
        logger.info(f"列出活跃对话: user_id={user_id}")
        
        # 获取对话列表
        conversations = pipeline.list_active_conversations(user_id)
        
        response_data = {
            "conversations": conversations,
            "total_count": len(conversations),
            "user_id": user_id,
            "retrieved_at": datetime.now().isoformat()
        }
        
        return APIResponse.success_response(
            message="对话列表获取成功",
            data=response_data
        )
        
    except Exception as e:
        logger.error_with_context(
            e,
            {
                "operation": "list_conversations",
                "user_id": user_id
            }
        )
        
        return APIResponse.error_response(
            message=f"获取对话列表失败: {str(e)}",
            error_code="LIST_CONVERSATIONS_ERROR"
        )


@router.delete("/conversations/{conversation_id}", response_model=APIResponse)
async def close_conversation(
    conversation_id: str,
    pipeline: PipelineInterface = Depends(get_pipeline_interface)
):
    """
    关闭对话会话
    
    Args:
        conversation_id: 对话ID
        pipeline: Pipeline接口实例
        
    Returns:
        APIResponse: 关闭结果
    """
    try:
        logger.info(f"关闭对话会话: {conversation_id}")
        
        # 关闭对话
        success = pipeline.close_conversation(conversation_id)
        
        if success:
            return APIResponse.success_response(
                message="对话关闭成功",
                data={"conversation_id": conversation_id, "closed_at": datetime.now().isoformat()}
            )
        else:
            return APIResponse.error_response(
                message="对话不存在或已关闭",
                error_code="CONVERSATION_NOT_FOUND"
            )
        
    except Exception as e:
        logger.error_with_context(
            e,
            {
                "operation": "close_conversation",
                "conversation_id": conversation_id
            }
        )
        
        return APIResponse.error_response(
            message=f"关闭对话失败: {str(e)}",
            error_code="CLOSE_CONVERSATION_ERROR"
        )


@router.get("/statistics", response_model=APIResponse)
async def get_pipeline_statistics(
    pipeline: PipelineInterface = Depends(get_pipeline_interface)
):
    """
    获取Pipeline统计信息
    
    Args:
        pipeline: Pipeline接口实例
        
    Returns:
        APIResponse: 统计信息
    """
    try:
        logger.info("获取Pipeline统计信息")
        
        # 获取统计信息
        stats = pipeline.get_statistics()
        
        return APIResponse.success_response(
            message="统计信息获取成功",
            data=stats
        )
        
    except Exception as e:
        logger.error_with_context(e, {"operation": "get_pipeline_statistics"})
        
        return APIResponse.error_response(
            message=f"获取统计信息失败: {str(e)}",
            error_code="GET_STATISTICS_ERROR"
        )
