# Reranker 接口 (Reranker)

多后端 Reranker 系统，支持 aliyun (DashScope)、cohere、jina 三种后端。`LightRAGReranker` 实现了 LangChain `BaseDocumentCompressor` 接口，可直接用于 `ContextualCompressionRetriever` 管道。`Reranker` 为 Protocol 定义，工厂函数 `create_reranker()` 根据配置自动分发到对应的后端适配器。

::: lightrag_langchain.reranker.LightRAGReranker

::: lightrag_langchain.reranker.Reranker
