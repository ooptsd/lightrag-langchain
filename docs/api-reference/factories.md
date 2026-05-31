# 工厂函数 (Factory Functions)

工厂函数提供 LLM、Embedding 和 Reranker 实例的延迟创建。返回的对象为惰性代理，实际的 ChatOpenAI / OpenAIEmbeddings / Reranker 构造推迟到首次属性访问时进行，确保 `import lightrag_langchain` 无需 `.env` 文件或网络连接。

::: lightrag_langchain.llm.create_llm

::: lightrag_langchain.llm.create_embedding

::: lightrag_langchain.reranker.create_reranker
