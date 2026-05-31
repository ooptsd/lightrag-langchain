# lightrag-langchain

基于 LangChain 框架的 LightRAG 知识图谱查询层。直接读取 LightRAG 已处理好的 PostgreSQL 知识图谱数据库（pgvector + Apache AGE），提供标准 LangChain `Retriever` + `Chain` 接口。脱离 LightRAG 运行时独立运行，只做查询不做数据写入。

## 核心价值

- **零依赖 LightRAG 运行时**：仅需 PostgreSQL 数据库连接即可工作，无需启动 LightRAG 服务
- **标准 LangChain API**：`BaseRetriever` + `BaseModel` Chain 接口，与 LangGraph / LangServe / LangSmith 完全兼容
- **六种查询模式**：完整复刻 LightRAG 的 naive / local / global / hybrid / mix / bypass 全部检索策略

## 快速导航

| 文档 | 说明 |
|------|------|
| [快速开始](quick-start.md) | 安装、配置 .env、第一个查询 |
| [API 参考](api-reference/index.md) | Chains、Retrievers、Factories、Reranker、Keywords、Token Budget、Configuration 完整参考 |
| [示例](examples.md) | 可运行的查询示例脚本和 Jupyter Notebook |

---

本文档使用 MkDocs + Material for MkDocs 构建。支持全文搜索（Ctrl+K）、明暗主题切换、代码复制等特性。
