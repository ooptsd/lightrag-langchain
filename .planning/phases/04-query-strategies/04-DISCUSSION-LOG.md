# Phase 4: Query Strategies - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-30
**Phase:** 04-query-strategies
**Areas discussed:** 结果格式与接口契约

---

## 结果格式与接口契约

### 6 种查询模式的返回结果应该是什么抽象层次？

| Option | Description | Selected |
|--------|-------------|----------|
| 结构化中间表示 | 返回强类型 QueryResult 对象，Phase 4 只管检索逻辑，Phase 5/6 负责后续转换 | ✓ |
| 直接返回 LangChain Document | 6 种模式直接返回 List[Document]，减少中间层但耦合 Phase 5 职责 | |
| 返回 context 字符串 | 返回格式化好的 context string，简单但丧失 LangChain 可组合性 | |

**User's choice:** 结构化中间表示
**Notes:** 保持 Phase 4 职责单一——产出检索结果，不做格式化或包装。

### 6 种模式的返回类型应该如何设计？

| Option | Description | Selected |
|--------|-------------|----------|
| 每种模式独立类型 | NaiveResult / LocalResult / ... — 精确反映结构差异，IDE 类型安全 | |
| 单一联合类型 | 一个 QueryResult 包含所有可能的字段，各模式填充相关字段 | ✓ |
| 基类 + 子类 | QueryResultBase + 各模式子类，兼顾统一接口和类型精确 | |

**User's choice:** 单一联合类型
**Notes:** 简单直接，避免过度抽象。不为类型安全增加复杂度。

### 查询策略如何获取查询向量？

| Option | Description | Selected |
|--------|-------------|----------|
| 接收预计算向量 | 策略方法接收 query_embedding: list[float]，不依赖 embedding 服务 | ✓ |
| 内部自动生成 embedding | 策略接收 query: str，内部调用 create_embedding() | |
| 两者都支持 | embedding 参数可选 | |

**User's choice:** 接收预计算向量
**Notes:** 延续 Phase 2 D-10 设计（PGVectorStore 接收预计算向量），策略层保持纯检索逻辑。

### 图遍历结果在 QueryResult 中如何表达？

| Option | Description | Selected |
|--------|-------------|----------|
| 三元组扁平化 | (entity, relation, entity) 三元组列表，匹配上游 LightRAG 上下文组装 | ✓ |
| 节点+边分开存储 | nodes dict + edges dict + adjacencies list，保留原始图结构 | |
| 只存序列化文本 | 图结果直接序列化为文本字符串，简单但丢失结构化信息 | |

**User's choice:** 三元组扁平化
**Notes:** 匹配上游 LightRAG 的上下文组装方式，方便 Phase 6 直接序列化给 LLM。

---

## Not Discussed

以下领域在 discuss 阶段提出但用户选择不深入讨论，由 Claude 在 CONTEXT.md 中记录处置建议：

- **模块与API设计**: 委托给 Planner，遵循 Phase 2/3 模式
- **Reranker 定位**: 不在 Phase 4 范围（属于 Phase 5/6）
- **Naive 模式子策略 (WEIGHT)**: 委托给 Researcher 确认上游行为

## Claude's Discretion

- 模块组织: 遵循渐进拆分模式，6 种策略集中在一个 query 模块中
- Reranker: 确认不在 Phase 4，由 Phase 5/6 在结果消费侧应用
- Bypass 模式: 返回空 QueryResult，不做数据库查询

## Deferred Ideas

None — 讨论保持在 phase scope 内
