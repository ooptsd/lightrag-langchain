"""Token budget 截断和计算工具。

纯计算模块——无 I/O、无外部 API 调用、默认非异步。使用 tiktoken 进行精确的
BPE tokenization，匹配上游 LightRAG 的 TiktokenTokenizer（gpt-4o-mini 编码）。

提供：
  - truncate_entities_by_tokens()——实体列表截断（D-17）
  - truncate_relations_by_tokens()——关系列表截断（D-17）
  - compute_chunk_token_budget()——剩余 token 分配（D-17）
  - 用于 Phase 4/6 pipeline 兼容性的异步包装器（D-19）

Token budget 不变量（max_entity_tokens + max_relation_tokens < max_total_tokens）
在配置验证时（Phase 1 QueryParamsConfig）强制执行——不在此处（D-20）。

验证：LLM-05 需求。
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Internal tokenizer factory
# ---------------------------------------------------------------------------


def _get_tokenizer(model_name: str = "gpt-4o-mini"):
    """为指定模型惰性加载 tiktoken 编码器。

    tiktoken 是惰性导入的，因此模块可以在未预装 tiktoken 的情况下导入
    （仅在调用函数时才需要）。

    对于无法识别的模型名称（例如 DeepSeek、自定义 provider），回退到
    ``"gpt-4o-mini"``（o200k_base 编码）。

    Args:
        model_name: tiktoken 模型编码名称。默认 ``"gpt-4o-mini"``。

    Returns:
        tiktoken.Encoding 实例。

    Raises:
        ImportError: 如果未安装 tiktoken。
    """
    import tiktoken

    try:
        return tiktoken.encoding_for_model(model_name)
    except KeyError:
        return tiktoken.encoding_for_model("gpt-4o-mini")


# ---------------------------------------------------------------------------
# Serialization helper
# ---------------------------------------------------------------------------


def _serialize_item(item: dict[str, Any]) -> str:
    """序列化单个实体/关系字典以进行 token 计数。

    格式：每行一个 ``key: value`` 对，跳过 None 值。
    匹配上游 LightRAG 用于上下文组装的典型序列化模式。

    Args:
        item: 包含字符串键和可选值的字典。

    Returns:
        以换行符连接的 ``key: value`` 对字符串。
    """
    return "\n".join(f"{k}: {v}" for k, v in item.items() if v is not None)


# ---------------------------------------------------------------------------
# Entity truncation
# ---------------------------------------------------------------------------


def truncate_entities_by_tokens(
    entities: list[dict[str, Any]],
    max_tokens: int,
    model: str = "gpt-4o-mini",
) -> list[dict[str, Any]]:
    """返回实体列表的累积 token 计数在限制内的前缀。

    按顺序遍历实体，通过 tiktoken 序列化每个实体并累积 token 计数。
    在第一个会导致累积计数超过 *max_tokens* 的实体处停止，并返回到该条目
    （但不包括）为止的切片。

    Args:
        entities: 实体字典（entity_name、content、source_id 等）。
        max_tokens: 序列化列表的硬性 token 上限。
        model: tiktoken 模型名称（默认 ``"gpt-4o-mini"``）。

    Returns:
        *entities* 中序列化后 token 计数 <= *max_tokens* 的前缀。
        当 *max_tokens* <= 0 或第一个实体单独就已超过限制时，返回空列表
        （不返回部分实体）。

    Example:
        ```python
        from lightrag_langchain.token_budget import truncate_entities_by_tokens

        entities = [{"entity_name": "东莞", "content": "..."}]
        truncated = truncate_entities_by_tokens(entities, max_tokens=6000)
        print(len(truncated))
        ```
    """
    if max_tokens <= 0:
        return []

    enc = _get_tokenizer(model)
    cumulative = 0

    for i, entity in enumerate(entities):
        serialized = _serialize_item(entity)
        cumulative += len(enc.encode(serialized))
        if cumulative > max_tokens:
            return entities[:i]

    return entities


# ---------------------------------------------------------------------------
# Relation truncation
# ---------------------------------------------------------------------------


def truncate_relations_by_tokens(
    relations: list[dict[str, Any]],
    max_tokens: int,
    model: str = "gpt-4o-mini",
) -> list[dict[str, Any]]:
    """返回关系列表的累积 token 计数在限制内的前缀。

    算法与 :func:`truncate_entities_by_tokens` 相同，但操作对象为关系字典。
    作为独立函数存在，以便调用者在 Phase 4/6 pipeline 中清晰区分实体与关系上下文。

    Args:
        relations: 关系字典（src_id、tgt_id、content、description 等）。
        max_tokens: 序列化列表的硬性 token 上限。
        model: tiktoken 模型名称（默认 ``"gpt-4o-mini"``）。

    Returns:
        *relations* 中序列化后 token 计数 <= *max_tokens* 的前缀。
        当 *max_tokens* <= 0 或第一个关系单独就已超过限制时，返回空列表。

    Example:
        ```python
        from lightrag_langchain.token_budget import truncate_relations_by_tokens

        relations = [{"src_id": "1", "tgt_id": "2", "description": "..."}]
        truncated = truncate_relations_by_tokens(relations, max_tokens=8000)
        print(len(truncated))
        ```
    """
    if max_tokens <= 0:
        return []

    enc = _get_tokenizer(model)
    cumulative = 0

    for i, relation in enumerate(relations):
        serialized = _serialize_item(relation)
        cumulative += len(enc.encode(serialized))
        if cumulative > max_tokens:
            return relations[:i]

    return relations


# ---------------------------------------------------------------------------
# Chunk budget calculation
# ---------------------------------------------------------------------------


def compute_chunk_token_budget(
    total_tokens: int,
    sys_prompt_tokens: int,
    query_tokens: int,
    entity_tokens_used: int,
    relation_tokens_used: int,
    buffer_tokens: int = 200,
) -> int:
    """计算 chunk 内容的剩余 token 容量。

    公式（匹配上游 LightRAG 顺序）：
      remaining = total_tokens
                - sys_prompt_tokens
                - query_tokens
                - entity_tokens_used
                - relation_tokens_used
                - buffer_tokens

    Args:
        total_tokens: 最大总 token 数（来自 QueryParamsConfig）。
        sys_prompt_tokens: 系统 prompt 的 token 数。
        query_tokens: 用户查询的 token 数。
        entity_tokens_used: 截断后实体列表消耗的 token 数。
        relation_tokens_used: 截断后关系列表消耗的 token 数。
        buffer_tokens: 用于 prompt 格式化开销的安全缓冲
            （默认 200，匹配上游 LightRAG）。

    Returns:
        非负整数——chunk 内容的剩余 token 预算。
        当预算耗尽时返回 0（绝不返回负数）。

    Example:
        ```python
        from lightrag_langchain.token_budget import compute_chunk_token_budget

        budget = compute_chunk_token_budget(
            total_tokens=30000,
            sys_prompt_tokens=500,
            query_tokens=50,
            entity_tokens_used=4000,
            relation_tokens_used=6000,
        )
        print(f"Chunk budget: {budget} tokens")
        ```
    """
    kg_tokens = entity_tokens_used + relation_tokens_used
    remaining = total_tokens - (sys_prompt_tokens + query_tokens + kg_tokens + buffer_tokens)
    return max(0, remaining)


# ---------------------------------------------------------------------------
# Async wrappers (D-19 — thin wrappers for Phase 4/6 pipeline compatibility)
# ---------------------------------------------------------------------------


async def atruncate_entities_by_tokens(
    entities: list[dict[str, Any]],
    max_tokens: int,
    model: str = "gpt-4o-mini",
) -> list[dict[str, Any]]:
    """:func:`truncate_entities_by_tokens` 的异步包装器。

    核心计算是纯函数（无 I/O）；异步仅用于 Phase 4/6
    异步上下文的 pipeline 兼容性。
    """
    return truncate_entities_by_tokens(entities, max_tokens, model)


async def atruncate_relations_by_tokens(
    relations: list[dict[str, Any]],
    max_tokens: int,
    model: str = "gpt-4o-mini",
) -> list[dict[str, Any]]:
    """:func:`truncate_relations_by_tokens` 的异步包装器。"""
    return truncate_relations_by_tokens(relations, max_tokens, model)


async def acompute_chunk_token_budget(
    total_tokens: int,
    sys_prompt_tokens: int,
    query_tokens: int,
    entity_tokens_used: int,
    relation_tokens_used: int,
    buffer_tokens: int = 200,
) -> int:
    """:func:`compute_chunk_token_budget` 的异步包装器。"""
    return compute_chunk_token_budget(
        total_tokens,
        sys_prompt_tokens,
        query_tokens,
        entity_tokens_used,
        relation_tokens_used,
        buffer_tokens,
    )
