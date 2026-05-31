# Token 预算控制 (Token Budget)

Token 预算控制系统，使用 tiktoken 进行精确的 BPE Token 计数。在 QA 管道中按固定顺序执行：实体截断 → 关系截断 → 序列化统计 → 构建预热系统提示词并计数 → 计算文本块剩余预算 → 按前缀截断文本块。异步包装函数（`atruncate_*` / `acompute_*`）仅用于管道兼容性，核心计算为纯同步函数。

::: lightrag_langchain.token_budget.truncate_entities_by_tokens

::: lightrag_langchain.token_budget.truncate_relations_by_tokens

::: lightrag_langchain.token_budget.compute_chunk_token_budget
