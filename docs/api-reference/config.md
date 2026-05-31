# 配置 (Configuration)

类型化配置系统，基于 Pydantic `BaseSettings` 和 `.env` 文件。提供五个子模型分别管理 PostgreSQL、LLM、Embedding、Reranker 和查询参数的配置，以及一个模块级延迟单例 `settings`。所有配置验证在首次访问时以快速失败方式执行，错误信息按分组归类展示。

## 顶层配置

::: lightrag_langchain.config.Settings

`settings` 为模块级延迟单例，通过 `from lightrag_langchain.config import settings` 访问。

## 配置子模型

::: lightrag_langchain.config.PgConfig

::: lightrag_langchain.config.LlmConfig

::: lightrag_langchain.config.EmbeddingConfig

::: lightrag_langchain.config.RerankerConfig

::: lightrag_langchain.config.QueryParamsConfig

## 异常

::: lightrag_langchain.config.SettingsError
