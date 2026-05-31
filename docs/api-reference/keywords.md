# 关键词提取 (Keyword Extraction)

基于 LLM 的关键词提取模块，使用上游 LightRAG 的提示词模板，通过 `with_structured_output(KeywordsSchema, method="function_calling")` 实现类型安全的结构化提取。输出包含高层关键词（概念/主题）和低层关键词（实体/细节），用于指导知识图谱检索策略。

::: lightrag_langchain.keywords.extract_keywords

::: lightrag_langchain.keywords.KeywordsSchema
