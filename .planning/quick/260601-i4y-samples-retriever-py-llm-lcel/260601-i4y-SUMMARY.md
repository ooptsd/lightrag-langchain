---
quick_id: 260601-i4y
slug: samples-retriever-py-llm-lcel
status: complete
date: 2026-06-01
commit: 4de91a1
---

# Quick Task 260601-i4y: 在samples中增加*_retriever.py

## Goal

为六种检索模式增加 retriever-only 示例文件，只检索不生成 LLM 结果，供在 LCEL 中调用。

## Deliverables

| File | Retriever | Stores | Description |
|------|-----------|--------|-------------|
| `examples/naive_retriever.py` | NaiveRetriever | vector_store | 纯向量 chunk 搜索 |
| `examples/local_retriever.py` | LocalRetriever | vector_store + graph_store | 实体搜索 + 图扩展 |
| `examples/global_retriever.py` | GlobalRetriever | vector_store + graph_store | 关系搜索 + 实体查找 |
| `examples/hybrid_retriever.py` | HybridRetriever | vector_store + graph_store | 并行 local + global |
| `examples/mix_retriever.py` | MixRetriever | vector_store + graph_store | hybrid + chunk 搜索 |
| `examples/bypass_retriever.py` | BypassRetriever | vector_store | 空检索 (always []) |

## Verification

All grep gates PASS:
- Zero LLM/chain imports across all 6 files
- `retriever.ainvoke()` in all 6 files
- `asyncio.run(main())` in all 6 files
- `PGGraphStore()` absent from naive (0) and bypass (0), present in local/global/hybrid/mix (1 each)
- `page_content` and `metadata` printed in all files

## Notes

- No chain/LLM imports — each file stops after retriever invocation
- Pattern matches existing `*_query.py` examples (async main, init_pool, PGVectorStore)
- BypassRetriever returns `[]` without I/O but still calls init_pool/PGVectorStore for consistent setup pattern
