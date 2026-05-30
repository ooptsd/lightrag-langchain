"""Token budget truncation and calculation utilities.

Pure computation module — no I/O, no external API calls, no async by default.
Uses tiktoken for accurate BPE tokenization matching upstream LightRAG's
TiktokenTokenizer (gpt-4o-mini encoding).

Provides:
  - truncate_entities_by_tokens() — entity list truncation (D-17)
  - truncate_relations_by_tokens() — relation list truncation (D-17)
  - compute_chunk_token_budget() — remaining token allocation (D-17)
  - Async wrappers for Phase 4/6 pipeline compatibility (D-19)

Token budget invariant (max_entity_tokens + max_relation_tokens < max_total_tokens)
is enforced at config validation time (Phase 1 QueryParamsConfig) — not here (D-20).

Validates: LLM-05 requirements.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Internal tokenizer factory
# ---------------------------------------------------------------------------


def _get_tokenizer(model_name: str = "gpt-4o-mini"):
    """Lazy-load tiktoken encoder for the given model.

    tiktoken is imported lazily so the module can be imported without
    tiktoken pre-installed (only needed when functions are called).

    Args:
        model_name: tiktoken model encoding name. Default "gpt-4o-mini"
            (o200k_base encoding, also valid for gpt-4o).

    Returns:
        tiktoken.Encoding instance.

    Raises:
        ImportError: If tiktoken is not installed.
        KeyError: If model_name is not recognised by tiktoken.
    """
    import tiktoken

    return tiktoken.encoding_for_model(model_name)


# ---------------------------------------------------------------------------
# Serialization helper
# ---------------------------------------------------------------------------


def _serialize_item(item: dict[str, Any]) -> str:
    """Serialize a single entity/relation dict for token counting.

    Format: one ``key: value`` pair per line, skipping None values.
    Matches upstream LightRAG's typical serialization pattern for
    context assembly.

    Args:
        item: Dict with string keys and optional values.

    Returns:
        Newline-joined string of ``key: value`` pairs.
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
    """Return a prefix of the entity list whose cumulative token count fits.

    Iterates entities in order, serializing each and accumulating token
    counts via tiktoken.  Stops at the first entity that would cause the
    cumulative count to exceed *max_tokens* and returns the slice up to
    (but not including) that item.

    Args:
        entities: Entity dicts (entity_name, content, source_id, …).
        max_tokens: Hard token ceiling for the serialized list.
        model: tiktoken model name (default ``"gpt-4o-mini"``).

    Returns:
        Prefix of *entities* whose serialized token count <= *max_tokens*.
        Empty list when *max_tokens* <= 0 or when the first entity alone
        already exceeds the limit (no partial entities).
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
    """Return a prefix of the relation list whose cumulative token count fits.

    Identical algorithm to :func:`truncate_entities_by_tokens` but operating
    on relation dicts.  Exists as a separate function for caller clarity
    (entity vs. relation context in Phase 4/6 pipeline).

    Args:
        relations: Relation dicts (src_id, tgt_id, content, description, …).
        max_tokens: Hard token ceiling for the serialized list.
        model: tiktoken model name (default ``"gpt-4o-mini"``).

    Returns:
        Prefix of *relations* whose serialized token count <= *max_tokens*.
        Empty list when *max_tokens* <= 0 or when the first relation alone
        already exceeds the limit.
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
    """Calculate remaining token capacity for chunk content.

    Formula (matching upstream LightRAG order):
      remaining = total_tokens
                - sys_prompt_tokens
                - query_tokens
                - entity_tokens_used
                - relation_tokens_used
                - buffer_tokens

    Args:
        total_tokens: Maximum total tokens (from QueryParamsConfig).
        sys_prompt_tokens: Token count of the system prompt.
        query_tokens: Token count of the user query.
        entity_tokens_used: Tokens consumed by truncated entity list.
        relation_tokens_used: Tokens consumed by truncated relation list.
        buffer_tokens: Safety buffer for prompt formatting overhead
            (default 200, matching upstream LightRAG).

    Returns:
        Non-negative integer — the remaining token budget for chunk content.
        Returns 0 when the budget is exhausted (never negative).
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
    """Async wrapper for :func:`truncate_entities_by_tokens`.

    Core computation is pure (no I/O); async exists only for pipeline
    compatibility with Phase 4/6 async contexts.
    """
    return truncate_entities_by_tokens(entities, max_tokens, model)


async def atruncate_relations_by_tokens(
    relations: list[dict[str, Any]],
    max_tokens: int,
    model: str = "gpt-4o-mini",
) -> list[dict[str, Any]]:
    """Async wrapper for :func:`truncate_relations_by_tokens`."""
    return truncate_relations_by_tokens(relations, max_tokens, model)


async def acompute_chunk_token_budget(
    total_tokens: int,
    sys_prompt_tokens: int,
    query_tokens: int,
    entity_tokens_used: int,
    relation_tokens_used: int,
    buffer_tokens: int = 200,
) -> int:
    """Async wrapper for :func:`compute_chunk_token_budget`."""
    return compute_chunk_token_budget(
        total_tokens,
        sys_prompt_tokens,
        query_tokens,
        entity_tokens_used,
        relation_tokens_used,
        buffer_tokens,
    )
