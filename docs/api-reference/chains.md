# Chain 接口 (Chains)

完整的端到端问答管道，封装了关键词提取、文档检索、Document 类型转换、Token 预算控制、引用列表生成、上下文组装和 LLM 调用，支持同步、异步和流式三种调用方式。

## 基类

::: lightrag_langchain.chain.base.LightRAGBaseChain
    options:
      members:
        - invoke
        - ainvoke
        - astream

## 查询模式 Chain 子类

每个子类只设置 `mode` 属性，继承全部管道逻辑。BypassChain 覆盖全部三个方法，跳过检索直接调用 LLM。

::: lightrag_langchain.chain.chains.NaiveChain

::: lightrag_langchain.chain.chains.LocalChain

::: lightrag_langchain.chain.chains.GlobalChain

::: lightrag_langchain.chain.chains.HybridChain

::: lightrag_langchain.chain.chains.MixChain

::: lightrag_langchain.chain.chains.BypassChain
