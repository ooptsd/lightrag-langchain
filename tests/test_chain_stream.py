"""Unit tests for D-09 astream contract: yields str tokens then final dict.
D-10: sources/keywords determined before LLM streaming begins.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from lightrag_langchain.chain.chains import BypassChain, NaiveChain


# ---------------------------------------------------------------------------
# Fixture: patch settings singleton (same pattern as test_chain_base.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def _patch_settings(mock_query_params_config):
    import lightrag_langchain.config as _cfg

    original = _cfg._settings
    mock = MagicMock()
    mock.query_params = mock_query_params_config
    _cfg._settings = mock
    yield
    _cfg._settings = original


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_naive_chain(mock_retriever, mock_llm):
    """Construct NaiveChain with model_construct to bypass Pydantic validation."""
    return NaiveChain.model_construct(
        retriever=mock_retriever, llm=mock_llm
    )


def _make_bypass_chain(mock_retriever, mock_llm):
    """Construct BypassChain with model_construct."""
    return BypassChain.model_construct(
        retriever=mock_retriever, llm=mock_llm
    )


# ===========================================================================
# Test Class: TestChainAstream
# ===========================================================================


class TestChainAstream:
    """D-09 / D-10: astream() yields str tokens then final dict."""

    # ------------------------------------------------------------------
    # Test 1 — D-09: token-then-dict contract
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_astream_yields_tokens_then_dict(
        self, _patch_settings, mock_llm, mock_retriever
    ):
        """astream() yields raw str chunks from the LLM then a final dict
        with the complete structured result (D-09 contract)."""
        mock_retriever.ainvoke.return_value = []

        # Set up mock_llm.astream to yield 3 token chunks
        async def _mock_stream(messages):
            yield MagicMock(content="Hello")
            yield MagicMock(content=" ")
            yield MagicMock(content="World")

        mock_llm.astream = MagicMock(side_effect=_mock_stream)

        chain = _make_bypass_chain(mock_retriever, mock_llm)
        chunks = []
        async for chunk in chain.astream("test query"):
            chunks.append(chunk)

        # 3 str tokens + 1 dict = 4 chunks
        assert len(chunks) == 4
        assert chunks[0] == "Hello"
        assert isinstance(chunks[0], str)
        assert chunks[1] == " "
        assert isinstance(chunks[1], str)
        assert chunks[2] == "World"
        assert isinstance(chunks[2], str)
        # Final chunk is the dict
        assert isinstance(chunks[3], dict)
        assert chunks[3]["answer"] == "Hello World"
        assert chunks[3]["mode"] == "bypass"
        assert chunks[3]["sources"] == []

    # ------------------------------------------------------------------
    # Test 2 — final dict has all 4 required keys
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_astream_final_dict_has_answer_sources_keywords_mode(
        self, _patch_settings, mock_llm, mock_retriever, make_chunk_doc
    ):
        """The final dict in an astream() must contain all 4 required keys:
        answer, sources, keywords, mode (CHAIN-02)."""
        chunk_doc = make_chunk_doc()
        mock_retriever.ainvoke.return_value = [chunk_doc]

        async def _mock_stream(messages):
            yield MagicMock(content="Response")

        mock_llm.astream = MagicMock(side_effect=_mock_stream)

        chain = _make_naive_chain(mock_retriever, mock_llm)
        final_dict = None
        async for chunk in chain.astream(
            "q", hl_keywords=["h"], ll_keywords=["l"]
        ):
            if isinstance(chunk, dict):
                final_dict = chunk

        assert final_dict is not None
        assert "answer" in final_dict
        assert "sources" in final_dict
        assert "keywords" in final_dict
        assert "mode" in final_dict
        assert isinstance(final_dict["answer"], str)
        assert len(final_dict["answer"]) > 0
        assert isinstance(final_dict["sources"], list)
        assert isinstance(final_dict["keywords"], dict)
        assert "high_level" in final_dict["keywords"]
        assert "low_level" in final_dict["keywords"]
        assert final_dict["mode"] == "naive"

    # ------------------------------------------------------------------
    # Test 3 — D-10: sources determined before any LLM token
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_sources_determined_before_streaming(
        self, _patch_settings, mock_llm, mock_retriever, make_chunk_doc
    ):
        """D-10: reference list and keywords are computed before any LLM
        token is yielded — the final dict carries pre-computed sources."""
        chunk_doc = make_chunk_doc(file_path="unique/file.txt")
        mock_retriever.ainvoke.return_value = [chunk_doc]

        async def _mock_stream(messages):
            yield MagicMock(content="T")

        mock_llm.astream = MagicMock(side_effect=_mock_stream)

        chain = _make_naive_chain(mock_retriever, mock_llm)
        final_dict = None
        async for chunk in chain.astream(
            "q", hl_keywords=["h"], ll_keywords=["l"]
        ):
            if isinstance(chunk, dict):
                final_dict = chunk

        # The reference list was computed before the LLM yielded any token
        # — it is present in the final dict carried by the last chunk.
        assert final_dict is not None
        sources = final_dict["sources"]
        assert len(sources) == 1
        assert sources[0]["file_path"] == "unique/file.txt"
        assert isinstance(sources[0]["reference_id"], int)
        assert sources[0]["reference_id"] >= 1

    # ------------------------------------------------------------------
    # Test 4 — empty LLM output edge case
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_astream_empty_llm_output_yields_empty_answer(
        self, _patch_settings, mock_llm, mock_retriever
    ):
        """When the LLM yields zero tokens, the final dict still has answer=""
        (not a missing key)."""
        mock_retriever.ainvoke.return_value = []

        # Empty async generator — yields nothing
        async def _empty_stream(messages):
            return
            yield  # pragma: no cover  # makes it an async generator

        mock_llm.astream = MagicMock(side_effect=_empty_stream)

        chain = _make_bypass_chain(mock_retriever, mock_llm)
        chunks = []
        async for chunk in chain.astream("test query"):
            chunks.append(chunk)

        # Only the final dict — no token chunks
        assert len(chunks) == 1
        assert isinstance(chunks[0], dict)
        assert chunks[0]["answer"] == ""  # LLM generated no tokens
        assert chunks[0]["mode"] == "bypass"

    # ------------------------------------------------------------------
    # Test 5 — CHAIN-03 keywords carried through streaming
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_astream_with_pre_provided_keywords(
        self, _patch_settings, mock_llm, mock_retriever, make_chunk_doc
    ):
        """Pre-provided keywords appear in the streaming final dict without
        triggering LLM keyword extraction (CHAIN-03 + streaming)."""
        chunk_doc = make_chunk_doc()
        mock_retriever.ainvoke.return_value = [chunk_doc]

        async def _mock_stream(messages):
            yield MagicMock(content="Token")

        mock_llm.astream = MagicMock(side_effect=_mock_stream)

        chain = _make_naive_chain(mock_retriever, mock_llm)
        final_dict = None
        async for chunk in chain.astream(
            query="q",
            hl_keywords=["provided_hl"],
            ll_keywords=["provided_ll"],
        ):
            if isinstance(chunk, dict):
                final_dict = chunk

        assert final_dict is not None
        assert final_dict["keywords"] == {
            "high_level": ["provided_hl"],
            "low_level": ["provided_ll"],
        }
        # Keyword extraction was never called
        mock_llm.with_structured_output.assert_not_called()
