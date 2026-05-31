# Reranker 接口 (Reranker)

`LightRAGReranker` 实现了 Langchain `BaseDocumentCompressor` 接口，支持三种后端（aliyun / cohere / jina），通过交叉编码器和排序增强检索结果的相关性。
