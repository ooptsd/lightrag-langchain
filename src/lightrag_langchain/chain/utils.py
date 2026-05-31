"""Shared Document-to-dict conversion utilities for LightRAG QA chains.

Pure functions (no I/O, no async, no side effects) that convert LangChain
``Document`` instances back into structured dicts for token budget truncation
and upstream prompt template assembly.

Reverse direction of :file:`retriever/utils.py` — Document -> dict instead
of record -> Document.

Usage::

    from lightrag_langchain.chain.utils import classify_and_convert

    docs = await retriever.ainvoke(query)
    entities, relations, chunks = classify_and_convert(docs)

Notes:
    * All functions use ``.get(key, default)`` for safe key access.
    * ``json.JSONDecodeError`` propagates to caller — chain layer does no
      error recovery on malformed page_content.
    * ``classify_and_convert`` dispatches by ``doc.metadata["document_type"]``
      and skips ``graph_triple`` Documents (their data is already captured
      through entity/relation Documents).
"""

from __future__ import annotations

import json
import logging

from langchain_core.documents import Document

logger = logging.getLogger(__name__)


def doc_to_entity_dict(doc: Document) -> dict:
    """Parse entity Document's JSON page_content into a structured dict.

    Parameters
    ----------
    doc:
        A Document with ``document_type='entity'`` in metadata.
        ``page_content`` is a JSON object with keys matching
        :func:`retriever.utils.entity_to_document`.

    Returns
    -------
    dict
        Dict with keys: ``entity_name``, ``entity_type``, ``description``,
        ``source_id``, ``file_path``.  All values default to ``""`` when
        the JSON key is missing.
    """
    obj = json.loads(doc.page_content)
    return {
        "entity_name": obj.get("entity_name", ""),
        "entity_type": obj.get("entity_type", ""),
        "description": obj.get("description", ""),
        "source_id": obj.get("source_id", ""),
        "file_path": obj.get("file_path", ""),
    }


def doc_to_relation_dict(doc: Document) -> dict:
    """Parse relation Document's JSON page_content into a structured dict.

    Parameters
    ----------
    doc:
        A Document with ``document_type='relation'`` in metadata.
        ``page_content`` is a JSON object with keys matching
        :func:`retriever.utils.relation_to_document`.

    Returns
    -------
    dict
        Dict with keys: ``src_id``, ``tgt_id``, ``description``,
        ``keywords``, ``weight``, ``source_id``, ``file_path``.
        ``weight`` defaults to ``0.0``, all strings default to ``""``.
    """
    obj = json.loads(doc.page_content)
    return {
        "src_id": obj.get("src_id", ""),
        "tgt_id": obj.get("tgt_id", ""),
        "description": obj.get("description", ""),
        "keywords": obj.get("keywords", ""),
        "weight": obj.get("weight", 0.0),
        "source_id": obj.get("source_id", ""),
        "file_path": obj.get("file_path", ""),
    }


def doc_to_chunk_dict(doc: Document) -> dict:
    """Parse chunk Document's JSON page_content into a structured dict.

    Parameters
    ----------
    doc:
        A Document with ``document_type='chunk'`` in metadata.
        ``page_content`` is a JSON object with keys matching
        :func:`retriever.utils.chunk_to_document`.

    Returns
    -------
    dict
        Dict with keys: ``content``, ``file_path``, ``chunk_id``,
        ``reference_id``.  All values default to ``""`` when the JSON key
        is missing.  The ``reference_id`` starts as ``""`` — Plan 06-02's
        reference list generation fills it in later.
    """
    obj = json.loads(doc.page_content)
    return {
        "content": obj.get("content", ""),
        "file_path": obj.get("file_path", ""),
        "chunk_id": obj.get("chunk_id", ""),
        "reference_id": obj.get("reference_id", ""),
    }


def classify_and_convert(
    docs: list[Document],
) -> tuple[list[dict], list[dict], list[dict]]:
    """Classify Documents by ``metadata['document_type']`` and convert each.

    Iterates all Documents and dispatches:
        * ``"entity"`` -> :func:`doc_to_entity_dict`
        * ``"relation"`` -> :func:`doc_to_relation_dict`
        * ``"chunk"`` -> :func:`doc_to_chunk_dict`
        * ``"graph_triple"`` -> skipped (no conversion; their entity/relation
          data is already captured through entity/relation Documents, and
          their ``file_path`` is always ``""``)
        * Unknown type -> skipped silently

    Parameters
    ----------
    docs:
        LangChain Documents from a Phase 5 retriever's ``ainvoke()``.

    Returns
    -------
    tuple[list[dict], list[dict], list[dict]]
        A ``(entities, relations, chunks)`` tuple of parsed dict lists.
    """
    entities: list[dict] = []
    relations: list[dict] = []
    chunks: list[dict] = []
    _unknown_warned: set[str] = set()

    for doc in docs:
        dtype = doc.metadata.get("document_type", "")
        if dtype == "entity":
            entities.append(doc_to_entity_dict(doc))
        elif dtype == "relation":
            relations.append(doc_to_relation_dict(doc))
        elif dtype == "chunk":
            chunks.append(doc_to_chunk_dict(doc))
        elif dtype == "graph_triple":
            pass  # data already in entity/relation dicts
        else:
            if dtype not in _unknown_warned:
                _unknown_warned.add(dtype)
                logger.warning(
                    "classify_and_convert: unrecognized document_type=%r, document skipped",
                    dtype or "<missing>",
                )

    return entities, relations, chunks
