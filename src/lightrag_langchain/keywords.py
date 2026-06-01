"""lightrag-langchain 的结构化输出关键词提取。

复用上游 LightRAG 经过验证的 prompt 模板，但将脆弱的 json_repair 解析路径
替换为 LangChain 的 ``with_structured_output(KeywordsSchema)``，以实现类型安全
的提取。

用法::

    from lightrag_langchain.config import settings
    from lightrag_langchain.llm import create_llm
    from lightrag_langchain.keywords import extract_keywords

    llm = create_llm(settings.llm)
    result = await extract_keywords(
        query="启动东莞市防风Ⅰ级应急响应",
        llm=llm,
        language=settings.query_params.keyword_language,
    )
    # result.high_level_keywords, result.low_level_keywords
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from langchain_openai import ChatOpenAI


# ---------------------------------------------------------------------------
# Structured output model (D-10)
# ---------------------------------------------------------------------------


class KeywordsSchema(BaseModel):
    """用于从用户查询中提取关键词的结构化输出。

    冻结以防止提取后的意外修改。

    Example:
        ```python
        from lightrag_langchain.keywords import extract_keywords, KeywordsSchema

        # result 是一个包含 high_level_keywords 和 low_level_keywords
        # 字段的 KeywordsSchema 实例
        result: KeywordsSchema = await extract_keywords(query, llm, language="Chinese")
        print(result.high_level_keywords, result.low_level_keywords)
        ```
    """

    model_config = ConfigDict(frozen=True)

    high_level_keywords: list[str]
    """总体概念或主题——用户的核心意图、主题领域或应急响应级别类型。"""

    low_level_keywords: list[str]
    """具体实体或细节——机构（包含城市名称）、专有名词、专业术语、
    基础设施、灾害事件、地理特征。"""


# ---------------------------------------------------------------------------
# Upstream LightRAG prompt template — embedded verbatim (D-11)
# ---------------------------------------------------------------------------

# Source: upstream LightRAG lightrag/prompt.py L:325-349, copied 2026-05-30
KEYWORDS_EXTRACTION_PROMPT = """---角色---
你是一位专业的关键词提取专家，专门为用户查询分析提取关键词，以用于面向应急管理和"三防"（防汛、防旱、防风、防冻）领域的检索增强生成（RAG）系统。你的目标是识别用户查询中的高层和低层关键词，用于有效的文档检索。

---目标---
给定用户查询，你的任务是提取两种不同类型的关键词：

1. **high_level_keywords**: 用于表示总体概念或主题，捕捉用户的核心意图、主题领域或所问的应急行动/响应级别类型。
2. **low_level_keywords**: 用于表示具体实体或细节，识别具体机构（包含城市名称）、专有名词（如"六个百分百"等特定机制）、专业术语、基础设施、具体灾害事件或自然地理特征。

---指令与约束---

1. **输出格式**: 你的输出必须是一个合法的 JSON 对象，除此之外不得有任何其他内容。不要在 JSON 前后包含任何解释性文字、Markdown 代码围栏（如 ```json）或任何其他文本。输出将直接被 JSON 解析器解析。
2. **信息来源**: 所有关键词必须明确从用户查询中提取，高层和低层关键词类别都必须包含内容。
3. **简洁有意义**: 关键词应该是简洁的词语或有意义的短语。当多词短语代表单一概念时，优先使用多词短语。
4. **处理边界情况**: 对于过于简单、模糊或无意义的查询，你必须返回一个两种关键词类型均为空列表的 JSON 对象。
5. **语言**: 所有提取的关键词必须使用{language}。专有名词应保留其原始语言。

---示例---
{examples}

---实际数据---
用户查询: {query}

---输出---
输出:"""

# Source: upstream LightRAG lightrag/prompt.py L:351-376, copied 2026-05-30
KEYWORDS_EXTRACTION_EXAMPLES: list[str] = [
    """Example 1:
Query: "启动东莞市防风Ⅰ级应急响应后，东莞市三防指挥部需要落实哪些‘五停’措施？"
Output:
{
"high_level_keywords": ["防风Ⅰ级应急响应", "应急处置", "响应措施", "指挥调度"],
"low_level_keywords": ["东莞市", "东莞市三防指挥部", "五停", "停工", "停产", "停课", "停运", "停业"]
}
""",
    """Example 2:
Query: "针对孤寡老人和留守儿童，广州市防汛预案中有哪些临灾转移和安置机制？"
Output:
{
"high_level_keywords": ["防汛预案", "临灾转移", "安置机制", "避险转移"],
"low_level_keywords": ["广州市", "孤寡老人", "留守儿童", "弱势群体", "应急避难场所"]
}
""",
    """Example 3:
Query: "当珠江流域发生超标准特大洪水时，水库和海堤的应急抢险物资储备标准是什么？"
Output:
{
"high_level_keywords": ["超标准特大洪水", "抢险物资储备", "防洪标准", "应急抢险"],
"low_level_keywords": ["珠江流域", "水库", "海堤", "冲锋舟", "沙袋", "抢险设备"]
}
""",
]


# ---------------------------------------------------------------------------
# Keyword extraction function (D-10, D-11, D-13, D-14)
# ---------------------------------------------------------------------------


async def extract_keywords(
    query: str,
    llm: ChatOpenAI,  # type: ignore[valid-type]  # duck-typed — any with_structured_output impl
    language: str = "Chinese",
) -> KeywordsSchema:
    """通过 LLM 从用户查询中提取高层和低层关键词。

    使用查询、示例和语言格式化上游 LightRAG prompt 模板，然后调用
    ``llm.with_structured_output(KeywordsSchema, method="json_mode")``
    进行类型安全的提取。

    Parameters
    ----------
    query:
        用户的自然语言查询。
    llm:
        用于提取的 ChatOpenAI（或兼容）实例。必须支持
        ``with_structured_output()``。
    language:
        提取关键词的目标语言。默认为 ``"Chinese"``（根据 D-13）。
        通常取自 ``settings.query_params.keyword_language``。

    Returns
    -------
    KeywordsSchema
        包含 LLM 提取的 ``high_level_keywords`` 和 ``low_level_keywords``
        的冻结模型。

    Notes
    -----
    - 无缓存（D-12）——每次调用都会调用 LLM。
    - 无 json_repair 回退（D-14）——结构化输出失败会传播。
    - ``method="json_mode"`` 避免了 API 请求中的 ``tool_choice``，后者与
      DeepSeek v4-pro 的 thinking（reasoning）模式不兼容。关键词提取 prompt
      已经指示模型输出 JSON。

    Example:
        ```python
        from lightrag_langchain.config import settings
        from lightrag_langchain.llm import create_llm
        from lightrag_langchain.keywords import extract_keywords

        llm = create_llm(settings.llm)
        result = await extract_keywords(
            query="启动东莞市防风Ⅰ级应急响应",
            llm=llm,
            language=settings.query_params.keyword_language,
        )
        print(result.high_level_keywords, result.low_level_keywords)
        ```
    """
    # Assemble examples into a single formatted string.
    examples_str = "\n".join(KEYWORDS_EXTRACTION_EXAMPLES)

    # Format the prompt template with all required placeholders.
    prompt = KEYWORDS_EXTRACTION_PROMPT.format(
        query=query,
        examples=examples_str,
        language=language,
    )

    # Create a structured LLM with json_mode to avoid tool_choice
    # incompatibility with DeepSeek v4-pro thinking (reasoning) mode.
    structured_llm = llm.with_structured_output(
        KeywordsSchema,
        method="json_mode",
    )

    # Extract keywords via async LLM call.
    result: KeywordsSchema = await structured_llm.ainvoke(prompt)

    return result
