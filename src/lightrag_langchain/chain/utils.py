"""LightRAG QA Chain 共享的 Document 转字典工具函数。

纯函数（无 I/O、无异步、无副作用），将 LangChain ``Document`` 实例
转换回结构化字典，用于 token 预算截断和上游 prompt 模板组装。

与 :file:`retriever/utils.py` 方向相反 — Document -> dict 而非
record -> Document。

Usage::

    from lightrag_langchain.chain.utils import classify_and_convert

    docs = await retriever.ainvoke(query)
    entities, relations, chunks = classify_and_convert(docs)

Notes:
    * 所有函数使用 ``.get(key, default)`` 进行安全的键访问。
    * ``json.JSONDecodeError`` 会向上传播给调用方 — chain 层不做
      格式异常的 page_content 的错误恢复。
    * ``classify_and_convert`` 通过 ``doc.metadata["document_type"]`` 分发，
      并跳过 ``graph_triple`` 类型的 Document（其数据已通过 entity/relation
      Document 捕获）。
"""

from __future__ import annotations

import json
import logging

from langchain_core.documents import Document

logger = logging.getLogger(__name__)


def doc_to_entity_dict(doc: Document) -> dict:
    """将 entity Document 的 JSON page_content 解析为结构化字典。

    Parameters
    ----------
    doc:
        metadata 中 ``document_type='entity'`` 的 Document。
        ``page_content`` 是与 :func:`retriever.utils.entity_to_document`
        键匹配的 JSON 对象。

    Returns
    -------
    dict
        包含键：``entity_name``、``entity_type``、``description``、
        ``source_id``、``file_path`` 的字典。当 JSON 键缺失时，
        所有值默认为 ``""``。
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
    """将 relation Document 的 JSON page_content 解析为结构化字典。

    Parameters
    ----------
    doc:
        metadata 中 ``document_type='relation'`` 的 Document。
        ``page_content`` 是与 :func:`retriever.utils.relation_to_document`
        键匹配的 JSON 对象。

    Returns
    -------
    dict
        包含键：``src_id``、``tgt_id``、``description``、``keywords``、
        ``weight``、``source_id``、``file_path`` 的字典。
        ``weight`` 默认为 ``0.0``，所有字符串默认为 ``""``。
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
    """将 chunk Document 的 JSON page_content 解析为结构化字典。

    Parameters
    ----------
    doc:
        metadata 中 ``document_type='chunk'`` 的 Document。
        ``page_content`` 是与 :func:`retriever.utils.chunk_to_document`
        键匹配的 JSON 对象。

    Returns
    -------
    dict
        包含键：``content``、``file_path``、``chunk_id``、
        ``reference_id`` 的字典。当 JSON 键缺失时，所有值默认为 ``""``。
        ``reference_id`` 初始为 ``""`` — Plan 06-02 的引用列表生成
        会在后续填充。
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
    """按 ``metadata['document_type']`` 分类 Document 并逐一转换。

    遍历所有 Document 并分发：
        * ``"entity"`` -> :func:`doc_to_entity_dict`
        * ``"relation"`` -> :func:`doc_to_relation_dict`
        * ``"chunk"`` -> :func:`doc_to_chunk_dict`
        * ``"graph_triple"`` -> 跳过（无需转换；其 entity/relation
          数据已通过 entity/relation Document 捕获，且其
          ``file_path`` 始终为 ``""``）
        * 未知类型 -> 静默跳过

    Parameters
    ----------
    docs:
        来自 Phase 5 retriever 的 ``ainvoke()`` 返回的 LangChain Document 列表。

    Returns
    -------
    tuple[list[dict], list[dict], list[dict]]
        一个 ``(entities, relations, chunks)`` 的解析后字典列表元组。
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
