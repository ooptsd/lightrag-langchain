# 示例 (Examples)

本目录包含 lightrag-langchain 的可运行示例脚本，演示全部查询模式。

## 前置条件

- Python >= 3.12
- PostgreSQL 数据库已由上游 LightRAG 完成知识图谱构建（含 `entities_vdb`、`relationships_vdb`、`chunks_vdb` 和 AGE 图数据）
- PostgreSQL 已安装 pgvector 和 Apache AGE 扩展

## 配置

1. 复制项目根目录的 `.env.example` 为 `.env` 并填入实际配置：

   ```bash
   cp ../.env.example ../.env
   # 编辑 ../.env，填入你的 PostgreSQL 和 LLM 凭证
   ```

2. 安装项目依赖：

   ```bash
   cd .. && uv sync
   ```

## 运行示例

### Python 脚本

每个脚本独立演示一种查询模式。从项目根目录运行：

```bash
uv run python examples/naive_query.py
```

或先 `cd examples` 再执行（脚本会自动将项目根目录加入 `sys.path`）：

```bash
cd examples && uv run python naive_query.py
```

### Jupyter Notebook

`walkthrough.ipynb` 演示所有六种查询模式。需要先安装 jupyter（不作为项目依赖）：

```bash
pip install jupyter
jupyter notebook examples/walkthrough.ipynb
```

## 查询模式说明

| 文件 | 模式 | 描述 |
|------|------|------|
| `naive_query.py` | Naive | 纯向量相似度搜索 `chunks_vdb`，无图遍历 |
| `local_query.py` | Local | 实体中心图扩展 — `entities_vdb` 搜索 + AGE 图邻居扩展 |
| `global_query.py` | Global | 关系中心图扩展 — `relationships_vdb` 搜索 + AGE 图实体查找 |
| `hybrid_query.py` | Hybrid | 并行 local + global，round-robin 交错合并 |
| `mix_query.py` | Mix | hybrid 检索 + chunks_vdb 向量搜索，融合图知识和原始文本块 |
| `bypass_query.py` | Bypass | 跳过所有检索，直接调用 LLM |
| `walkthrough.ipynb` | 全部 6 种 | 完整 Notebook，覆盖 Naive / Local / Global / Hybrid / Mix / Bypass |

> 全部 6 种查询模式均有独立 Python 脚本；`walkthrough.ipynb` 提供完整的交互式演示。

## 脚本结构

所有 Python 脚本遵循统一结构：

1. `sys.path.insert` — 将项目根目录加入路径，支持从 `examples/` 内直接运行
2. `async main()` — 五个步骤：(1) 创建数据连接、(2) 创建 LLM/Embedding、(3) 构建 Retriever、(4) 构建 Chain、(5) 执行查询并打印结果
3. `asyncio.run(main())` — 脚本入口

> **导入说明**：Chain 和 Retriever 使用懒加载形式 `from lightrag_langchain import NaiveChain`；数据层连接类（`PGVectorStore` / `PGGraphStore`）直接从 `lightrag_langchain.data.store` 和 `lightrag_langchain.data.graph` 导入。
