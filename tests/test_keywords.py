"""Unit tests for KeywordsSchema and extract_keywords().

Tests cover:
- KeywordsSchema frozen + validation behaviour (Tests 1-2)
- Prompt template embedding and formatting (Tests 3-4)
- extract_keywords() structured output flow with mock LLM (Tests 5-6)

Per LLM-04 requirements.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

# fmt: off
from lightrag_langchain.keywords import (  # noqa: E402  -- module does not exist yet
    KEYWORDS_EXTRACTION_EXAMPLES,
    KEYWORDS_EXTRACTION_PROMPT,
    KeywordsSchema,
    extract_keywords,
)
# fmt: on


# ---------------------------------------------------------------------------
# Test 1 — KeywordsSchema is frozen (immutable after construction)
# ---------------------------------------------------------------------------


def test_keywords_schema_is_frozen() -> None:
    """Given a KeywordsSchema instance, mutation must raise."""
    schema = KeywordsSchema(
        high_level_keywords=["topic"],
        low_level_keywords=["entity"],
    )

    # The plan acknowledges both pydantic.ValidationError and TypeError
    # depending on the exact Pydantic version.
    with pytest.raises((ValidationError, TypeError)):
        schema.high_level_keywords = ["mutated"]  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Test 2 — KeywordsSchema type validation
# ---------------------------------------------------------------------------


def test_keywords_schema_validation() -> None:
    """Valid inputs must succeed; type mismatches must raise."""
    # Empty low_level_keywords is valid.
    schema = KeywordsSchema(
        high_level_keywords=["a"],
        low_level_keywords=[],
    )
    assert schema.high_level_keywords == ["a"]
    assert schema.low_level_keywords == []

    # Passing a non-list for high_level_keywords must raise ValidationError.
    with pytest.raises(ValidationError):
        KeywordsSchema(
            high_level_keywords="not_a_list",  # type: ignore[arg-type]
            low_level_keywords=[],
        )


# ---------------------------------------------------------------------------
# Test 3 — Prompt template contains required placeholder tokens
# ---------------------------------------------------------------------------


def test_prompt_template_contains_placeholders() -> None:
    """The embedded KEYWORDS_EXTRACTION_PROMPT must carry {query}, {examples},
    and {language} format placeholders."""
    assert "{query}" in KEYWORDS_EXTRACTION_PROMPT
    assert "{examples}" in KEYWORDS_EXTRACTION_PROMPT
    assert "{language}" in KEYWORDS_EXTRACTION_PROMPT


# ---------------------------------------------------------------------------
# Test 4 — Prompt formatting works with all three placeholders
# ---------------------------------------------------------------------------


def test_prompt_formatting() -> None:
    """Formatting with real values must not raise KeyError."""
    examples = "\n".join(KEYWORDS_EXTRACTION_EXAMPLES)
    formatted = KEYWORDS_EXTRACTION_PROMPT.format(
        query="test query",
        examples=examples,
        language="Chinese",
    )
    assert "test query" in formatted
    assert "ex1" not in formatted  # examples are the real upstream strings
    assert "Chinese" in formatted
    # Verify the example content is present in the formatted output.
    assert "东莞市" in formatted


# ---------------------------------------------------------------------------
# Test 5 — extract_keywords calls with_structured_output and returns schema
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_keywords_calls_structured_output() -> None:
    """extract_keywords() must delegate to llm.with_structured_output() with
    method="function_calling" and return a KeywordsSchema."""
    expected = KeywordsSchema(
        high_level_keywords=["防汛"],
        low_level_keywords=["东莞市"],
    )

    # Build a mock ChatOpenAI whose with_structured_output → ainvoke returns
    # the expected KeywordsSchema instance.
    structured_mock = MagicMock()
    structured_mock.ainvoke = AsyncMock(return_value=expected)

    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = structured_mock

    result = await extract_keywords(
        query="test",
        llm=mock_llm,
        language="Chinese",
    )

    # Verify the returned schema matches expected values.
    assert isinstance(result, KeywordsSchema)
    assert result.high_level_keywords == ["防汛"]
    assert result.low_level_keywords == ["东莞市"]

    # Verify with_structured_output was called once with the right args.
    mock_llm.with_structured_output.assert_called_once_with(
        KeywordsSchema,
        method="function_calling",
    )

    # Verify ainvoke was called on the structured LLM.
    structured_mock.ainvoke.assert_awaited_once()


# ---------------------------------------------------------------------------
# Test 6 — extract_keywords defaults language to "Chinese"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_keywords_default_language() -> None:
    """When language is not supplied, extract_keywords must default to
    "Chinese" per D-13."""
    expected = KeywordsSchema(
        high_level_keywords=["test_hl"],
        low_level_keywords=["test_ll"],
    )

    structured_mock = MagicMock()
    structured_mock.ainvoke = AsyncMock(return_value=expected)

    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = structured_mock

    result = await extract_keywords(query="test query", llm=mock_llm)

    assert result.high_level_keywords == ["test_hl"]
    assert result.low_level_keywords == ["test_ll"]

    # Verify the default language "Chinese" was passed into the prompt.
    prompt_arg = structured_mock.ainvoke.call_args[0][0]
    assert "Chinese" in prompt_arg
