# Phase 6: QA Chain - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-31
**Phase:** 6-QA Chain
**Areas discussed:** Chain架构设计, Prompt模板定制, 流式策略, 引用格式

---

## Chain API 设计

| Option | Description | Selected |
|--------|-------------|----------|
| dict 输入 dict 输出 | invoke({"query", "mode", ...}) → {"answer", "sources", ...} | |
| QueryParam 对象输入 | Pydantic 模型输入，类型安全 | |
| 6 个独立 Chain 类 | 每种模式一个 Chain 类，模式由类固化 | ✓ |

**User's choice:** 6 个独立 Chain 类
**Notes:** 每个 Chain 封装自己的 retriever，用户通过选择 Chain 类决定查询模式。模式更显式。

---

## Prompt 模板定制

| Option | Description | Selected |
|--------|-------------|----------|
| 复用上游模板 + 允许覆盖 | 默认上游模板，system_prompt 参数可选覆盖 | ✓ |
| 仅复用上游模板，不可覆盖 | 常量不可变 | |
| 自定义 prompt 模板 | 完全自定义 | |

**User's choice:** 复用上游模板 + 允许覆盖
**Notes:** 默认与上游 LightRAG 100% 一致。下游有特殊需求时可以完整替换系统提示。

---

## 流式策略

| Option | Description | Selected |
|--------|-------------|----------|
| token-by-token 文本 + 最后 dict | 先流式文本，最后 chunk 是完整 dict | ✓ |
| 完整 dict chunk 逐步输出 | 每个 chunk 是部分 dict | |
| 只流式文本 | 不返回结构化信息 | |

**User's choice:** token-by-token 文本 + 最后完整 dict
**Notes:** sources 在 LLM 调用前已确定，延迟到流式结束后返回。

---

## 引用格式

| Option | Description | Selected |
|--------|-------------|----------|
| 上游格式 [n] file_path | reference_id 自增 + file_path 映射 | ✓ |
| 简化格式 source_id 列表 | 只返回 source_id | |
| 复用上游 reference_list 生成逻辑 | 完全复制上游实现 | |

**User's choice:** 上游格式 [n] file_path
**Notes:** 使用自增数字 [1], [2]... 匹配上游行为。

---

## Chain 架构设计（子决策）

| Option | Description | Selected |
|--------|-------------|----------|
| 共享基类 LightRAGBaseChain | 基类封装所有共享逻辑，子类极薄 | ✓ |
| 独立实现 + 共享工具函数 | 各自内联逻辑 | |
| 独立 LCEL 管道 + 组合 | Runnable 组合 | |

**User's choice:** 共享基类 LightRAGBaseChain
**Notes:** 关键词提取、Document→dict 转换、token 截断、LLM 调用、流式管道全在基类。子类只提供 retriever + 选模板。

| Option | Description | Selected |
|--------|-------------|----------|
| query + 可选覆盖参数 | invoke(query, *, system_prompt, hl_keywords, ll_keywords) | ✓ |
| query 纯文本 | 所有配置在构造时设好 | |
| Pydantic QueryParam 输入 | 类型安全参数模型 | |

**User's choice:** query + 可选覆盖参数
**Notes:** 简洁灵活，关键词参数可选。

| Option | Description | Selected |
|--------|-------------|----------|
| 注入 Retriever 实例 | 外部创建好传入 | ✓ |
| 注入 Store + Config | 内部自行创建 | |
| 两种都支持 | fallback 模式 | |

**User's choice:** 注入 Retriever 实例
**Notes:** 匹配 Phase 5 DI 惯例，测试最方便。

| Option | Description | Selected |
|--------|-------------|----------|
| chain/ 包: base + chains | 两文件 + __init__ | ✓ |
| chain.py 单文件 | 全部在一个文件 | |

**User's choice:** chain/ 包: base + chains

---

## Prompt 模板定制（子决策）

| Option | Description | Selected |
|--------|-------------|----------|
| 整篇替换 | system_prompt 完整替换默认模板 | ✓ |
| 只覆盖 user_prompt | 只替换模板中的插值 | |
| 不可覆盖 | 硬编码 | |

**User's choice:** 整篇替换
**Notes:** 最大灵活性，调用者可完全控制 LLM 行为。

---

## 引用生成（子决策）

| Option | Description | Selected |
|--------|-------------|----------|
| 只 chunks 生成引用 | 只 chunks 参与引用 | |
| 所有来源类型都生成引用 | entities + relations + chunks | |
| 按 file_path 去重 | 有 file_path 的源头都纳入，去重 | ✓ |

**User's choice:** 按 file_path 去重
**Notes:** entities/relations 有 file_path 的纳入；没有的跳过。

| Option | Description | Selected |
|--------|-------------|----------|
| 自增数字 1,2,3... | 匹配上游行为 | ✓ |
| chunk_id 自增 | 全局唯一 ID | |

**User's choice:** 自增数字 1,2,3...

---

## 流式细节（子决策）

| Option | Description | Selected |
|--------|-------------|----------|
| 延迟到最后附完整结果 | 流式完最后一个 yield dict | ✓ |
| 第一个 chunk 给 metadata | 提前获得 sources/keywords | |

**User's choice:** 延迟到最后附完整结果

---

## Claude's Discretion

- Chain 输出 dict 结构: `{"answer": str, "sources": list[dict], "keywords": dict, "mode": str}`
- BypassChain: 跳过关键词提取和检索，直接 LLM；空 sources/keywords
- 空结果: 告知 LLM "无上下文"，不提前短路
- LLM 实例: 同一个 ChatOpenAI 用于关键词提取和最终生成
- Token 预算执行顺序: entities → relations → chunks
- Document→dict 转换: 纯函数，放 base.py 或 chain/utils.py
- 错误处理: 信任 Retriever/LLM 自身错误传播
- Pydantic 字段: BaseModel + arbitrary_types_allowed
- __init__.py lazy export: 添加到顶级 __getattr__
- Prompt 模板嵌入: 模块级常量，匹配 keywords.py 模式
- keyword_language: 从 settings.query_params 读取
- 对话历史: 本 phase 不支持 (v2 CHAIN-05)

## Deferred Ideas

- 对话历史管理 — v2 CHAIN-05
- LLM 响应缓存 — v2 CHAIN-04
