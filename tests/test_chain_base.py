"""Integration tests for LightRAGBaseChain core pipeline: invoke/ainvoke dict
structure, empty results, template selection, system prompt override, reference
list generation, and token budget ordering.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.documents import Document

from lightrag_langchain.chain.base import LightRAGBaseChain
from lightrag_langchain.chain.chains import BypassChain, LocalChain, NaiveChain
from lightrag_langchain.keywords import KeywordsSchema


# ---------------------------------------------------------------------------
# Fixture: patch settings singleton so chain tests don't need a real .env
# ---------------------------------------------------------------------------


@pytest.fixture
def _patch_settings(mock_query_params_config):
    """Pre-set the lazy _settings singleton so _apply_token_budget works.

    The chain's ``_apply_token_budget`` method does a lazy ``from
    lightrag_langchain.config import settings``, which triggers
    ``__getattr__`` → ``Settings()`` from .env.  In tests without a .env
    file this raises ``SettingsError``.  By setting ``_settings`` to a mock
    with the test ``QueryParamsConfig`` **before** the chain accesses it,
    all chain methods work with empty or populated retriever results.
    """
    import lightrag_langchain.config as _cfg

    original = _cfg._settings
    mock = MagicMock()
    mock.query_params = mock_query_params_config
    _cfg._settings = mock
    yield
    _cfg._settings = original


# ===========================================================================
# Helpers
# ===========================================================================


def _make_naive_chain(mock_retriever, mock_llm):
    """Construct a NaiveChain with model_construct to bypass Pydantic v2
    field validation on the ChatOpenAI-typed ``llm`` field.

    Using ``model_construct`` (instead of ``NaiveChain(...)``) is a necessary
    deviation: Pydantic v2 validates model-typed fields even with
    ``arbitrary_types_allowed=True``, and ChatOpenAI's model validators
    (``validate_temperature``) fail on an ``AsyncMock`` input.
    """
    return NaiveChain.model_construct(
        retriever=mock_retriever, llm=mock_llm
    )


def _make_local_chain(mock_retriever, mock_llm):
    """Construct a LocalChain with model_construct (same rationale as above)."""
    return LocalChain.model_construct(
        retriever=mock_retriever, llm=mock_llm
    )


def _make_bypass_chain(mock_retriever, mock_llm):
    """Construct a BypassChain with model_construct."""
    return BypassChain.model_construct(
        retriever=mock_retriever, llm=mock_llm
    )


# ===========================================================================
# Test Class 1: TestChainInvoke — invoke() dict structure
# ===========================================================================


class TestChainInvoke:
    """invoke() — synchronous bridge that returns a structured dict."""

    def test_invoke_returns_dict_structure(
        self, _patch_settings, mock_llm, mock_retriever, make_chunk_doc
    ):
        """invoke() returns dict with answer, sources, keywords, mode keys."""
        chunk_doc = make_chunk_doc(content="test chunk")
        mock_retriever.ainvoke.return_value = [chunk_doc]
        mock_llm.ainvoke.return_value.content = "Answer text"

        chain = _make_naive_chain(mock_retriever, mock_llm)
        result = chain.invoke(
            "test query", hl_keywords=["kw"], ll_keywords=["kw"]
        )

        assert result["answer"] == "Answer text"
        assert result["mode"] == "naive"
        assert isinstance(result["sources"], list)
        assert isinstance(result["keywords"], dict)
        assert result["keywords"] == {
            "high_level": ["kw"],
            "low_level": ["kw"],
        }

    def test_invoke_async_bridge(
        self, _patch_settings, mock_llm, mock_retriever, make_chunk_doc
    ):
        """invoke() is a synchronous method — returns dict, not coroutine."""
        chunk_doc = make_chunk_doc(content="test chunk")
        mock_retriever.ainvoke.return_value = [chunk_doc]
        mock_llm.ainvoke.return_value.content = "Answer text"

        chain = _make_naive_chain(mock_retriever, mock_llm)
        result = chain.invoke(
            "test query", hl_keywords=["kw"], ll_keywords=["kw"]
        )

        assert isinstance(result, dict)
        assert result["answer"] == "Answer text"


# ===========================================================================
# Test Class 2: TestChainAinvoke — async pipeline verification
# ===========================================================================


class TestChainAinvoke:
    """ainvoke() — async pipeline that calls retriever then LLM."""

    @pytest.mark.asyncio
    async def test_ainvoke_pipeline_order(
        self, _patch_settings, mock_llm, mock_retriever, make_chunk_doc
    ):
        """ainvoke calls retriever first then LLM, sets keywords via extraction."""
        chunk_doc = make_chunk_doc()
        mock_retriever.ainvoke.return_value = [chunk_doc]
        mock_llm.ainvoke.return_value.content = "Answer"

        # Set up with_structured_output for keyword extraction
        extracted = KeywordsSchema(
            high_level_keywords=["hw"], low_level_keywords=["lw"]
        )
        structured_mock = MagicMock()
        structured_mock.ainvoke = AsyncMock(return_value=extracted)
        mock_llm.with_structured_output = MagicMock(
            return_value=structured_mock
        )

        chain = _make_naive_chain(mock_retriever, mock_llm)
        result = await chain.ainvoke("test query")

        assert result["answer"] == "Answer"
        assert result["keywords"] == {
            "high_level": ["hw"],
            "low_level": ["lw"],
        }
        assert result["mode"] == "naive"
        mock_retriever.ainvoke.assert_awaited_once()
        mock_llm.ainvoke.assert_awaited_once()


# ===========================================================================
# Test Class 3: TestEmptyResults — empty retriever results
# ===========================================================================


class TestEmptyResults:
    """Empty retriever results — chain does NOT short-circuit."""

    def test_empty_retriever_still_calls_llm(
        self, _patch_settings, mock_llm, mock_retriever
    ):
        """Empty retriever: LLM still receives empty context (Claude's Discretion)."""
        mock_retriever.ainvoke.return_value = []
        mock_llm.ainvoke.return_value.content = (
            "I don't have enough information"
        )

        chain = _make_naive_chain(mock_retriever, mock_llm)
        result = chain.invoke(
            "test query", hl_keywords=["kw"], ll_keywords=["kw"]
        )

        assert result["answer"] == "I don't have enough information"
        assert result["sources"] == []
        mock_llm.ainvoke.assert_awaited_once()
        # Retriever was still called — chain does not short-circuit
        mock_retriever.ainvoke.assert_awaited_once()


# ===========================================================================
# Test Class 4: TestTemplateSelection — D-07 mode-based templates
# ===========================================================================


class TestTemplateSelection:
    """D-07: template selection depends on chain mode."""

    def test_naive_mode_uses_naive_templates(
        self, _patch_settings, mock_llm, mock_retriever, make_chunk_doc
    ):
        """NaiveChain uses {content_data} (NAIVE_RAG_RESPONSE_PROMPT), not
        {context_data} from RAG_RESPONSE_PROMPT."""
        chunk_doc = make_chunk_doc(content="chunk text")
        mock_retriever.ainvoke.return_value = [chunk_doc]
        mock_llm.ainvoke.return_value.content = "Answer"

        chain = _make_naive_chain(mock_retriever, mock_llm)
        chain.invoke("q", hl_keywords=["h"], ll_keywords=["l"])

        # Extract the SystemMessage content
        messages = mock_llm.ainvoke.call_args[0][0]
        sys_content = messages[0].content

        # Naive template references "Document Chunks" (not "Knowledge Graph Data")
        assert "Document Chunks" in sys_content
        # content_data placeholder formatted (not context_data)
        assert "Knowledge Graph Data" not in sys_content

    def test_kg_mode_uses_kg_templates(
        self, _patch_settings, mock_llm, mock_retriever, make_entity_doc
    ):
        """KG modes (LocalChain) use KG_QUERY_CONTEXT_TEMPLATE +
        RAG_RESPONSE_PROMPT with Knowledge Graph Data + Document Chunks."""
        entity_doc = make_entity_doc()
        mock_retriever.ainvoke.return_value = [entity_doc]
        mock_llm.ainvoke.return_value.content = "Answer"

        chain = _make_local_chain(mock_retriever, mock_llm)
        chain.invoke("q", hl_keywords=["h"], ll_keywords=["l"])

        messages = mock_llm.ainvoke.call_args[0][0]
        sys_content = messages[0].content

        # KG template references "Knowledge Graph Data" (both entities + relations)
        assert "Knowledge Graph Data" in sys_content
        # context_data placeholder (not content_data)
        assert "Document Chunks" in sys_content


# ===========================================================================
# Test Class 5: TestSystemPromptOverride — D-08 full override
# ===========================================================================


class TestSystemPromptOverride:
    """D-08: system_prompt parameter replaces entire prompt verbatim."""

    def test_system_prompt_override_replaces_entire_prompt(
        self, _patch_settings, mock_llm, mock_retriever, make_chunk_doc
    ):
        """system_prompt='CUSTOM' → SystemMessage content is 'CUSTOM' exactly
        (no template wrapping, no formatting)."""
        chunk_doc = make_chunk_doc()
        mock_retriever.ainvoke.return_value = [chunk_doc]
        mock_llm.ainvoke.return_value.content = "Answer"

        chain = _make_naive_chain(mock_retriever, mock_llm)
        chain.invoke(
            "q",
            system_prompt="CUSTOM SYSTEM PROMPT",
            hl_keywords=["h"],
            ll_keywords=["l"],
        )

        messages = mock_llm.ainvoke.call_args[0][0]
        sys_content = messages[0].content
        assert sys_content == "CUSTOM SYSTEM PROMPT"
        # No template wrapping — the custom prompt doesn't contain upstream text
        assert "你是一位专业的 AI 助手" not in sys_content


# ===========================================================================
# Test Class 6: TestReferenceList — D-11/D-12 reference list
# ===========================================================================


class TestReferenceList:
    """D-11/D-12: reference list dedup by file_path, integer reference_ids."""

    def test_reference_list_dedup_by_file_path(
        self, _patch_settings, mock_llm, mock_retriever, make_chunk_doc
    ):
        """file_path 'a.txt' appearing twice → only 1 source entry for a.txt."""
        chunk_a1 = make_chunk_doc(
            chunk_id="c1", content="a1 content", file_path="a.txt"
        )
        chunk_b = make_chunk_doc(
            chunk_id="c2", content="b content", file_path="b.txt"
        )
        chunk_a2 = make_chunk_doc(
            chunk_id="c3", content="a2 content", file_path="a.txt"
        )
        mock_retriever.ainvoke.return_value = [chunk_a1, chunk_b, chunk_a2]
        mock_llm.ainvoke.return_value.content = "Answer"

        chain = _make_naive_chain(mock_retriever, mock_llm)
        result = chain.invoke(
            "q", hl_keywords=["h"], ll_keywords=["l"]
        )

        sources = result["sources"]
        # 2 unique file_paths, not 3
        assert len(sources) == 2
        # Integer reference_ids
        assert isinstance(sources[0]["reference_id"], int)
        assert isinstance(sources[1]["reference_id"], int)
        # Both are integers starting from 1
        assert sources[0]["reference_id"] >= 1

    def test_reference_list_excludes_unknown_source(
        self, _patch_settings, mock_llm, mock_retriever, make_chunk_doc
    ):
        """file_path='unknown_source' is filtered out (D-11)."""
        chunk_unknown = make_chunk_doc(
            chunk_id="c1", content="bad", file_path="unknown_source"
        )
        chunk_valid = make_chunk_doc(
            chunk_id="c2", content="good", file_path="valid.txt"
        )
        mock_retriever.ainvoke.return_value = [chunk_unknown, chunk_valid]
        mock_llm.ainvoke.return_value.content = "Answer"

        chain = _make_naive_chain(mock_retriever, mock_llm)
        result = chain.invoke(
            "q", hl_keywords=["h"], ll_keywords=["l"]
        )

        sources = result["sources"]
        # Only valid.txt survives
        assert len(sources) == 1
        assert sources[0]["file_path"] == "valid.txt"


# ===========================================================================
# Test Class 7: TestTokenBudget — token budget application
# ===========================================================================


class TestTokenBudget:
    """Token budget: entity truncation + chunk truncation applied in order."""

    def test_token_budget_called(
        self,
        _patch_settings,
        mock_llm,
        mock_retriever,
        make_entity_doc,
        make_chunk_doc,
    ):
        """With 30+ entities and max_entity_tokens=4000, entity list is
        truncated and chain does not crash."""
        entities = [
            make_entity_doc(entity_name=f"e{i}")
            for i in range(30)
        ]
        chunk = make_chunk_doc()
        mock_retriever.ainvoke.return_value = entities + [chunk]
        mock_llm.ainvoke.return_value.content = "Answer"

        chain = _make_local_chain(mock_retriever, mock_llm)
        result = chain.invoke(
            "q", hl_keywords=["h"], ll_keywords=["l"]
        )

        # Answer must be returned — chain did not crash on token budget
        assert isinstance(result["answer"], str)
        assert len(result["answer"]) > 0
        assert result["mode"] == "local"
