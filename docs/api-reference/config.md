# 配置 (Configuration)

配置系统基于 Pydantic Settings，包含 `Settings` 单例和五个子模型（`PgConfig` / `LlmConfig` / `EmbeddingConfig` / `GraphConfig` / `VectorConfig`），所有配置通过 `.env` 文件加载。
