"""
知识库检索示例（使用ID模式）

这个示例展示了正确的知识库检索模式：
1. 先通过名称获取知识库ID
2. 使用ID进行查询
"""

import asyncio
from app.services.knowledge_service import KnowledgeService
from app.config import get_settings
import json


async def main():
    # 配置信息
    settings = get_settings()
    
    # 用户token（需要替换为实际的token）
    USER_TOKEN = "your-user-token-here"
    
    # 创建知识库服务实例
    knowledge_service = KnowledgeService()
    
    try:
        # 1. 获取所有知识库列表
        print("获取知识库列表...")
        knowledge_bases = await knowledge_service.get_knowledge_bases(
            token=USER_TOKEN,
            api_url=settings.openwebui_base_url
        )
        
        if knowledge_bases:
            print(f"\n找到 {len(knowledge_bases)} 个知识库:")
            for kb in knowledge_bases:
                print(f"  - 名称: {kb.get('name')}, ID: {kb.get('id')}")
        else:
            print("未找到任何知识库")
            return
        
        # 2. 根据名称获取知识库ID
        target_kb_name = "test"
        print(f"\n查找名称为 '{target_kb_name}' 的知识库...")
        
        kb_id = await knowledge_service.get_knowledge_base_id_by_name(
            token=USER_TOKEN,
            knowledge_base_name=target_kb_name,
            api_url=settings.openwebui_base_url
        )
        
        if kb_id:
            print(f"找到知识库ID: {kb_id}")
        else:
            print(f"未找到名称为 '{target_kb_name}' 的知识库")
            return
        
        # 3. 使用ID进行查询（方式一：直接使用query_doc）
        query = "你的查询问题"
        print(f"\n使用ID查询（方式一）: {query}")
        
        result1 = await knowledge_service.query_doc(
            token=USER_TOKEN,
            collection_name=kb_id,  # 这里使用ID，参数名仍为collection_name是为了兼容性
            query=query,
            k=5,
            api_url=settings.openwebui_base_url
        )
        
        print("查询结果（方式一）:")
        print(json.dumps(result1, ensure_ascii=False, indent=2))
        
        # 4. 使用名称进行查询（方式二：使用query_doc_by_name，自动处理ID查找）
        print(f"\n使用名称查询（方式二）: {query}")
        
        result2 = await knowledge_service.query_doc_by_name(
            token=USER_TOKEN,
            knowledge_base_name=target_kb_name,  # 直接使用名称
            query=query,
            k=5,
            api_url=settings.openwebui_base_url
        )
        
        print("查询结果（方式二）:")
        print(json.dumps(result2, ensure_ascii=False, indent=2))
        
        # 5. 处理查询结果
        if result2.get("documents"):
            documents = result2["documents"][0] if result2["documents"] else []
            print(f"\n找到 {len(documents)} 个相关文档片段")
            
            for i, doc in enumerate(documents[:3]):  # 只显示前3个结果
                print(f"\n结果 {i+1}:")
                print(f"内容: {doc[:200]}...")  # 只显示前200个字符
        
    except Exception as e:
        print(f"\n发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 关闭连接
        await knowledge_service.close()


# 使用说明
def usage():
    """
    使用说明：
    
    1. 修改 USER_TOKEN 为你的实际访问token
    2. 修改 target_kb_name 为你要查询的知识库名称
    3. 修改 query 为你的查询问题
    4. 运行脚本: python examples/knowledge_search_with_id.py
    
    重要说明：
    - 知识库API需要先通过名称获取ID，然后使用ID进行查询
    - query_doc方法的collection_name参数实际上应该传入知识库ID
    - query_doc_by_name方法会自动处理名称到ID的转换
    """
    print(usage.__doc__)


if __name__ == "__main__":
    # 显示使用说明
    # usage()
    
    # 运行主程序
    asyncio.run(main())