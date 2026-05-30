"""Unit tests for token budget truncation and calculation functions.

Validates: LLM-05 requirements.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Test data factories
# ---------------------------------------------------------------------------


def _make_entity(name: str, source_id: str, *, content_multiplier: int = 3) -> dict:
    """Create a token-heavy entity dict matching Phase 2 data model shape."""
    return {
        "entity_name": name,
        "content": "负责全市应急管理工作，包括安全生产监督、防灾减灾、应急救援等职能。" * content_multiplier,
        "source_id": source_id,
        "file_path": "/data/doc1.txt",
    }


def _make_relation(
    src_id: str,
    tgt_id: str,
    *,
    content_multiplier: int = 3,
) -> dict:
    """Create a token-heavy relation dict matching Phase 2 data model shape."""
    return {
        "src_id": src_id,
        "tgt_id": tgt_id,
        "content": "该部门负责统筹协调全市应急管理工作，指导各区县应急管理局业务。" * content_multiplier,
        "description": "上下级业务指导关系",
    }


# ---------------------------------------------------------------------------
# Entity truncation tests
# ---------------------------------------------------------------------------


def test_truncate_entities_respects_limit():
    """Test 1: Entity list truncated when serialized token count exceeds limit.

    Given 5 token-heavy entity dicts and max_tokens=50, truncation should
    stop before cumulative count exceeds 50, returning fewer than 5 entities.
    """
    from lightrag_langchain.token_budget import truncate_entities_by_tokens

    entities = [
        _make_entity("东莞市应急管理局", "ent-001"),
        _make_entity("深圳市应急管理局", "ent-002"),
        _make_entity("广州市应急管理局", "ent-003"),
        _make_entity("珠海市应急管理局", "ent-004"),
        _make_entity("佛山市应急管理局", "ent-005"),
    ]

    result = truncate_entities_by_tokens(entities, max_tokens=50)

    assert len(result) < 5, f"Expected <5, got {len(result)}"
    # Verify it's a prefix: first N items match original
    for i, item in enumerate(result):
        assert item["entity_name"] == entities[i]["entity_name"]


def test_truncate_entities_empty_list():
    """Test 2: Empty entity list returns empty list."""
    from lightrag_langchain.token_budget import truncate_entities_by_tokens

    result = truncate_entities_by_tokens([], max_tokens=100)

    assert result == []


def test_truncate_entities_all_fit():
    """Test 3: All entities fit within a generous token budget."""
    from lightrag_langchain.token_budget import truncate_entities_by_tokens

    entities = [
        _make_entity("Engine-S", "ent-a", content_multiplier=1),
        _make_entity("Engine-T", "ent-b", content_multiplier=1),
    ]

    result = truncate_entities_by_tokens(entities, max_tokens=2000)

    assert len(result) == 2
    assert result[0]["entity_name"] == "Engine-S"
    assert result[1]["entity_name"] == "Engine-T"


def test_truncate_entities_zero_tokens_returns_empty():
    """Test: max_tokens=0 returns empty list (no room for any entity)."""
    from lightrag_langchain.token_budget import truncate_entities_by_tokens

    entities = [_make_entity("Test", "ent-x", content_multiplier=1)]

    result = truncate_entities_by_tokens(entities, max_tokens=0)

    assert result == []


def test_truncate_entities_negative_tokens_returns_empty():
    """Test: max_tokens < 0 returns empty list (safety boundary)."""
    from lightrag_langchain.token_budget import truncate_entities_by_tokens

    entities = [_make_entity("Test", "ent-x", content_multiplier=1)]

    result = truncate_entities_by_tokens(entities, max_tokens=-5)

    assert result == []


def test_truncate_entities_single_entity_too_large():
    """Test: When first entity alone exceeds max_tokens, return empty list.

    No partial entities — truncation is all-or-nothing per item.
    """
    from lightrag_langchain.token_budget import truncate_entities_by_tokens

    entities = [_make_entity("HugeEntity", "ent-big", content_multiplier=10)]

    result = truncate_entities_by_tokens(entities, max_tokens=10)

    assert result == []


# ---------------------------------------------------------------------------
# Relation truncation tests
# ---------------------------------------------------------------------------


def test_truncate_relations_respects_limit():
    """Test 4: Relation list truncated when token count exceeds limit.

    Given 3 token-heavy relation dicts and max_tokens=40, truncation
    should return fewer than 3 relations.
    """
    from lightrag_langchain.token_budget import truncate_relations_by_tokens

    relations = [
        _make_relation("ent-001", "ent-002"),
        _make_relation("ent-002", "ent-003"),
        _make_relation("ent-003", "ent-004"),
    ]

    result = truncate_relations_by_tokens(relations, max_tokens=40)

    assert len(result) < 3, f"Expected <3, got {len(result)}"
    # Verify it's a prefix
    for i, item in enumerate(result):
        assert item["src_id"] == relations[i]["src_id"]


def test_truncate_relations_empty_list():
    """Test: Empty relation list returns empty list."""
    from lightrag_langchain.token_budget import truncate_relations_by_tokens

    result = truncate_relations_by_tokens([], max_tokens=100)

    assert result == []


def test_truncate_relations_all_fit():
    """Test: All relations fit within a large budget."""
    from lightrag_langchain.token_budget import truncate_relations_by_tokens

    relations = [
        _make_relation("a", "b", content_multiplier=1),
        _make_relation("b", "c", content_multiplier=1),
    ]

    result = truncate_relations_by_tokens(relations, max_tokens=2000)

    assert len(result) == 2


# ---------------------------------------------------------------------------
# Chunk budget calculation tests
# ---------------------------------------------------------------------------


def test_compute_chunk_budget_basic():
    """Test 5: Budget formula with default buffer=200.

    total=30000, sys=150, query=50, entity=4000, relation=3000, buffer=200
    → 30000 - (150 + 50 + 4000 + 3000 + 200) = 22600
    """
    from lightrag_langchain.token_budget import compute_chunk_token_budget

    remaining = compute_chunk_token_budget(
        total_tokens=30000,
        sys_prompt_tokens=150,
        query_tokens=50,
        entity_tokens_used=4000,
        relation_tokens_used=3000,
    )
    # Default buffer = 200
    assert remaining == 22600, f"Expected 22600, got {remaining}"


def test_compute_chunk_budget_custom_buffer():
    """Test 6: Budget formula with explicit buffer=500.

    total=30000, sys=150, query=50, entity=4000, relation=3000, buffer=500
    → 30000 - (150 + 50 + 4000 + 3000 + 500) = 22300
    """
    from lightrag_langchain.token_budget import compute_chunk_token_budget

    remaining = compute_chunk_token_budget(
        total_tokens=30000,
        sys_prompt_tokens=150,
        query_tokens=50,
        entity_tokens_used=4000,
        relation_tokens_used=3000,
        buffer_tokens=500,
    )
    assert remaining == 22300, f"Expected 22300, got {remaining}"


def test_compute_chunk_budget_zero_remaining():
    """Test 7: Tight budget where costs exceed total → returns 0, never negative.

    total=1000, sys=300, query=200, entity=300, relation=300, buffer=200
    → 1000 - (300 + 200 + 300 + 300 + 200) = -300 → clipped to 0
    """
    from lightrag_langchain.token_budget import compute_chunk_token_budget

    remaining = compute_chunk_token_budget(
        total_tokens=1000,
        sys_prompt_tokens=300,
        query_tokens=200,
        entity_tokens_used=300,
        relation_tokens_used=300,
        buffer_tokens=200,
    )
    assert remaining == 0, f"Expected 0 (floor), got {remaining}"


def test_compute_chunk_budget_exact_zero():
    """Test: Budget exactly zero remaining — returns 0."""
    from lightrag_langchain.token_budget import compute_chunk_token_budget

    remaining = compute_chunk_token_budget(
        total_tokens=1000,
        sys_prompt_tokens=200,
        query_tokens=100,
        entity_tokens_used=300,
        relation_tokens_used=200,
        buffer_tokens=200,
    )
    # 1000 - (200 + 100 + 300 + 200 + 200) = 0
    assert remaining == 0


# ---------------------------------------------------------------------------
# Async wrapper tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_wrappers_exist():
    """Test 8: Async wrappers are importable and produce same results as sync.

    atruncate_entities_by_tokens, atruncate_relations_by_tokens,
    acompute_chunk_token_budget — all return same results when awaited.
    """
    from lightrag_langchain.token_budget import (
        atruncate_entities_by_tokens,
        atruncate_relations_by_tokens,
        acompute_chunk_token_budget,
        truncate_entities_by_tokens,
        truncate_relations_by_tokens,
        compute_chunk_token_budget,
    )

    entities = [
        _make_entity("Test-Ent", "ent-x", content_multiplier=2),
    ]

    # Entities
    sync_result = truncate_entities_by_tokens(entities, max_tokens=100)
    async_result = await atruncate_entities_by_tokens(entities, max_tokens=100)
    assert sync_result == async_result

    # Relations
    relations = [
        _make_relation("a", "b", content_multiplier=2),
    ]
    sync_rel = truncate_relations_by_tokens(relations, max_tokens=100)
    async_rel = await atruncate_relations_by_tokens(relations, max_tokens=100)
    assert sync_rel == async_rel

    # Budget
    sync_budget = compute_chunk_token_budget(30000, 150, 50, 4000, 3000)
    async_budget = await acompute_chunk_token_budget(30000, 150, 50, 4000, 3000)
    assert sync_budget == async_budget


# ---------------------------------------------------------------------------
# Tokenizer factory test
# ---------------------------------------------------------------------------


def test_tokenizer_uses_correct_model():
    """Test 9: Internal tokenizer factory calls tiktoken.encoding_for_model.

    Verify with patching that the correct model name is passed.
    """
    import tiktoken

    with patch("tiktoken.encoding_for_model", wraps=tiktoken.encoding_for_model) as spy:
        from lightrag_langchain.token_budget import _get_tokenizer

        tokenizer = _get_tokenizer("gpt-4o-mini")
        spy.assert_called_once_with("gpt-4o-mini")
        assert tokenizer is not None

    # Also test default: no arg → should use "gpt-4o-mini"
    with patch("tiktoken.encoding_for_model", wraps=tiktoken.encoding_for_model) as spy2:
        from lightrag_langchain.token_budget import _get_tokenizer

        tokenizer2 = _get_tokenizer()
        spy2.assert_called_once_with("gpt-4o-mini")
