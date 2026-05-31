# Retriever 接口 (Retrievers)

符合 Langchain `BaseRetriever` 接口的检索器类，每种查询模式对应一个独立的 Retriever 子类，支持同步和异步调用，返回包含 JSON 元数据的 `Document` 对象。
