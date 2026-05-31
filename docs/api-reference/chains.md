# Chain 接口 (Chains)

完整的端到端问答管道，封装关键词提取、检索、Token 预算控制、上下文组装和 LLM 调用。包含 `LightRAGBaseChain` 基类和六种查询模式子类（NaiveChain / LocalChain / GlobalChain / HybridChain / MixChain / BypassChain）。
