# Retriever 接口 (Retrievers)

检索器负责从 LightRAG 知识图谱中获取相关文档。每个检索器封装一种查询模式的检索策略，通过向量相似度搜索和/或图遍历获取实体、关系和文本块，返回 LangChain `Document` 对象。

## 基类

::: lightrag_langchain.retriever.base.LightRAGBaseRetriever

## 查询模式 Retriever 子类

::: lightrag_langchain.retriever.retrievers.NaiveRetriever

::: lightrag_langchain.retriever.retrievers.LocalRetriever

::: lightrag_langchain.retriever.retrievers.GlobalRetriever

::: lightrag_langchain.retriever.retrievers.HybridRetriever

::: lightrag_langchain.retriever.retrievers.MixRetriever

::: lightrag_langchain.retriever.retrievers.BypassRetriever
