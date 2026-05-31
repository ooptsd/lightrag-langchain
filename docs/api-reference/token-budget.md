# Token 预算控制 (Token Budget)

Token 预算控制函数（`truncate_entities_by_tokens()` / `truncate_relations_by_tokens()` / `compute_chunk_token_budget()`）使用 tiktoken 按 Token 数量截断实体和关系列表，确保上下文窗口不溢出。
