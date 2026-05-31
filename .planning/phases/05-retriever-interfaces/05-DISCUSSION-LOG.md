# Phase 5: Retriever Interfaces - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-31
**Phase:** 5-Retriever Interfaces
**Areas discussed:** 依赖注入模式, Document 内容格式, 类层次与代码共享, 模块文件组织

---

## 依赖注入模式

| Option | Description | Selected |
|--------|-------------|----------|
| 构造函数注入 | 每个 Retriever 构造函数接收共享的 vector_store、graph_store、embedding 函数 | ✓ |
| 共享 Context 对象 | 定义 RetrieverContext 持有所有共享依赖 | |
| 自动线接 (.env) | Retriever 从 Settings 单例自举创建依赖 | |

**User's choice:** 构造函数注入 (Recommended)
**Notes:** 匹配 Phase 2 D-07 的 DI pool 模式，最直接、最可测试。

### Embedding 注入形式

| Option | Description | Selected |
|--------|-------------|----------|
| 可调用对象 | 接收 Callable[[str], List[float]] | |
| OpenAIEmbeddings 实例 | 直接接收 LangChain 实例 | |
| 字符串模板 + 内部创建 | 接收 embedding config，内部调用 create_embedding() | ✓ |

**User's choice:** 接收 config + 内部调用 create_embedding()
**Notes:** 类似 Phase 2 pool.py 的延迟初始化模式。Retriever import 不触发网络连接。

### top_k 放置位置

| Option | Description | Selected |
|--------|-------------|----------|
| Retriever 构造时 | 作为 Retriever 的构造参数（Pydantic 字段） | ✓ |
| invoke/ainvoke 时 | 作为 invoke 的额外关键字参数 | |

**User's choice:** Retriever 构造时 (Recommended)
**Notes:** 匹配 LangChain BaseRetriever 惯例，实例自身持有搜索参数。

---

## Document 内容格式

### page_content 序列化格式

| Option | Description | Selected |
|--------|-------------|----------|
| 结构化 key: value 格式 | newline-joined key:value pairs | |
| 简洁连续文本 | 自然语言描述 | |
| 仅保留 content/description | 只放原始文本字段 | |
| **JSON 对象序列化 (用户指定)** | 每条记录 `json.dumps()` 一行，匹配上游 LightRAG | ✓ |

**User's choice:** JSON 对象序列化 — page_content 用上游 LightRAG 兼容的 JSON 格式
**Notes:** 字段与上游 `convert_to_user_format()` 输出一致。Entity: entity_name/entity_type/description/source_id/file_path。Relationship: src_id/tgt_id/description/keywords/weight/source_id/file_path。Chunk: reference_id/content/file_path/chunk_id。

### metadata 内容

| Option | Description | Selected |
|--------|-------------|----------|
| 类型特定 + 公共字段 | 公共字段 + 按类型填充不同字段 | ✓ |
| 统一最小字段集 | 仅 source_id, file_path, retrieval_mode | |
| 最大信息保留 | metadata 放全部字段 | |

**User's choice:** 类型特定 + 公共字段 (Recommended)
**Notes:** GraphTriple 的三元组结构化格式（src_entity, relation, tgt_entity）完整保留在 metadata 中。

---

## 类层次与代码共享

| Option | Description | Selected |
|--------|-------------|----------|
| 共享基类 | LightRAGBaseRetriever 封装 embedding 生成、async 桥接、错误处理 | ✓ |
| 独立实现 + 共享工具函数 | 6 个直接继承 BaseRetriever，共享函数放 utils.py | |
| 统一 Retriever + mode 参数 | 单个类通过 mode 参数切换 | |

**User's choice:** 共享基类 (Recommended)
**Notes:** 子类只实现策略调用 + QueryResult→Document 转换。

---

## 模块文件组织

| Option | Description | Selected |
|--------|-------------|----------|
| retriever/ 包，2-3 文件 | base.py + retrievers.py (+ utils.py) | ✓ |
| 单个 retriever.py | 所有 7 个类在一个文件 | |
| retriever/ 包，per-mode 文件 | 每 mode 一个独立文件 | |

**User's choice:** retriever/ 包，2-3 文件 (Recommended)
**Notes:** 匹配 Phase 4 query/results.py + query/strategies.py 的两文件模式。

---

## Claude's Discretion

- 基类 vs 子类职责切分：embedding 生成、async 桥接、错误处理 → 基类；策略调用 + 转换 → 子类
- Document 转换 helper：公共 JSON 序列化函数提取到 utils.py；各子类的模式特定装配内联实现
- BypassRetriever：无依赖，直接返回空 List[Document]
- sync 桥接：asyncio.run，匹配 LightRAGReranker 模式
- Pydantic 字段：arbitrary_types_allowed=True 支持 vector_store/graph_store 类型

## Deferred Ideas

None — 讨论保持在 phase scope 内
