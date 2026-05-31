# Phase 7: Samples & Docs + README.md — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-31
**Phase:** 07-samples-docs-readme-md
**Areas discussed:** 文档工具链, API 文档深度, 示例代码形式, 文档发布位置

---

## 文档工具链

| Option | Description | Selected |
|--------|-------------|----------|
| MkDocs + Material for MkDocs | 简洁 Markdown 驱动，Material 主题，mkdocstrings 支持自动 API 文档 | ✓ |
| Sphinx + rST/Markdown | 经典方案，生态成熟，配置较重 | |
| 纯 Markdown in-repo | 零依赖，无导航/搜索 | |

**User's choice:** MkDocs + Material for MkDocs
**Notes:** 选择与 LangChain 生态系统一致。Material 主题是当前 Python 库文档的事实标准。

---

## API 文档深度

| Option | Description | Selected |
|--------|-------------|----------|
| Public API only | 只记录 `__init__.py` 导出的类/函数 | |
| Public API + core internal | 额外包含 base class 重要方法 | |
| 全部 public + 使用示例 | API 文档嵌入代码片段，每个类/函数附带 minimal example | ✓ |

**User's choice:** 全部 public API + 嵌入使用示例
**Notes:** 每个公开 API 都需附带可运行的代码片段。

---

## 示例代码形式

| Option | Description | Selected |
|--------|-------------|----------|
| 单个 Jupyter Notebook | 6 种 mode 逐一演示 | |
| 多个独立 .py 脚本 | 每个 mode 一个脚本 | |
| 完整 examples/ 目录 | Notebook + 脚本 + 配置模板 | ✓ |

**User's choice:** 完整 `examples/` 目录
**Notes:** 参照 LangChain cookbook 模式，包含 walkthrough notebook、独立脚本和 .env 模板。

---

## 文档发布位置

| Option | Description | Selected |
|--------|-------------|----------|
| GitHub Pages | 免费，与 repo 同源，CI 自动部署 | ✓ |
| ReadTheDocs | Python 生态传统选择，自动构建 | |
| 仅 in-repo Markdown | 零配置，GitHub 直接渲染 | |

**User's choice:** GitHub Pages
**Notes:** 与 MkDocs 最自然的搭配，`mkdocs gh-deploy` 一行命令部署。

---

## Claude's Discretion

- README 结构（用户跳过，由 Claude 决定）
- README 语言：中英双语（中文为主，技术术语保留英文）
- Examples 覆盖范围：至少覆盖 naive/local/global/hybrid
- Docs 导航结构：由 Claude 在 mkdocs.yml 中决定

## Deferred Ideas

- 多语言文档 (i18n) — 未来 phase
- CONTRIBUTING.md — 单独 phase
