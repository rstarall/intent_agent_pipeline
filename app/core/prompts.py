"""
提示词模板模块

基于SOTA研究的专业提示词模板，支持多阶段工作流。
包含问题扩写、专家分析、任务规划、综合分析等提示词模板。
"""

from typing import Dict, Any, Optional


def build_question_expansion_prompt(current_question: str, history_context: str, 
                                  recent_questions: list) -> str:
    """
    构建问题扩写提示词
    根据历史会话和历史问题对当前问题进行上下文扩写
    
    Args:
        current_question: 当前用户问题
        history_context: 历史会话上下文
        recent_questions: 最近的历史问题列表
        
    Returns:
        问题扩写提示词
    """
    # 构建历史问题列表
    history_questions_text = ""
    if recent_questions:
        history_questions_text = "\n".join([f"- {q}" for q in recent_questions[-5:]])  # 最近5个问题
    else:
        history_questions_text = "无历史问题"
    
    return f"""
作为对话上下文理解专家，您需要基于历史会话和问题，对当前问题进行智能扩写，使其更加完整和准确。

**当前分析任务:**
当前问题: {current_question}

**历史上下文信息:**
历史会话: {history_context}

最近的历史问题:
{history_questions_text}

**扩写要求:**

1. **上下文理解**
   - 分析当前问题与历史会话的关联性
   - 识别问题中可能的省略或简化表达
   - 理解用户在整个会话流程中的真实意图

2. **问题补全与扩写**
   - 基于历史上下文，补全当前问题中的省略信息
   - 明确问题中的指代关系（如"这个"、"它"、"上述"等）
   - 添加必要的背景信息和限定条件
   - 保持问题的核心意图不变

3. **质量控制**
   - 如果当前问题已经很完整，无需大幅修改
   - 扩写后的问题应该更加清晰、具体和可执行
   - 避免过度扩写导致问题偏离原意
   - 保持自然的表达方式

**扩写策略:**
- 若当前问题与历史会话高度相关：进行上下文补全
- 若当前问题是独立的新问题：进行适度优化和明确化
- 若当前问题含有指代词：基于历史信息进行具体化
- 若当前问题过于简单：适当增加细节和背景

以JSON格式返回扩写结果：
{{
    "expanded_question": "扩写后的完整问题，保持原意的同时更加清晰完整",
    "expansion_reasoning": "扩写的理由和依据，说明进行了哪些补全和优化",
    "context_relevance": "high|medium|low - 当前问题与历史上下文的关联度",
    "original_intent": "对用户原始意图的理解总结"
}}

重要：请只返回JSON对象，不要包含任何其他文本。
"""


def build_expert_analysis_prompt(user_question: str, history_context: str) -> str:
    """
    构建专家级别的问题分析提示词
    基于SOTA研究中的structured reasoning和expert analysis模式
    
    Args:
        user_question: 用户问题
        history_context: 对话历史上下文
        
    Returns:
        专家分析提示词
    """
    return f"""
作为一名跨领域专家分析师，您需要对用户问题进行深度、系统性的专业分析。

**当前分析任务:**
用户问题: {user_question}
对话历史: {history_context}

**分析要求:**
您必须以领域专家的身份进行全面分析，严格基于提供的信息，避免任何不当的领域偏见或扩展。

**分析步骤 - 请逐步执行并展示您的分析过程:**

1. **问题理解与解析**
   - 识别问题的核心概念和关键要素
   - 理解问题的具体内容和范围
   - 分析问题可能涉及的主要方面

2. **信息需求识别**
   - 确定回答问题所需的核心信息
   - 识别相关的知识领域和专业内容
   - 理解用户的询问意图和期望

3. **分析策略制定**
   - 确定适合的分析方法和思路
   - 识别问题的复杂程度和层次
   - 规划合理的信息组织方式

请基于以上步骤进行详细分析，每个步骤都要展示您的具体分析过程和结论。

以JSON格式返回分析结果：
{{
    "expert_analysis": "您的详细专业分析内容，至少300字，体现专家级别的深度思考"
}}

重要：请只返回JSON对象，不要包含任何其他文本。
"""


def build_universal_task_planning_prompt(optimized_question: str, analysis_result: str, history_context: str = "") -> str:
    """
    构建通用任务规划提示词
    严格基于用户问题和历史对话生成检索查询
    
    Args:
        optimized_question: 优化后的问题
        analysis_result: 专家分析结果
        history_context: 历史对话上下文
        
    Returns:
        任务规划提示词
    """
    return f"""
作为信息检索专家，您需要严格基于用户问题设计精准的检索查询。

**核心任务:**
用户问题: {optimized_question}
专家分析: {analysis_result}
历史对话: {history_context}

**检索资源:**
- **在线搜索**: 最新信息、实时数据、当前动态
- **知识库检索**: 专业知识、技术文档、权威资料
- **知识图谱检索**: 概念关联、系统关系、深层联系

**查询生成要求:**
1. **严格基于用户问题**: 所有查询都必须围绕用户问题的核心需求
2. **利用历史对话**: 考虑历史对话的上下文和关联
3. **陈述句形式**: 使用陈述句描述需要检索的信息内容
4. **关键词丰富**: 包含问题中的核心概念和相关术语
5. **避免偏离**: 不要扩展到用户问题之外的无关内容

**具体要求:**
- **在线搜索查询**: 针对用户问题的最新信息、实时数据和当前状况，80-120字
- **知识库查询**: 针对用户问题的专业知识、理论基础和系统性内容，60-100字
- **知识图谱查询**: 针对用户问题相关概念的关联关系和深层联系，60-100字

**重要原则:**
- 每个查询都要直接服务于回答用户问题
- 基于专家分析提取的核心要素构建查询
- 结合历史对话的相关信息
- 避免过度扩展和无关内容

以JSON格式返回：
{{
    "tasks": [
        {{"type": "online_search", "query": "针对用户问题的陈述性在线搜索查询"}},
        {{"type": "knowledge_search", "query": "针对用户问题的陈述性知识库查询"}}, 
        {{"type": "lightrag_search", "query": "针对用户问题的陈述性知识图谱查询"}}
    ]
}}

请严格基于用户问题生成检索查询，确保所有查询都直接服务于回答用户问题。
"""


def build_comprehensive_synthesis_prompt(user_question: str, expanded_question: str,
                                       optimized_question: str, results_context: str, 
                                       history_context: str) -> str:
    """
    构建综合性分析回答提示词
    聚焦于直接回答用户问题，避免无用扩展
    
    Args:
        user_question: 用户原始问题
        expanded_question: 扩写后问题
        optimized_question: 优化后问题
        results_context: 检索结果上下文
        history_context: 对话历史上下文
        
    Returns:
        综合分析提示词
    """
    return f"""
作为专业分析师，您需要基于检索信息为用户提供全面、深入、详细的专业回答。

**核心任务:**
用户问题: {user_question}
完整问题: {expanded_question}
优化问题: {optimized_question}

**信息来源:**
检索结果: {results_context}
历史对话: {history_context}

**回答要求:**

**1. 核心原则**
- **全面回答**: 充分、完整地回答用户问题的各个方面和层次
- **基于检索**: 深度挖掘和利用提供的检索结果信息
- **聚焦相关**: 围绕用户问题展开，但要充分延展相关内容
- **结合历史**: 考虑历史对话的上下文和连续性

**2. 详细回答结构**
请按以下结构组织丰富详实的回答：

### 🎯 **核心问题回答**
提供完整、准确的问题回答，确保涵盖问题的主要方面和关键要点

### 📊 **深入分析与详解**  
基于检索结果进行多维度、多层次的深入分析：

#### **背景与现状**
- 详细的背景信息、发展历程和演变过程[引用具体来源]
- 当前状况、主要特征和发展趋势[引用数据支撑]
- 重要统计数据、研究发现和权威观点[标注信息来源]

#### **核心内容详解**
根据问题性质和检索信息，详细展开以下相关内容：
- 核心概念、关键要素的深入解释和机制分析[引用权威来源]
- 重要事实、具体数据和研究发现的详细阐述[引用具体数据]
- 典型案例、实践经验和应用实例的深入分析[引用具体案例]
- 多角度的对比分析、关联性探讨和影响因素分析
- 基于检索信息的深层原理解释和机制探讨

#### **拓展与关联**
基于用户问题相关的延展内容：
- 相关概念、衍生问题和关联领域的探讨
- 不同观点、研究角度和理论框架的对比
- 实际应用、发展前景和潜在影响的分析

### 💡 **深层洞察与总结**
基于全面分析得出的重要发现、深层理解和专业见解

### 📚 **详细信息来源**
完整列出所有引用的检索结果来源：
[1] 在线搜索 - 完整标题 - URL链接 - 关键内容详细摘要
[2] 知识库检索 - 文档完整标题 - 关键内容详细摘要  
[3] 知识图谱 - 概念关系详述 - 关键发现详细摘要

**3. 质量标准**
- **聚焦性**: 所有内容都服务于回答用户问题及其相关延展
- **准确性**: 基于检索结果，确保信息准确可靠有据可查
- **完整性**: 充分回答用户问题的各个方面和深度层次
- **丰富性**: 提供详实充分的内容，深度挖掘检索信息的价值
- **延展性**: 适当延展相关内容，提供更全面的理解视角
- **引用性**: 所有重要信息都要详细标注来源和依据

**重要提醒:**
请充分利用检索结果，提供详实丰富的专业分析。在聚焦用户问题的基础上，充分挖掘相关信息的深度和广度，确保回答内容充实、有价值。
"""


def build_knowledge_base_selection_prompt(query: str, knowledge_bases: list) -> str:
    """
    构建知识库智能选择提示词
    
    Args:
        query: 用户查询
        knowledge_bases: 可用知识库列表
        
    Returns:
        知识库选择提示词
    """
    # 构建知识库描述
    kb_list = []
    for kb in knowledge_bases:
        kb_name = kb.get('name', '未知')
        kb_desc = kb.get('description', '无描述')
        kb_list.append(f'"{kb_name}": {kb_desc}')
    
    kb_descriptions = "\n".join(kb_list)
    valid_names = [kb.get('name', '') for kb in knowledge_bases]
    
    return f"""
根据用户的查询问题，选择最合适的知识库进行检索。

用户查询：{query}

可用的知识库：
{kb_descriptions}

请分析用户查询的内容和意图，选择最相关的知识库。

返回JSON格式：
{{
    "collection_name": "选择的知识库名称",
    "reason": "选择这个知识库的原因（简短说明）"
}}

【重要】collection_name必须严格从上述可用知识库列表中选择，不能使用列表之外的任何名称！
可选择的知识库名称仅限于：{', '.join(valid_names)}
如果不确定选择哪个，请选择第一个知识库。
"""


# 提示词配置常量
class PromptConfig:
    """提示词配置常量"""
    
    # 温度参数
    EXPANSION_TEMPERATURE = 0.4
    ANALYSIS_TEMPERATURE = 0.3
    PLANNING_TEMPERATURE = 0.2
    SYNTHESIS_TEMPERATURE = 0.7
    SELECTION_TEMPERATURE = 0.1
    
    # Token限制
    MAX_EXPANSION_TOKENS = 800
    MAX_ANALYSIS_TOKENS = 1000
    MAX_PLANNING_TOKENS = 800
    MAX_SYNTHESIS_TOKENS = 4000
    
    # 质量标准
    MIN_EXPANSION_LENGTH = 20
    MIN_ANALYSIS_LENGTH = 300
    MIN_SYNTHESIS_LENGTH = 2000
    QUERY_LENGTH_RANGE = (40, 60)
    
    # 系统消息
    JSON_SYSTEM_MESSAGE = "You are a helpful assistant that always responds with valid JSON. Never include any text before or after the JSON object." 