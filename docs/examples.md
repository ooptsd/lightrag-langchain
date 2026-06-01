# 示例 (Examples)

[`examples/`](https://github.com/<user>/lightrag-langchain/tree/main/examples) 目录包含独立可运行的 Python 脚本和 Jupyter Notebook，演示 lightrag-langchain 的全部查询模式。

示例分为两类：
- **Chain 示例 (`*_query.py`)**：完整管线 — 检索 + LLM 生成答案
- **Retriever 示例 (`*_retriever.py`)**：仅检索 — 返回 `list[Document]`，供在 LCEL 管线中独立调用

每个脚本都是自包含的（无需额外依赖），可直接复制到你的项目中使用。它们使用与 README 一致的懒加载导入模式，并附有中文注释解释每一步操作。

## 运行前准备

请参考 [`examples/README.md`](https://github.com/<user>/lightrag-langchain/tree/main/examples/README.md) 中的详细设置说明。简要步骤如下：

1. 确保 PostgreSQL 数据库已由 LightRAG 完成知识图谱构建
2. 复制 `.env.example` 为 `.env` 并填入你的实际配置
3. 安装依赖：`uv sync`
4. 运行任意脚本：`uv run python examples/naive_query.py`

## 可用示例

### Chain 示例（完整管线）

| 文件 | 模式 | 描述 |
|------|------|------|
| [`naive_query.py`](https://github.com/<user>/lightrag-langchain/blob/main/examples/naive_query.py) | Naive | 纯向量相似度搜索 `chunks_vdb`，不做图遍历。适用于简单的语义匹配查询。 |
| [`local_query.py`](https://github.com/<user>/lightrag-langchain/blob/main/examples/local_query.py) | Local | 实体中心图扩展——先对 `entities_vdb` 搜索 Top-K 实体，再通过 AGE 图扩展获取关联的边和邻居实体。 |
| [`global_query.py`](https://github.com/<user>/lightrag-langchain/blob/main/examples/global_query.py) | Global | 关系中心图扩展——先对 `relationships_vdb` 搜索 Top-K 关系，再通过 AGE 图查找关联实体。 |
| [`hybrid_query.py`](https://github.com/<user>/lightrag-langchain/blob/main/examples/hybrid_query.py) | Hybrid | 并行 Local + Global 检索，round-robin 交错合并结果。 |
| [`mix_query.py`](https://github.com/<user>/lightrag-langchain/blob/main/examples/mix_query.py) | Mix | Hybrid 检索 + chunks_vdb 向量搜索，融合图知识和原始文本块。 |
| [`bypass_query.py`](https://github.com/<user>/lightrag-langchain/blob/main/examples/bypass_query.py) | Bypass | 跳过所有检索，直接将用户问题发送给 LLM。 |

### Retriever 示例（仅检索，供 LCEL 调用）

| 文件 | 模式 | 描述 |
|------|------|------|
| [`naive_retriever.py`](https://github.com/<user>/lightrag-langchain/blob/main/examples/naive_retriever.py) | Naive | 纯向量 chunk 搜索，返回 `list[Document]`。无 chain/LLM。 |
| [`local_retriever.py`](https://github.com/<user>/lightrag-langchain/blob/main/examples/local_retriever.py) | Local | 实体搜索 + AGE 图扩展，返回 entity + GraphTriple Documents。 |
| [`global_retriever.py`](https://github.com/<user>/lightrag-langchain/blob/main/examples/global_retriever.py) | Global | 关系搜索 + 实体查找，返回 relation + GraphTriple Documents。 |
| [`hybrid_retriever.py`](https://github.com/<user>/lightrag-langchain/blob/main/examples/hybrid_retriever.py) | Hybrid | 并行 local + global，返回 entity + relation + GraphTriple Documents。 |
| [`mix_retriever.py`](https://github.com/<user>/lightrag-langchain/blob/main/examples/mix_retriever.py) | Mix | hybrid + chunk 搜索，返回四种类型 Documents。 |
| [`bypass_retriever.py`](https://github.com/<user>/lightrag-langchain/blob/main/examples/bypass_retriever.py) | Bypass | 空检索，始终返回 `[]`。 |

### Notebook

| 文件 | 描述 |
|------|------|
| [`walkthrough.ipynb`](https://github.com/<user>/lightrag-langchain/blob/main/examples/walkthrough.ipynb) | 完整 Jupyter Notebook 演示，覆盖所有六种 Chain 模式（Naive / Local / Global / Hybrid / Mix / Bypass）。 |

## 示例结构

### Chain 示例 (`*_query.py`)

每个 Python 脚本遵循以下统一结构：

1. **异步 `main()` 函数** — 分为五个步骤：
   - (1) 创建数据层连接（`PGVectorStore` / `PGGraphStore`）
   - (2) 创建 LLM / Embedding（通过 `create_llm` / `create_embedding` 工厂）
   - (3) 构建 Retriever（模式对应的 `*Retriever`）
   - (4) 构建 Chain（模式对应的 `*Chain`）
   - (5) 执行查询并打印结果（模式、关键词、来源数、回答）
2. **`if __name__ == "__main__"` 入口** — 使用 `asyncio.run(main())` 启动

### Retriever 示例 (`*_retriever.py`)

每个脚本仅包含检索步骤（无 Chain、无 LLM）：

1. **异步 `main()` 函数** — 分为三个步骤：
   - (1) 创建数据层连接（`PGVectorStore` / `PGGraphStore`）
   - (2) 构建 Retriever（模式对应的 `*Retriever`）
   - (3) 调用 `retriever.ainvoke(query)` → `list[Document]`，打印 `page_content` 和 `metadata`
2. **`if __name__ == "__main__"` 入口** — 使用 `asyncio.run(main())` 启动
3. **不导入 Chain、LLM、Reranker** — 仅依赖数据层和 Retriever

## 运行 Notebook

要运行 `walkthrough.ipynb`，需要安装 `jupyter`：

```bash
pip install jupyter
jupyter notebook examples/walkthrough.ipynb
```

Notebook 按顺序演示六种查询模式，每个模式包含说明性的 Markdown 介绍和可执行代码，可逐一运行查看结果。
