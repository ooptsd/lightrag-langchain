# Phase 1: Configuration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-29
**Phase:** 1-Configuration
**Areas discussed:** 配置库选型与项目结构, 配置验证策略, 配置分组与 API 设计

---

## 配置库选型与项目结构

| Option | Description | Selected |
|--------|-------------|----------|
| pydantic-settings | Pydantic 官方配置管理库，Langchain 生态事实标准。支持 .env 自动加载、类型校验、嵌套 model、SecretStr | ✓ |
| python-dotenv + dataclasses | 轻量方案：dotenv 加载 + dataclass 封装，缺少内置校验和 SecretStr | |
| pydantic BaseSettings (v2) | Pydantic v2 自带，功能相近但版本耦合 | |

| Option | Description | Selected |
|--------|-------------|----------|
| src-layout + hatchling | src/lightrag_langchain/ 布局，hatchling 零配置构建，Python 社区现代标准 | ✓ |
| flat-layout + setuptools | lightrag_langchain/ 直接在根目录，传统布局 | |
| src-layout + poetry | src/ 布局 + Poetry，功能全但对库项目偏重 | |

| Option | Description | Selected |
|--------|-------------|----------|
| .env.example + .env gitignore | .env.example 含示例值提交仓库，.env 加入 .gitignore | ✓ |
| 仅 .env，不提交示例 | 本地维护 .env 无模板，新开发者需额外文档 | |
| 多环境 .env 文件 | .env.dev / .env.prod / .env.test，对纯库项目偏重 | |

| Option | Description | Selected |
|--------|-------------|----------|
| pytest + ruff | pytest 测试框架 + ruff 代码检查/格式化，轻量现代 | ✓ |
| pytest + flake8 + black | 传统组合，成熟稳定但多工具配合 | |
| pytest + mypy + ruff | 最严格，加入静态类型检查 | |

**User's choice:** 全部选 Recommended 选项
**Notes:** 用户偏好 Langchain 生态一致性和 Python 社区现代标准

---

## 配置验证策略

| Option | Description | Selected |
|--------|-------------|----------|
| fail-fast 启动时全量校验 | import 时立即校验所有字段，错误早发现 | ✓ |
| 懒加载按需校验 | 各组首次访问时才校验，启动快但错误延迟 | |
| 混合策略 | 结构校验启动时 + 连接校验按需，最灵活但最复杂 | |

| Option | Description | Selected |
|--------|-------------|----------|
| 明确区分必填/可选 | PG连接/API Key 必填；QueryParams 有默认值；Embedding 维度默认 1024 | ✓ |
| 全部必填，无默认值 | 每个字段必须显式设置，最严格 | |
| 全部可选，有 fallback | 全部有默认值，最宽松但可能隐藏错误 | |

| Option | Description | Selected |
|--------|-------------|----------|
| 分类汇总式错误 | 一次性收集所有校验失败，按配置组分组汇总 | ✓ |
| 具体指引式错误 | 每条错误详细说明 key 用途和修复方法 | |
| 简洁技术错误 | 仅报告字段名和校验原因 | |

| Option | Description | Selected |
|--------|-------------|----------|
| 关键约束 + 宽松 | 仅校验 token budget 等关键约束，不强制 provider 间一致性 | ✓ |
| 严格全量跨字段校验 | 检查所有可预见的字段间约束 | |
| 不做跨字段校验 | 每个字段独立验证 | |

**User's choice:** fail-fast + 必填/可选区分 + 分类汇总错误 + 关键约束
**Notes:** 用户偏好尽早暴露配置问题，错误信息清晰但不冗长

---

## 配置分组与 API 设计

| Option | Description | Selected |
|--------|-------------|----------|
| 嵌套子模型 | 顶层 Settings 含 5 个 BaseModel 子模型，分层清晰，可独立测试 | ✓ |
| 扁平单类 | 所有字段在一个 Settings 类中，简单但无法独立测试单组 | |
| 独立 Settings 类 + 组合 | 5 个独立 Settings 类，最模块化但 .env 命名复杂 | |

| Option | Description | Selected |
|--------|-------------|----------|
| 单文件 config.py | Phase 1 约 100-150 行，后续膨胀再拆分 | ✓ |
| config/ 子包拆分 | 每组一个文件，模块化强但 Phase 1 过度 | |
| config.py + config_types.py | 分离类型定义和实例化 | |

| Option | Description | Selected |
|--------|-------------|----------|
| 模块级单例 | `from lightrag_langchain.config import settings`，简单直接 | ✓ |
| 工厂函数 | get_settings() 支持 lazy loading 和缓存 | |
| 依赖注入 | 构造函数传入，最可测试但每个组件需传递 | |

| Option | Description | Selected |
|--------|-------------|----------|
| frozen 不可变 | Pydantic frozen=True，运行时不可修改 | ✓ |
| 可变但约定不修改 | 技术上可变，依赖开发者纪律 | |
| 允许修改并提供 reset() | 可修改，reset() 恢复 .env 值 | |

**User's choice:** 嵌套子模型 + 单文件 + 模块单例 + frozen
**Notes:** 用户偏好简洁 API 和强不可变性约束

---

## Claude's Discretion

- 敏感信息处理：API Key / Password 使用 SecretStr 自动脱敏
- 日志安全：`__repr__` / `__str__` 不暴露 SecretStr 值
- 错误消息中不包含连接信息（PG_HOST 等不出现在 error message 中）

## Deferred Ideas

None — 讨论保持在 phase scope 内
