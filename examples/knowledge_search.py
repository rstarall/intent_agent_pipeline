import requests
import json

def query_doc(base_url, token, collection_name, query, k=5):
    """
    调用知识库查询接口
    
    Args:
        base_url: Open WebUI的基础URL
        token: 用户token
        collection_name: 文档集合ID（注意：需要传入知识库ID，不是名称）
        query: 查询内容
        k: 返回结果数量
    
    Returns:
        dict: 查询结果，格式如下：
        {
            "ids": [["doc_id_1", "doc_id_2", "doc_id_3"]],
            "documents": [["文档内容1", "文档内容2", "文档内容3"]],
            "metadatas": [
                [
                    {"filename": "file1.txt", "source": "upload", "page": 1},
                    {"filename": "file2.pdf", "source": "upload", "page": 2},
                    {"filename": "file3.docx", "source": "upload", "page": 1}
                ]
            ],
            "distances": [[0.85, 0.72, 0.68]]
        }
    """
    url = f"{base_url.rstrip('/')}/api/v1/retrieval/query/doc"
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    data = {
        "collection_name": collection_name,
        "query": query,
        "k": k
    }
    
    # 不支持 k_reranker, r, hybrid 等参数
    
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    
    return response.json()

# 返回结构示例:
"""
{
    "ids": [["chunk_1", "chunk_2", "chunk_3"]],
    "documents": [
        [
            "这是第一个文档片段的内容，包含相关的信息...",
            "这是第二个文档片段的内容，也包含相关信息...",
            "这是第三个文档片段的内容，同样包含相关信息..."
        ]
    ],
    "metadatas": [
        [
            {
                "filename": "技术文档.pdf",
                "source": "upload",
                "page": 1,
                "timestamp": "2024-01-01T00:00:00Z"
            },
            {
                "filename": "用户手册.docx", 
                "source": "upload",
                "page": 3,
                "timestamp": "2024-01-02T00:00:00Z"
            },
            {
                "filename": "FAQ.txt",
                "source": "upload", 
                "page": 1,
                "timestamp": "2024-01-03T00:00:00Z"
            }
        ]
    ],
    "distances": [[0.92, 0.85, 0.78]]
}
"""